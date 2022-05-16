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


log = logging.getLogger(__name__)


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
