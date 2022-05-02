# SPDX-License-Identifier: LGPL-2.1+
#
# Copyright © 2018-2020 Collabora Ltd
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
import sys
from configparser import ConfigParser
from typing import Union

from steamosatomupd.image import Image
from steamosatomupd.manifest import Manifest
from steamosatomupd.update import UpdateCandidate, UpdatePath, Update

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
                           force_update: bool) -> list[UpdateCandidate]:
    """Get possible update candidates within a list.

    This is where we decide who are the valid update candidates for a
    given image. The valid candidates are:
    - images that are more recent than image
    - images that are either a checkpoint, either the latest image
    """

    # TODO Add an option to force always an update, even if it ends up being a downgrade

    latest = None
    checkpoints = []

    for candidate in candidates:
        if force_update:
            if not latest or candidate.image > latest.image:
                latest = candidate

        if candidate.image <= image:
            continue

        if candidate.image.checkpoint:
            checkpoints.append(candidate)

        if not latest or candidate.image > latest.image:
            latest = candidate

    winners = checkpoints
    if latest and latest not in winners:
        winners.append(latest)

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
                          config['Images'].getboolean('Snapshots'),
                          config['Images'].getboolean('Unstable'),
                          config['Images']['Products'].split(),
                          config['Images']['Releases'].split(),
                          config['Images']['Variants'].split(),
                          config['Images']['Archs'].split())

    @classmethod
    def validate_config(cls, config: ConfigParser) -> None:
        """Validate a ConfigParser.

        The execution will stop if the validation fails."""

        options = ['PoolDir', 'Snapshots', 'Unstable', 'Products', 'Releases', 'Variants', 'Archs']
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

    def _create_pool(self, images_dir: str, work_with_snapshots: bool,
                     want_unstable_images: bool, supported_products: list[str],
                     supported_releases: list[str], supported_variants: list[str],
                     supported_archs: list[str]) -> None:

        # Make sure the images directory exist
        images_dir = os.path.abspath(images_dir)
        if not os.path.isdir(images_dir):
            raise RuntimeError("Images dir '{}' does not exist".format(images_dir))

        # Make sure releases are sorted
        if not sorted(supported_releases) == supported_releases:
            raise RuntimeError("Release list '{}' is not sorted".format(supported_releases))

        # If we work with snapshots, then obviously we want to consider unstable images
        # (as snapshots are treated as unstable images)
        if work_with_snapshots:
            want_unstable_images = True

        # Our variables
        self.images_dir = images_dir
        self.work_with_snapshots = work_with_snapshots
        self.want_unstable_images = want_unstable_images
        self.supported_products = supported_products
        self.supported_releases = supported_releases
        self.supported_variants = supported_variants
        self.supported_archs = supported_archs
        self.images_found = []

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
            for f in files:
                # We're looking for manifest files
                if not f.endswith(IMAGE_MANIFEST_EXT):
                    continue

                manifest_path = os.path.join(root, f)

                # Create an image instance
                try:
                    manifest = Manifest.from_file(manifest_path)
                except Exception as e:
                    log.error("Failed to create image from manifest %s: %s", f, e)
                    continue

                image = manifest.image

                # Get an update path for this image
                try:
                    update_path = _get_rauc_update_path(images_dir, manifest_path)
                except Exception as e:
                    log.debug("Failed to get update path for manifest %s: %s", f, e)
                    continue

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

                # Only add it as an image found if it's valid, etc.
                self.images_found.append(image)

                # Add image as an update candidate
                candidate = UpdateCandidate(image, update_path)
                candidates.append(candidate)
                log.debug("Update candidate added from manifest: %s", f)

    def __str__(self) -> str:
        return '\n'.join([
            'Images dir: {}'.format(self.images_dir),
            'Snapshots : {}'.format(self.work_with_snapshots),
            'Unstable  : {}'.format(self.want_unstable_images),
            'Products  : {}'.format(self.supported_products),
            'Releases  : {}'.format(self.supported_releases),
            'Variants  : {}'.format(self.supported_variants),
            'Archs     : {}'.format(self.supported_archs),
            'Candidates: (see below)',
            '{}'.format(pprint.pformat(self.candidates))
        ])

    def _get_candidate_list(self, image: Image, override_release='') -> list[UpdateCandidate]:
        """Return the list of update candidates that an image belong to

        The optional 'override_release' field is used to override the image release.

        This method also does sanity check, to ensure the image is supported.
        We might raise exceptions if the image is not supported.
        """

        # Mixing snapshot and non-snapshot images is not allowed
        if image.version and self.work_with_snapshots:
            raise ValueError("Image has a version, however we support only snapshots")
        if not image.version and not self.work_with_snapshots:
            raise ValueError("Image is a snapshot, however we support only versions")

        # Get the image list according to image details
        try:
            product = image.product
            release = override_release if override_release else image.release
            variant = image.variant
            arch = image.arch
            candidates = self.candidates[product][arch][release][variant]
        except KeyError as e:
            # None with that variant, so don't suggest anything
            raise ValueError("Image is not supported") from e

        return candidates

    def get_updates_for_release(self, image: Image, release: str,
                                force_update: bool) -> Union[UpdatePath, None]:
        """Get a list of update candidates for a given release

        Return an UpdatePath object, or None if no updates available.
        """

        try:
            all_candidates = self._get_candidate_list(image, release)
        except ValueError:
            return None

        candidates = _get_update_candidates(all_candidates, image, force_update)
        if not candidates:
            return None

        return UpdatePath(release, candidates)

    def get_updates(self, image: Image, force_update) -> Union[Update, None]:
        """Get updates

        We look for update candidates in the same release as the image,
        and in the next release (if any).

        Return an Update object, or None if no updates available.
        """

        curr_release = image.release
        minor_update = self.get_updates_for_release(image, curr_release, force_update=False)

        next_release = _get_next_release(curr_release, self.supported_releases)
        major_update = None
        if next_release:
            major_update = self.get_updates_for_release(image, next_release, force_update=False)

        if minor_update or major_update:
            return Update(minor_update, major_update)

        if force_update:
            minor_update = self.get_updates_for_release(image, curr_release, force_update)
            return Update(minor_update, major_update)

        return None

    def get_images_found(self) -> list[Image]:
        """ Get list of images found

        To iterate over the list of known images we need a list of known images

        Return a list of Image objects.
        """
        return self.images_found

    def get_supported_variants(self) -> list[str]:
        """ Get list of supported variants"""
        return self.supported_variants
