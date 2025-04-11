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

import errno
import json
import logging
import os
import pprint
import shutil
import sys
import tempfile
import weakref
from collections import defaultdict
from configparser import ConfigParser
from copy import deepcopy, copy
from pathlib import Path

from steamosatomupd.image import Image
from steamosatomupd.update import UpdateCandidate, UpdatePath, UpdateType
from steamosatomupd.utils import get_update_size, extract_index_from_raucb, get_precise_update_size

log = logging.getLogger(__name__)

IMAGE_MANIFEST_EXT = '.manifest.json'

# Atomic image things

RAUC_BUNDLE_EXT = '.raucb'
CASYNC_STORE_EXT = '.castr'
CHUNKS_DETAILS_EXT = '.chunks_details.json'


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
    # different variants and branches.
    # Also remove any candidate that is newer than our chosen `newest_candidate`. We may encounter
    # newer candidates when we are searching for the penultimate update or when there are shadow
    # checkpoints.
    filtered_candidates = [candidate for candidate in candidates if
                           candidate.image.variant == newest_candidate.image.variant and
                           candidate.image.branch == newest_candidate.image.branch and
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
        log.info("(%s) can't update to \"%s\"/\"%s\" because it is missing a required checkpoint",
                 image, newest_candidate.image.variant, newest_candidate.image.branch)
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
            # branches, we assume that they are exactly the same image and do not
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
        variants_eol = config.get('Images', 'VariantsEOL', fallback='').split()
        if config.has_section('Images.BranchesToConsider'):
            branches_to_consider = dict(config['Images.BranchesToConsider'])
        else:
            branches_to_consider = {}
        if config.has_section('Images.ProvideRemoteInfoConfig'):
            remote_info_variants = config['Images.ProvideRemoteInfoConfig'].get('Variants', '').split()
            remote_info_branches = config['Images.ProvideRemoteInfoConfig'].get('Branches', '').split()
        else:
            remote_info_variants = []
            remote_info_branches = []
        self._create_pool(config['Images']['PoolDir'],
                          config['Images'].getboolean('Unstable'),
                          config['Images']['Products'].split(),
                          config['Images']['Releases'].split(),
                          config['Images']['Variants'].split(),
                          dict((pair.split(':') for pair in variants_eol)),
                          config['Images']['Branches'].split(),
                          branches_to_consider,
                          config['Images']['Archs'].split(),
                          config['Images'].getboolean('StrictPoolValidation', True),
                          remote_info_variants,
                          remote_info_branches)

    @classmethod
    def validate_config(cls, config: ConfigParser) -> None:
        """Validate a ConfigParser.

        The execution will stop if the validation fails."""

        options = ['PoolDir', 'Unstable', 'Products', 'Releases', 'Variants', 'Branches', 'Archs']
        for option in options:
            if not config.has_option('Images', option):
                log.error("Please provide a valid configuration file, the option '%s' is missing", option)
                sys.exit(1)

        if config.has_section('Images.ProvideRemoteInfoConfig'):
            if not config['Images.ProvideRemoteInfoConfig'].get('Variants', ''):
                log.error("Please provide a valid configuration file, the section 'ProvideRemoteInfoConfig' is missing "
                          "the 'Variants' option")
                sys.exit(1)
            if not config['Images.ProvideRemoteInfoConfig'].get('Branches', ''):
                log.error("Please provide a valid configuration file, the section 'ProvideRemoteInfoConfig' is missing "
                          "the 'Branches' option")
                sys.exit(1)

    def _create_pool(self, images_dir: str, want_unstable_images: bool, supported_products: list[str],
                     supported_releases: list[str], supported_variants: list[str], variants_eol: dict[str, str],
                     supported_branches: list[str], branches_to_consider: dict[str, str],
                     supported_archs: list[str], strict_pool_validation: bool,
                     remote_info_variants: list[str], remote_info_branches: list[str]) -> None:

        # Make sure the images directory exist
        images_dir = os.path.abspath(images_dir)
        if not os.path.isdir(images_dir):
            raise RuntimeError("Images dir '{}' does not exist".format(images_dir))

        # Our variables
        self.images_dir = images_dir
        self.want_unstable_images = want_unstable_images
        self.supported_products = supported_products
        self.supported_releases = supported_releases
        self.supported_variants = supported_variants
        self.variants_eol = variants_eol
        self.supported_branches = supported_branches
        self.supported_archs = supported_archs
        self.strict_pool_validation = strict_pool_validation
        self.image_updates_found: list[UpdateCandidate] = []
        self.extract_dir = tempfile.mkdtemp()

        self.branches_to_consider: dict[str, list[str]] = {}
        for branch in branches_to_consider:
            self.branches_to_consider[branch] = branches_to_consider[branch].split()

        self.remote_info_config_variants = remote_info_variants
        self.remote_info_config_branches = remote_info_branches

        self._finalizer = weakref.finalize(self, shutil.rmtree, self.extract_dir)

        self.candidates: dict[str, list[UpdateCandidate]] = defaultdict(list)

        # Create a set to store all the images that we encounter. This is used to ensure we don't have
        # multiple images with the same version, release and buildid.
        images_found: set[Image] = set()

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
                    with open(manifest_path, 'r', encoding='utf-8') as m:
                        data = json.load(m)

                    image = Image.from_dict(data)
                except Exception as e:
                    raise RuntimeError('Failed to create image from manifest %s' % f) from e

                if image in images_found:
                    raise RuntimeError("There are two images in the pool with the same version %s and buildid %s. "
                                       "This is not allowed!" % (image.get_version_str(), image.buildid))

                images_found.add(image)

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

        seen_intro: dict[str, list[int]] = defaultdict(list)
        seen_shadow: dict[str, list[int]] = defaultdict(list)
        seen_intro_skip: list[tuple[str, int]] = []

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
                    if image.introduces_checkpoint in seen_shadow[f'{image.variant}_{image.branch}']:
                        raise RuntimeError(f"There are two shadow images for the same variant {image.variant}, "
                                           f"branch {image.branch} and checkpoint {image.introduces_checkpoint}!")
                    seen_shadow[f'{image.variant}_{image.branch}'].append(image.introduces_checkpoint)
                elif not image.skip:
                    if image.introduces_checkpoint in seen_intro[f'{image.variant}_{image.branch}']:
                        raise RuntimeError(f"There are two images for the same variant {image.variant}, "
                                           f"and branch {image.branch}, that introduce the same "
                                           f"checkpoint {image.introduces_checkpoint}!")
                    seen_intro[f'{image.variant}_{image.branch}'].append(image.introduces_checkpoint)
                else:
                    seen_intro_skip.append((f'{image.variant}_{image.branch}', image.introduces_checkpoint))

        for variant_branch, introduced_checkpoint in seen_intro_skip:
            if introduced_checkpoint not in seen_intro[variant_branch]:
                log.warning("The pool has a checkpoint for (%s, %s) marked as 'skip', but "
                            "there isn't a canonical checkpoint to replace it.",
                            variant_branch, introduced_checkpoint)

    def __str__(self) -> str:
        return '\n'.join([
            'Images dir: {}'.format(self.images_dir),
            'Unstable  : {}'.format(self.want_unstable_images),
            'Products  : {}'.format(self.supported_products),
            'Releases  : {}'.format(self.supported_releases),
            'Variants  : {}'.format(self.supported_variants),
            'Variants EOL: {}'.format(self.variants_eol),
            'Branches  : {}'.format(self.supported_branches),
            'Branches order: {}'.format(self.branches_to_consider),
            'Archs     : {}'.format(self.supported_archs),
            'Candidates: (see below)',
            '{}'.format(pprint.pformat(self.candidates))
        ])

    def _get_candidate_list(self, image: Image, override_branch='') -> list[UpdateCandidate]:
        """Return the list of update candidates that an image belong to

        The optional 'override_branch' field is used to override the image branch.

        This method also does sanity check, to ensure the image is supported.
        We might raise exceptions if the image is not supported.
        """

        branch = override_branch if override_branch else image.branch

        if (image.product not in self.supported_products
                or image.arch not in self.supported_archs
                or image.release not in self.supported_releases
                or image.variant not in self.supported_variants
                or branch not in self.supported_branches):
            raise ValueError(f'Image ({image.product}, {image.arch}, {image.release}, {image.variant}, {branch}) '
                             'is not supported')

        return self.candidates[f'{image.product}_{image.arch}_{image.release}_{image.variant}_{branch}']

    def get_all_allowed_candidates(self, image: Image,
                                   requested_branch: str) -> tuple[list[UpdateCandidate], list[UpdateCandidate]]:
        """Get a list of UpdateCandidate that are potentially valid updates for the image

        The first list contains all the possible allowed candidates, while the second one has only
        images that are specifically for the requested branch.
        The two lists may differ when the server is configured to take into consideration more
        stable branches.

        The returned lists are sorted in ascending order.
        """
        all_candidates: list[UpdateCandidate] = []

        # Take into consideration all the more stable branches too
        additional_branches: list[str] = self.branches_to_consider.get(requested_branch, [])

        try:
            all_candidates.extend(self._get_candidate_list(image, requested_branch))
        except ValueError as err:
            # Continue to check the additional branches, if any
            log.debug(err)

        for additional_branch in additional_branches:
            try:
                additional_candidates = self._get_candidate_list(image, additional_branch)
                # Remove all additional candidates that are still unversioned. We can't reliably
                # consider additional images for different branches, if they are old snapshot
                # images (no way to really order them). So we just skip over those.
                all_candidates.extend([candidate for candidate in additional_candidates if candidate.image.version])
            except ValueError as err:
                # If the image with that branch is not supported try the next one
                log.debug(err)

        all_candidates.sort(key=lambda x: x.image)

        same_branch_candidates = [candidate for candidate in all_candidates if
                                  candidate.image.branch == requested_branch]

        return all_candidates, same_branch_candidates

    def get_updatepath(self, image: Image, relative_update_path: Path | None,
                       requested_branch: str, candidates: list[UpdateCandidate],
                       estimate_download_size: bool, replacement_eol_variant: str) -> UpdatePath | None:
        """Get an UpdatePath from a given UpdateCandidate list

        Return an UpdatePath object, or None if no updates available.
        """

        if not candidates:
            return None

        if candidates[-1].image.branch != requested_branch:
            log.info("Selected image '%s' from branch '%s', instead of '%s', because is newer",
                     candidates[-1].image.buildid, candidates[-1].image.branch, requested_branch)

        # Only estimate the size of the first update for now. Once we'll have the first
        # checkpoint we can also begin to estimate the subsequent updates, if needed.
        if estimate_download_size and relative_update_path:
            candidates[0] = self.estimate_download_size(image, relative_update_path, candidates[0])

        return UpdatePath(image.release, replacement_eol_variant, candidates)

    def get_updates(self, image: Image, relative_update_path: Path,
                    requested_branch: str, update_type=UpdateType.standard,
                    estimate_download_size=False) -> UpdatePath | None:
        """Get updates

        Look for available update candidates.
        "requested_branch" is used to request updates for a specific branch, which may be the
        same string as "image.branch".
        "relative_update_path" is used to estimate the download size of the updates. The path
        needs to be relative to the pool images directory. If set to None, the download size
        will not be estimated.

        Return an Update object, or None if no updates available.
        """

        replacement_eol_variant = self.variants_eol.get(image.variant, '')

        if replacement_eol_variant:
            log.info("The requested variant '%s' is EOL, going to '%s' instead",
                     image.variant, replacement_eol_variant)
            image = copy(image)
            image.variant = replacement_eol_variant
            if update_type != UpdateType.second_last:
                # Except for the penultimate update, which can be considered a special case,
                # we want to force users out of that image because their original variant
                # was marked as EOL
                update_type = UpdateType.forced

        all_candidates, same_branch_candidates = self.get_all_allowed_candidates(image, requested_branch)
        candidates = _get_update_candidates(all_candidates, image, update_type)
        if not candidates:
            # If we were not able to find a valid update candidate we retry with only candidates
            # that are exactly the requested branch. For example, when we use a BranchOrder we
            # might attempt to go to a more stable branch, but sometimes that could not be possible.
            candidates = _get_update_candidates(same_branch_candidates, image, update_type)

        update_path = self.get_updatepath(image, relative_update_path, requested_branch,
                                          candidates, estimate_download_size, replacement_eol_variant)

        if update_path:
            return update_path

        if update_type == UpdateType.unexpected_buildid:
            if not all_candidates:
                if self.strict_pool_validation:
                    # This can be caused by a configuration error, e.g. the image pool is pointing at the wrong
                    # directory. In those cases it's better to exit with an error to avoid ending up producing
                    # unexpected JSON files.
                    log.error("There is not a single valid candidate for the branch %s. This can be "
                              "caused by having unexpected branches in the server configuration.\nIf you are "
                              "bootstrapping a new server, you might consider the option AllowAbsentImageTypes.",
                              requested_branch)
                    sys.exit(1)
                else:
                    # Even if we don't have a single image in the pool for one of the branches listed in "Branches",
                    # we don't consider this an error and continue anyway. This is a common situation when you are
                    # bootstrapping a new server, and you don't have yet all the image types you expect.
                    log.debug("There is not a valid candidate for the branch %s. Continuing...")
                    return None
            else:
                log.debug("There isn't a fallback update for [%i, %s]",
                          image.requires_checkpoint, requested_branch)
                return None

        if update_type == UpdateType.second_last:
            # This can happen for example when our first valid candidate is a checkpoint and we
            # can't propose a different image
            return None

        if image.should_be_skipped():
            # If the client is using an image that has been removed, we force a downgrade to
            # avoid leaving it with its, probably borked, image.
            update_type = UpdateType.forced
        elif requested_branch != image.branch:
            # Force an update if we are in an unstable branch, and we want to switch back to a
            # more stable branch. By reaching this point it means that there isn't a proper
            # update because our current version is already newer. For this reason we force the
            # update, that will effectively be a downgrade.
            # We do the same even if there isn't an order between the two branches
            if (requested_branch in self.branches_to_consider.get(image.branch, []) or
                    image.branch not in self.branches_to_consider.get(requested_branch, [])):
                update_type = UpdateType.forced

            # If we reached this point, we had a valid branch order. However, for unversioned
            # images we can't reliably consider more stable branches. So we force an update
            # regardless, to allow the requested branch switch.
            if update_type != UpdateType.forced and not image.version:
                update_type = UpdateType.forced

        if update_type == UpdateType.forced:
            candidates_forced = _get_update_candidates(all_candidates, image, update_type)
            if not candidates_forced:
                candidates_forced = _get_update_candidates(same_branch_candidates, image, update_type)

            update_path = self.get_updatepath(image, relative_update_path, requested_branch,
                                              candidates_forced, estimate_download_size, replacement_eol_variant)
            if update_path:
                return update_path

            log.warning("Failed to force an update from '%s' (%s) to '%s'",
                        image.branch, image.buildid, requested_branch)

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

        chunks_details = update_raucb.with_suffix(CHUNKS_DETAILS_EXT)

        if initial_image_index and update_index:
            if chunks_details.is_file():
                update_copy.image.estimated_size = get_precise_update_size(initial_image_index, update_index,
                                                                           chunks_details)
            else:
                # TODO when we start to always include the chunks_details.json file for new images,
                # we can stop doing this fallback estimated update size entirely
                log.info("The download size is only an estimation because the chunks_details file is missing")
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

    def get_supported_branches(self) -> list[str]:
        """ Get list of supported branches"""
        return self.supported_branches

    def generate_remote_info_config(self) -> bool:
        """ If we need to generate the remote-info.conf files """
        return bool(self.remote_info_config_variants)
