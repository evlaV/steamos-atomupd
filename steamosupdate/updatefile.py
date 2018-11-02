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

import json
import os

import steamosupdate.images
import steamosupdate.version as version

def _make_update_candidate(image):
    """Make an update candidate from an Image"""

    data = {
        'version': '{}'.format(image.version),
        'path': image.rauc_bundle_path,
    }

    return data

def validate_candidate(node):
    """Validate an update candidate, which is expected to be like that:

       {
         'version': '3.5',
         'path': 'a/relative/path'
       }

       Raise KeyError or ValueError
    """

    if not all(key in node for key in ['version', 'path']):
        raise KeyError("node missing fields: {}".format(node))

    # possibly raise value error
    version_string = node['version']
    version.parse_string(version_string, 'guess')

    path = node['path']
    if os.path.isabs(path):
        raise ValueError("invalid path (not relative): {}".format(path))


def make_release_node(release, images):
    """Make a release node, which looks like that:

       {
         'release': 'clockwerk',
         'candidates': [ <update-candidate-1>, ... ]
       }
    """

    node = {}

    if not images:
        return node

    node['release'] = release

    candidates = []
    for image in images:
        candidates.append(_make_update_candidate(image))
    node['candidates'] = candidates

    return node
