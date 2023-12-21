# SPDX-License-Identifier: LGPL-2.1+
#
# Copyright © 2018-2024 Collabora Ltd
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

import argparse

from steamosatomupd.image import Image
from steamosatomupd.manifest import Manifest


def main(args=None):
    """Make a manifest from the os-release file"""

    parser = argparse.ArgumentParser(
        description='\n'.join([
            "Create a manifest of the current system, using the os-release file.",
            "Feel free to use the optional arguments to override the values from",
            "the os-release file, in case you know better."
        ]))
    parser.add_argument('--product', default='')
    parser.add_argument('--release', default='')
    parser.add_argument('--variant', default='')
    parser.add_argument('--arch', default='')
    parser.add_argument('--version', default='')
    parser.add_argument('--buildid', default='')
    parser.add_argument('--introduces-checkpoint', type=int, default=0)
    parser.add_argument('--requires-checkpoint', type=int, default=0)

    args = parser.parse_args(args)

    try:
        image = Image.from_os(product=args.product, release=args.release, variant=args.variant,
                              arch=args.arch, version_str=args.version, buildid_str=args.buildid,
                              introduces_checkpoint=args.introduces_checkpoint,
                              requires_checkpoint=args.requires_checkpoint)
    except Exception as e:
        raise RuntimeError("Failed to create manifest") from e

    manifest = Manifest(image)
    manifest_string = manifest.to_string()
    print("{}".format(manifest_string))
