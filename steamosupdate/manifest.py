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
import json
import platform
import re

import steamosupdate.version as ver

Manifest = namedtuple(
    'Manifest',
    [ 'product', 'release', 'arch', 'variant', 'version', 'checkpoint' ])

def make_from_data(data):

    """Create a Manifest from a dictionary.

    Raise exceptions if the dictionary doesn't contain the
    expected keys.
    """

    # Get mandatory fields, raise KeyError if need be
    product = data['product']
    release = data['release']
    arch    = data['arch']
    variant = data['variant']
    version = data['version']

    # Get optional fields
    checkpoint = False
    if 'checkpoint' in data:
        checkpoint = data['checkpoint']

    # Tweak architecture a bit
    if arch == 'x86_64':
        arch = 'amd64'

    # Return a manifest
    return Manifest(product, release, arch, variant, version, checkpoint)

def make_from_file(filename):

    """Create a Manifest from a json file.
    """

    # Parse the json file, might raise exceptions
    with open(filename, 'r') as f:
        data = json.load(f)

    # Make a manifest from data, might raise exceptions
    return make_from_data(data)

def _load_os_release():

    """Load /etc/os-release in a dictionary
    """

    envre = re.compile(r'''^([^\s=]+)=(?:[\s"']*)(.+?)(?:[\s"']*)$''')
    result = {}

    with open('/etc/os-release') as f:
        for line in f:
            match = envre.match(line)
            if match is not None:
                result[match.group(1)] = match.group(2)

    return result

def make_from_running_os(release, variant, version, checkpoint):

    """Create a Manifest from the current running system.

    If arguments are None, they're looked for in the os-release file,
    except for 'checkpoint', which does not exist in any standard place.
    Note that os-release allows custom additional fields (and recommends
    to use some namespacing), so we could look for 'checkpoint' in a
    custom field named ${PRODUCT}_CHECKPOINT, for example.
    """

    # All these fields have a fallback value in the os-release
    osrel = _load_os_release()
    product = osrel['ID']
    if not release:
        release = osrel['VERSION_CODENAME']
    if not variant:
        variant = osrel['VARIANT_ID']
    if not version:
        version = osrel['VERSION_ID']

    # Arch comes from the platform, with a twist
    arch = platform.machine()
    if arch == 'x86_64':
        arch = 'amd64'

    # Make sure we understand the version
    ver.parse_string(version, 'guess')

    manifest = Manifest(product, release, arch, variant, version, checkpoint)

    return manifest

def write_to_string(manifest, **kwargs):

    """Write a Manifest to a string.
    """

    data = manifest._asdict()
    return json.dumps(data, **kwargs)
