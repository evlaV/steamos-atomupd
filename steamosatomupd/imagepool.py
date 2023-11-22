# SPDX-License-Identifier: LGPL-2.1+
#
# Copyright © 2018-2022 Collabora Ltd
#
# This package is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This package is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this package.  If not, see
# <http://www.gnu.org/licenses/>.

# Needed to support list annotation for Python 3.7, without using the
# deprecated "typing".
from __future__ import annotations

import errno
import logging
import os
import pprint
import shutil
import sys
import tempfile
import weakref
from configparser import ConfigParser
from copy import deepcopy
from pathlib import Path
from typing import Union

from steamosatomupd.image import Image
from steamosatomupd.manifest import Manifest
from steamosatomupd.update import UpdateCandidate, UpdatePath, Update, UpdateType
from steamosatomupd.utils import get_update_size, extract_index_from_raucb

log = logging.getLogger(__name__)

IMAGE_MANIFEST_EXT = '.manifest.json'

# Atomic image things

RAUC_BUNDLE_EXT = '.raucb'
CASYNC_STORE_EXT = '.castr'


def _get_rauc_update_path(images_dir: str, manifest_path: str) -> str:

    rauc_bundle = manifest_path[:-len(IMAGE_MANIFEST_EXT)] + RAUC_BUNDLE_EXT
    if not os.path.isfile(rauc_bundle):
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), rauc_bundle)

    casync_store = manifest_path[:-len(IMAGE_MANIFEST_EXT)] + CASYNC_STORE_EXT
    if not os.path.isdir(casync_store):
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), casync_store)

    rauc_bundle_relpath = os.path.relpath(rauc_bundle, images_dir)

    return rauc_bundle_relpath

# Image pool


def _get_next_release(release: str, releases: list[str]) -> str:
    """Get the next release in a list of releases.

    Releases are expected to be strings, sorted alphabetically, ie:

      [ 'brewmaster', 'clockwerk', 'doom' ]

    Cycling is not supported, ie. we won't go from 'zeus' to 'abaddon'.
    """

    try:
        idx = releases.index(release)
    except ValueError:
        return ''

    try:
        next_release = releases[idx + 1]
    except IndexError:
        return ''

    return next_release


def _get_update_candidates(candidates: list[UpdateCandidate], image: Image,
                           update_type: UpdateType) -> list[UpdateCandidate]:
    """Get possible update candidates within an ordered list.

    This is where we decide who are the valid update candidates for a
    given image. The valid candidates are:
    - images that are more recent than image
    - images that are either a checkpoint, either the latest image
    """

    previous: UpdateCandidate | None = None
    newest_candidate: UpdateCandidate | None = None
    winners: list[UpdateCandidate] = []

    if not candidates:
        return []

    for candidate in reversed(candidates):
        if candidate.image.shadow_checkpoint:
            continue

        if not newest_candidate:
            newest_candidate = candidate
        elif not previous:
            previous = candidate
            break

    if update_type == UpdateType.second_last:
        # If we are looking for the penultimate update, discard the newest image and
        # replace it with the "previous" ones
        newest_candidate = previous

    if not newest_candidate:
        log.debug("There are no updates for %s/%s/%s",
                  image.version, image.release, image.buildid)
        return []

    if image.get_image_checkpoint() > newest_candidate.image.requires_checkpoint:
        log.info("(%s) can't update to (%s) because it is past a newer checkpoint",
                 image, newest_candidate.image)
        return []

    if not update_type.is_fallback() and update_type != UpdateType.forced:
        if image >= newest_candidate.image:
            log.debug("There aren't newer candidates for %s/%s/%s",
                      image.version, image.release, image.buildid)
            return []

    # Keep only the candidates from the destination image, to avoid hopping between
    # different variants.
    # Also remove any candidate that is newer than our chosen `newest_candidate`. We may encounter
    # newer candidates when we are searching for the penultimate update or when there are shadow
    # checkpoints.
    filtered_candidates = [candidate for candidate in candidates if
                           candidate.image.variant == newest_candidate.image.variant and
                           candidate.image < newest_candidate.image]

    # If the destination requires a newer checkpoint we add the necessary checkpoints to the winners list
    curr_checkpoint = image.get_image_checkpoint()
    for candidate in filtered_candidates:
        if not candidate.image.is_checkpoint():
            continue

        if curr_checkpoint == candidate.image.requires_checkpoint <= newest_candidate.image.requires_checkpoint:
            if not candidate.image.shadow_checkpoint:
                # Save this to the winners list only if it's not a shadow checkpoint.
                # Otherwise, we simply keep track that we passed that checkpoint but do not propose
                # it as an update.
                winners.append(candidate)
            curr_checkpoint = candidate.image.introduces_checkpoint

    if curr_checkpoint != newest_candidate.image.requires_checkpoint:
        log.info("(%s) can't update to \"%s\" because it is missing a required checkpoint",
                 image, newest_candidate.image.variant)
        return []

    if newest_candidate not in winners:
        winners.append(newest_candidate)

    if update_type.is_fallback():
        # If this is a fallback update, there is no need to do additional checks to avoid cycles.
        # We ALWAYS want to propose an upgrade/downgrade because, if a client requested this file,
        # it means its original image is unexpected/broken/deprecated.
        return winners

    for update in winners:
        if update.image == image:
            # If the same image version, release and buildid is available in multiple
            # variants, we assume that they are exactly the same image and do not
            # offer an update. Given that we don't know if a request is for an update,
            # or for a branch switch, this could otherwise introduce an unexpected cycle.
            log.info("Cycle detected, an update for %s/%s/%s can't be safely forced",
                     image.version, image.release, image.buildid)
            return []

    return winners


class ImagePool:

    """An image pool

    An image pool is created by walking an image hierarchy, and
    looking for manifest files. It does not matter how the hierarchy
    is organized.

    The truth is that an image pool doesn't contain Image objects, but
    instead UpdateCandidate objects, which are simply a wrapper above
    images, with an additional update_path attribute.

    Internally, candidates are stored in the following structure:

    {
      product1: {
        arch: {
          release1: {
            variant1: [ CANDIDATE1, CANDIDATE2, ... ],
            variant2: [ ... ]
          },
          release2: { ...
          }, ...
        }, ...
      }, ...
    }

    """

    def __init__(self, config):
        self._create_pool(config['Images']['PoolDir'],
                          config['Images'].getboolean('Unstable'),
                          config['Images']['Products'].split(),
                          config['Images']['Releases'].split(),
                          config['Images']['Variants'].split(),
                          config.get('Images', 'VariantsOrder', fallback='').split(),
                          config['Images']['Archs'].split())

    @classmethod
    def validate_config(cls, config: ConfigParser) -> None:
        """Validate a ConfigParser.

        The execution will stop if the validation fails."""

        options = ['PoolDir', 'Unstable', 'Products', 'Releases', 'Variants', 'Archs']
        for option in options:
            if not config.has_option('Images', option):
                log.error("Please provide a valid configuration file")
                sys.exit(1)

        # We strongly expect releases to be an ordered list. We could sort
        # it ourselves, but we can also just refuse an unsorted list, and
        # take this chance to warn user that we care about releases being
        # ordered (because we might use release names to compare to image,
        # and a clockwerk image (3.x) is below a doom (4.x) image).

        releases = config['Images']['Releases'].split()
        if sorted(releases) != releases:
            log.error("Releases in configuration file must be ordered!")
            sys.exit(1)

    def _create_pool(self, images_dir: str, want_unstable_images: bool,
                     supported_products: list[str], supported_releases: list[str],
                     supported_variants: list[str], variants_order: list[str],
                     supported_archs: list[str]) -> None:

        # Make sure the images directory exist
        images_dir = os.path.abspath(images_dir)
        if not os.path.isdir(images_dir):
            raise RuntimeError("Images dir '{}' does not exist".format(images_dir))

        # Make sure releases are sorted
        if not sorted(supported_releases) == supported_releases:
            raise RuntimeError("Release list '{}' is not sorted".format(supported_releases))

        # Our variables
        self.images_dir = images_dir
        self.want_unstable_images = want_unstable_images
        self.supported_products = supported_products
        self.supported_releases = supported_releases
        self.supported_variants = supported_variants
        self.variants_order = variants_order
        self.supported_archs = supported_archs
        self.image_updates_found: list[UpdateCandidate] = []
        self.extract_dir = tempfile.mkdtemp()

        self._finalizer = weakref.finalize(self, shutil.rmtree, self.extract_dir)

        # Create the hierarchy to store images
        data: dict[str, dict] = {}
        for product in supported_products:
            data[product] = {}
            for arch in supported_archs:
                data[product][arch] = {}
                for release in supported_releases:
                    data[product][arch][release] = {}
                    for variant in supported_variants:
                        data[product][arch][release][variant] = []
        self.candidates = data

        # Populate the candidates dict
        log.debug("Walking the image tree: %s", images_dir)
        for root, dirs, files in os.walk(images_dir):
            # Sort dirs and files to get the same order on all systems.
            dirs.sort()
            files.sort()
            dirs[:] = [d for d in dirs if not d.endswith(".castr")]
            # Exclude hidden directories from the search
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                # We're looking for manifest files
                if not f.endswith(IMAGE_MANIFEST_EXT):
                    continue

                manifest_path = os.path.join(root, f)

                # Create an image instance
                try:
                    manifest = Manifest.from_file(manifest_path)
                except Exception as e:
                    raise RuntimeError('Failed to create image from manifest %s' % f) from e

                image = manifest.image

                if image.should_be_skipped():
                    # This is an image that should not be an update candidate
                    # Record it and then continue
                    log.debug("Not considering %s as a valid update candidate", f)
                    candidate = UpdateCandidate(image, "")
                    self.image_updates_found.append(candidate)
                    continue

                # Get an update path for this image
                try:
                    if image.shadow_checkpoint:
                        # Those are not real images, so we don't expect valid update paths
                        update_path = ''
                    else:
                        update_path = _get_rauc_update_path(images_dir, manifest_path)
                except Exception as e:
                    raise RuntimeError("Failed to get update path for manifest %s" % f) from e

                # Get the list where this image belongs
                try:
                    candidates = self._get_candidate_list(image)
                except Exception as e:
                    log.debug("Discarded unsupported image %s: %s", f, e)
                    continue

                # Discard unstable images if we don't want them
                # TODO check the code to see if it's worth introducing image.is_unstable() for readability
                if not want_unstable_images and not image.is_stable():
                    log.debug("Discarded unstable image %s", f)
                    continue

                # Add image as an update candidate
                candidate = UpdateCandidate(image, update_path)
                self.image_updates_found.append(candidate)
                candidates.append(candidate)
                log.debug("Update candidate added from manifest: %s", f)

        seen_intro: dict[str, list[int]] = {variant: [] for variant in supported_variants}
        seen_shadow: dict[str, list[int]] = {variant: [] for variant in supported_variants}

        # Validate the image pool
        for image_update in self.image_updates_found:
            image = image_update.image

            if 0 < image.introduces_checkpoint <= image.requires_checkpoint:
                raise RuntimeError(f"The image {image.buildid} must require a checkpoint that is "
                                   f"lower than the one it is introducing.")

            if image.shadow_checkpoint:
                if image.introduces_checkpoint < 1:
                    raise RuntimeError(f"The image {image.buildid} is marked as a shadow checkpoint "
                                       f"but doesn't introduce any.")
                if image.skip:
                    raise RuntimeError(f"{image.buildid} can't be a shadow checkpoint and a skip at "
                                       f"the same time. If you want to delete a shadow checkpoint, "
                                       f"you can simply remove its manifest.")

            if image.is_checkpoint():
                if image.shadow_checkpoint:
                    if image.introduces_checkpoint in seen_shadow[image.variant]:
                        raise RuntimeError(f"There are two shadow images for the same variant "
                                           f"{image.variant} and checkpoint {image.introduces_checkpoint}!")
                    seen_shadow[image.variant].append(image.introduces_checkpoint)
                elif not image.skip:
                    if image.introduces_checkpoint in seen_intro[image.variant]:
                        raise RuntimeError(f"There are two images for the same variant {image.variant} "
                                           f"that introduce the same checkpoint {image.introduces_checkpoint}!")
                    seen_intro[image.variant].append(image.introduces_checkpoint)

    def __str__(self) -> str:
        return '\n'.join([
            'Images dir: {}'.format(self.images_dir),
            'Unstable  : {}'.format(self.want_unstable_images),
            'Products  : {}'.format(self.supported_products),
            'Releases  : {}'.format(self.supported_releases),
            'Variants  : {}'.format(self.supported_variants),
            'Variants order: {}'.format(self.variants_order),
            'Archs     : {}'.format(self.supported_archs),
            'Candidates: (see below)',
            '{}'.format(pprint.pformat(self.candidates))
        ])

    def _get_candidate_list(self, image: Image, override_release='',
                            override_variant='') -> list[UpdateCandidate]:
        """Return the list of update candidates that an image belong to

        The optional 'override_release' and 'override_variant' fields are used to respectively
        override the image release and the image variant.

        This method also does sanity check, to ensure the image is supported.
        We might raise exceptions if the image is not supported.
        """

        # Get the image list according to image details
        try:
            product = image.product
            release = override_release if override_release else image.release
            variant = override_variant if override_variant else image.variant
            arch = image.arch
            candidates = self.candidates[product][arch][release][variant]
        except KeyError as e:
            # None with that variant, so don't suggest anything
            raise ValueError("Image is not supported") from e

        return candidates

    def get_all_allowed_candidates(self, image: Image, release: str,
                                   requested_variant: str) -> tuple[list[UpdateCandidate], list[UpdateCandidate]]:
        """Get a list of UpdateCandidate that are potentially valid updates for the image

        The first list contains all the possible allowed candidates, while the second one has only
        images that are specifically for the requested variant.
        The two lists may differ when the server is configured to take into consideration more
        stable variants.

        The returned lists are sorted in ascending order.
        """
        all_candidates: list[UpdateCandidate] = []
        additional_variants: list[str] = []

        if requested_variant in self.variants_order:
            # Take into consideration all the more stable variants too
            variant_index = self.variants_order.index(requested_variant)
            additional_variants = self.variants_order[:variant_index]

        try:
            all_candidates.extend(self._get_candidate_list(image, release, requested_variant))
        except ValueError as err:
            # Continue to check the additional variants, if any
            log.debug(err)

        for additional_variant in additional_variants:
            try:
                additional_candidates = self._get_candidate_list(image, release, additional_variant)
                # Remove all additional candidates that are still unversioned. We can't reliably
                # consider additional images for different variants, if they are old snapshot
                # images (no way to really order them). So we just skip over those.
                all_candidates.extend([candidate for candidate in additional_candidates if candidate.image.version])
            except ValueError as err:
                # If the image with that variant is not supported try the next one
                log.debug(err)

        all_candidates.sort(key=lambda x: x.image)

        same_variant_candidates = [candidate for candidate in all_candidates if
                                   candidate.image.variant == requested_variant]

        return all_candidates, same_variant_candidates

    def get_updatepath(self, image: Image, relative_update_path: Union[Path, None],
                       requested_variant: str, release: str, candidates: list[UpdateCandidate],
                       update_type: UpdateType) -> Union[UpdatePath, None]:
        """Get an UpdatePath from a given UpdateCandidate list

        Return an UpdatePath object, or None if no updates available.
        """

        if not candidates:
            return None

        if candidates[-1].image.variant != requested_variant:
            log.info("Selected image '%s' from variant '%s', instead of '%s', because is newer",
                     candidates[-1].image.buildid, candidates[-1].image.variant, image.variant)

        # Only estimate the size of the first update for now. Once we'll have the first
        # checkpoint we can also begin to estimate the subsequent updates, if needed.
        # Skip this when the update type is a fallback, because we have no way of knowing what's the
        # base image the client is using.
        if relative_update_path and not update_type.is_fallback():
            candidates[0] = self.estimate_download_size(image, relative_update_path, candidates[0])

        return UpdatePath(release, candidates)

    def get_updates(self, image: Image, relative_update_path: Path,
                    requested_variant: str, update_type=UpdateType.standard) -> Union[Update, None]:
        """Get updates

        We look for update candidates in the same release as the image,
        and in the next release (if any).
        "requested_variant" is used to request updates for a specific variant, which may be the
        same string as "image.variant".
        "relative_update_path" is used to estimate the download size of the updates. The path
        needs to be relative to the pool images directory. If set to None, the download size
        will not be estimated.

        Return an Update object, or None if no updates available.
        """

        curr_release = image.release
        all_candidates, same_variant_candidates = self.get_all_allowed_candidates(image, image.release,
                                                                                  requested_variant)
        candidates = _get_update_candidates(all_candidates, image, update_type)
        if not candidates:
            # If we were not able to find a valid update candidate we retry with only candidates
            # that are exactly the requested variant. For example, when we use a VariantOrder we
            # might attempt to go to a more stable variant, but sometimes that could not be possible.
            candidates = _get_update_candidates(same_variant_candidates, image, update_type)

        minor_update = self.get_updatepath(image, relative_update_path, requested_variant,
                                           curr_release, candidates, update_type)

        next_release = _get_next_release(curr_release, self.supported_releases)
        major_update = None
        if next_release:
            all_candidates_next, sv_candidates_next = self.get_all_allowed_candidates(image, next_release,
                                                                                      requested_variant)
            candidates_next = _get_update_candidates(all_candidates_next, image, update_type)
            if not candidates_next:
                candidates_next = _get_update_candidates(sv_candidates_next, image, update_type)
            major_update = self.get_updatepath(image, relative_update_path, requested_variant,
                                               next_release, candidates_next, update_type)

        if minor_update or major_update:
            return Update(minor_update, major_update)

        if update_type == UpdateType.unexpected_buildid:
            if not all_candidates:
                # This can be caused by a configuration error, e.g. we don't have a single image in
                # the image pool for one of the variants listed in "Variants".
                # In those cases it's better to exit with an error to avoid ending up producing
                # unexpected JSON files.
                log.error("There is not a single valid candidate for the variant %s. This can be "
                          "caused by having unexpected variants in the server configuration",
                          requested_variant)
                sys.exit(1)
            else:
                log.debug("There isn't a fallback update for [%i, %s]",
                          image.requires_checkpoint, requested_variant)
                return None

        if update_type == UpdateType.second_last:
            # This can happen for example when our first valid candidate is a checkpoint and we
            # can't propose a different image
            return None

        if image.should_be_skipped():
            # If the client is using an image that has been removed, we force a downgrade to
            # avoid leaving it with its, probably borked, image.
            update_type = UpdateType.forced
        elif requested_variant != image.variant:
            try:
                # Force an update if we are in an unstable variant, and we want to switch back to a
                # more stable variant. By reaching this point it means that there isn't a proper
                # update because our current version is already newer. For this reason we force the
                # update, that will effectively be a downgrade.
                if self.variants_order.index(requested_variant) < self.variants_order.index(image.variant):
                    update_type = UpdateType.forced

                # If we reached this point, we had a valid variant order. However, for unversioned
                # images we can't reliably consider more stable variants. So we force an update
                # regardless, to allow the requested variant switch.
                if update_type != UpdateType.forced and not image.version:
                    update_type = UpdateType.forced
            except ValueError:
                # At least one of those images is not ordered, there is
                # no way of knowing which one is more stable.
                update_type = UpdateType.forced

        if update_type == UpdateType.forced:
            # Force only a minor update. We don't propose a downgrade from a major update because
            # that is not supported and will likely cause unexpected issues.
            candidates_forced = _get_update_candidates(all_candidates, image, update_type)
            if not candidates_forced:
                candidates_forced = _get_update_candidates(same_variant_candidates, image, update_type)

            minor_update = self.get_updatepath(image, relative_update_path, requested_variant,
                                               curr_release, candidates_forced, update_type)
            if minor_update:
                return Update(minor_update, major_update)

            log.warning("Failed to force an update from '%s' (%s) to '%s'",
                        image.variant, image.buildid, requested_variant)

        return None

    def estimate_download_size(self, initial_image: Image, image_relative_path: Path,
                               update: UpdateCandidate) -> UpdateCandidate:
        """Estimate the download size for the update candidate image

        Returns an "update" copy that includes the estimated download size.
        If the operation fails, the estimation will be equal to zero.
        """

        update_copy = deepcopy(update)

        initial_image_raucb = Path(self.images_dir) / image_relative_path
        initial_image_index = extract_index_from_raucb(initial_image_raucb, Path(self.extract_dir),
                                                       initial_image.get_unique_name())

        update_raucb = Path(self.images_dir) / update_copy.update_path
        update_index = extract_index_from_raucb(update_raucb, Path(self.extract_dir),
                                                update_copy.image.get_unique_name())

        if initial_image_index and update_index:
            update_copy.image.estimated_size = get_update_size(initial_image_index, update_index)
        else:
            # Estimating the download size is not a critical operation.
            # If it fails we try to continue anyway.
            log.debug("Unable to estimate the download size, continuing...")
            update_copy.image.estimated_size = 0

        return update_copy

    def get_image_updates_found(self) -> list[UpdateCandidate]:
        """ Get list of image updates found

        To iterate over the list of known images we need a list of known images

        Return a list of UpdateCandidate objects.
        """
        return self.image_updates_found

    def get_supported_variants(self) -> list[str]:
        """ Get list of supported variants"""
        return self.supported_variants
