# SPDX-License-Identifier: LGPL-2.1+
#
# Copyright © 2018 Collabora Ltd
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

from collections import namedtuple
import errno
import logging
import json
import os
import pprint

import steamosupdate.manifest as mnf
import steamosupdate.version as version

log = logging.getLogger(__name__)

IMAGE_MANIFEST_EXT = '.manifest.json'

#
# Image
#

class Image:

    """An OS image"""

    def __init__(self, manifest, versioning_scheme):
        self.product = manifest.product
        self.release = manifest.release
        self.arch    = manifest.arch
        self.variant = manifest.variant

        try:
            self.version = version.parse_string(manifest.version, versioning_scheme)
        except ValueError:
            raise ValueError("unsupported version '{}'".format(manifest.version))

        self.checkpoint = manifest.checkpoint

        self.rauc_bundle_path = None

    def set_rauc_bundle_path(self, path):
        self.rauc_bundle_path = path

    def is_unstable(self):
        return self.version.is_unstable()

    # Comparison operators only consider version and release, and don't
    # care about 'product', 'arch', and so on. This might be misleading,
    # depending on what you expect from 'img1 == img2'.
    #
    # At a first glance, you might think that comparing versions is enough.
    # However, if we're working with the date-based versioning scheme, it
    # would result in something like 'clockwerk 20181108 > doom 20181102'.
    # Which is not what we want.
    #
    # For this reason, we also consider 'release' in the comparison. This
    # makes the assumption that releases are sorted alphabetically. And we
    # don't support cycling, ie. 'zesty' is after 'artful'.

    def __eq__(self, other):
        return ((self.release, self.version) == (other.release, other.version))

    def __ne__(self, other):
        return ((self.release, self.version) != (other.release, other.version))

    def __lt__(self, other):
        return ((self.release, self.version) <  (other.release, other.version))

    def __le__(self, other):
        return ((self.release, self.version) <= (other.release, other.version))

    def __gt__(self, other):
        return ((self.release, self.version) >  (other.release, other.version))

    def __ge__(self, other):
        return ((self.release, self.version) >= (other.release, other.version))

    def __repr__(self):
        #return "{}-{}-{}-{}-{}".format(self.product, self.release,
        #    self.version, self.arch, self.variant)
        return "{}".format(self.version)

def _make_image(manifest, images_rootdir, image_dir, versioning_scheme):

    """An image is made of a valid manifest, plus the expected
    associated files.
    """

    # Create the image
    image = Image(manifest, versioning_scheme)

    # Check that all the files that should be associated with the
    # manifest exist.
    # TODO Use an artifact file instead of hard-coding?
    # TODO If using path from an artifact file, assert it's relative.
    rauc_bundle = 'rauc/casync-bundle.raucb'
    rauc_bundle_abspath = os.path.join(image_dir, rauc_bundle)
    if not os.path.exists(rauc_bundle_abspath):
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT),
                                rauc_bundle_abspath)

    # Add rauc bundle path
    image_reldir = os.path.relpath(image_dir, images_rootdir)
    rauc_bundle_relpath = os.path.join(image_reldir, rauc_bundle)
    assert not os.path.isabs(rauc_bundle_relpath)
    image.set_rauc_bundle_path(rauc_bundle_relpath)

    return image

#
# Image Pool
#

def _get_next_release(release, releases):

    """Get the next release in the list of releases.

    Releases are expected to be strings, sorted alphabetically, ie:

      [ 'brewmaster, 'clockwerk', 'doom' ]

    Cycling is not supported, ie. we won't go from 'zeus' to 'abaddon'.
    """

    try:
        idx = releases.index(release)
    except ValueError:
        return None

    try:
        next_release = releases[idx + 1]
    except IndexError:
        return None

    return next_release

def _get_update_candidates(images, image, want_unstable):

    # Keep only what's interesting, ie:
    # - every checkpoint image that is more recent
    # - the latest image, if it's more recent, if it's not a checkpoint
    # - possibly discard unstable images

    latest = None
    checkpoints = []

    for i in images:
        if i <= image:
            continue

        if i.is_unstable() and not want_unstable:
            continue

        if i.checkpoint:
            checkpoints.append(i)

        if not latest or i > latest:
            latest = i

    candidates = checkpoints
    if latest and latest not in checkpoints:
        candidates.append(latest)

    return candidates



class ImagePool:

    """An image pool is created by walking an image hierarchy, and
    looking for manifest files. It does not matter how the hierarchy
    is organized.

    Internally, images are stored in the following structure:

    {
      product1: {
        release1: {
          arch1: {
            variant1: [ '3.0', 3.1' ... ],
            variant2: [ '3.0', 3.1' ... ],
          },
          arch2: { ...
          }, ...
        }, ...
      }, ...
    }

    """

    # TODO Should have a watch on the images pool dir, for when
    #      images are added or removed. Another possibility is just
    #      to restart the server when images are added or removed.

    def __init__(self, dirname, versioning_scheme, supported_products, supported_releases,
                 supported_archs, supported_variants):

        # Our expectations
        assert sorted(supported_releases) == supported_releases

        dirname = os.path.abspath(dirname)
        assert os.path.isdir(dirname)

        # Our variables
        self.dirname = dirname
        self.versioning_scheme  = versioning_scheme
        self.supported_products = supported_products
        self.supported_releases = supported_releases
        self.supported_archs    = supported_archs
        self.supported_variants = supported_variants
        self.images = {}

        # Populate the images dict
        log.debug("Walking the image tree: {}".format(dirname))
        for root, dirs, files in os.walk(dirname):
            for f in files:
                # We're looking for image manifest files
                if not f.endswith(IMAGE_MANIFEST_EXT):
                    continue

                # Parse the manifest
                try:
                    manifest_file = os.path.join(root, f)
                    manifest = mnf.make_from_file(manifest_file)
                except Exception as e:
                    log.error("Failed to parse manifest {}: {}".format(f, e))
                    continue

                # Validate the manifest
                if not self.support_manifest(manifest):
                    log.debug("Discarding manifest {}".format(f))
                    continue

                # Create the image
                log.debug("Found supported manifest: {}".format(f))
                try:
                    img = _make_image(manifest, dirname, root, versioning_scheme)
                except Exception as e:
                    log.error("Failed to make image {}: {}".format(f, e))
                    continue

                # Walk the internal image hierarchy, all the way down to
                # the image list. Create missing elements along the way.
                dic = self.images

                for elem in [ img.product, img.release, img.arch ]:
                    if elem not in dic:
                        dic[elem] = {}
                    dic = dic[elem]

                if img.variant not in dic:
                    dic[img.variant] = []
                lst = dic[img.variant]

                # Add image to list
                lst.append(img)

    def __str__(self):
        return '\n'.join([
            'Images dir       : {}'.format(self.dirname),
            'Versioning scheme: {}'.format(self.versioning_scheme),
            'Products         : {}'.format(self.supported_products),
            'Releases         : {}'.format(self.supported_releases),
            'Architectures    : {}'.format(self.supported_archs),
            'Variants         : {}'.format(self.supported_variants),
            '----',
            '{}'.format(pprint.pformat(self.images))
        ])

    def support_manifest(self, manifest):

        """Return True is the manifest describes an image that is supported,
        False otherwise.
        """

        if not manifest.product in self.supported_products:
            return False
        if not manifest.release in self.supported_releases:
            return False
        if not manifest.arch in self.supported_archs:
            return False
        if not manifest.variant in self.supported_variants:
            return False
        try:
            v = version.parse_string(manifest.version, self.versioning_scheme)
        except ValueError:
            return False

        return True

    def _get_updates(self, image, release, want_unstable):

        # Get all applicable images
        try:
            p = image.product
            r = release
            a = image.arch
            v = image.variant
            images = self.images[p][r][a][v]
        except KeyError:
            return None, []

        # Return update candidates
        candidates = _get_update_candidates(images, image, want_unstable)
        return release, candidates


    def get_updates_current(self, image, want_unstable):

        """Get update candidates for image in the current release"""

        return self._get_updates(image, image.release, want_unstable)

    def get_updates_next(self, image, want_unstable):

        """Get update candidates for image in the next release"""

        next_release = _get_next_release(image.release, self.supported_releases)
        if not next_release:
            return None, []

        return self._get_updates(image, next_release, want_unstable)

