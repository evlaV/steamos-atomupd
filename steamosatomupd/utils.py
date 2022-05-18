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

import json
import logging
import subprocess
from pathlib import Path
from typing import Union

log = logging.getLogger(__name__)

DEFAULT_RAUC_CONF = Path('/etc/rauc/system.conf')
FALLBACK_RAUC_CONF = Path('/etc/rauc/fallback-system.conf')
ROOTFS_INDEX = Path('rootfs.img.caibx')


def get_update_size(seed_index: Path, update_index: Path) -> int:
    """Get the estimated update download size

    Returns the estimated size in Bytes or zero if we were not able to estimate
    the download size.
    """

    info = subprocess.run(['desync', 'info', '--seed', seed_index, update_index],
                          check=False,
                          capture_output=True,
                          text=True)

    if info.returncode != 0:
        log.warning("Failed to gather information about the update: %i: %s",
                    info.returncode, info.stdout)
        return 0

    index_info = json.loads(info.stdout)
    return index_info.get("dedup-size-not-in-seed", 0)


def extract_index_from_raucb(raucb_location: Union[Path, str], extract_prefix: Path,
                             unique_dir_name: str) -> Union[Path, None]:
    """Extract the rootfs index file from a rauc bundle.

    The provided raucb location can be either a path or a URL.

    Returns the image rootfs index path or None if an error occurred.
    """

    extract_path = extract_prefix / unique_dir_name
    image_index = extract_path / ROOTFS_INDEX

    if extract_path.exists():
        log.debug("Image '%s' has already been extracted", raucb_location)
    else:
        # Trust the environment because if we are inside a Docker image, we are unable to check
        # the ownership of a bundle. However, the bundle signature is still validated, and the
        # result is only used for estimating the download size.
        extract = subprocess.run(['rauc', 'extract',
                                  '--conf', str(DEFAULT_RAUC_CONF),
                                  '--trust-environment', str(raucb_location), str(extract_path)],
                                 check=False,
                                 stderr=subprocess.STDOUT,
                                 stdout=subprocess.PIPE,
                                 text=True)

        if extract.returncode != 0:
            log.warning("Failed to extract bundle: %i: %s", extract.returncode, extract.stdout)
            return None

    if not image_index.exists():
        log.warning("The extracted bundle '%s' doesn't have the expected '%s' file",
                    raucb_location, ROOTFS_INDEX)
        return None

    return image_index
