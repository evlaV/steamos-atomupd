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
import distro
import json
import platform

import steamosupdate.version as version

Manifest = namedtuple(
    'Manifest',
    [ 'product', 'release', 'arch', 'variant', 'version', 'checkpoint' ])

def make_from_data(data):

    """Create a Manifest from a dictionary.

    Raise exceptions if the dictionary doesn't contains the
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

def make_from_running_os():

    """Create a Manifest from the current running system.
    """

    product = distro.id()
    release = distro.codename()
    arch    = platform.machine()
    variant = distro.os_release_info()['variant_id']
    version = distro.version()
    checkpoint = False

    # Tweak architecture a bit
    if arch == 'x86_64':
        arch = 'amd64'

#    # TODO This needs to be set !!
#    try:
#        variant = distro.os_release_info()['variant_id']
#    except KeyError:
#        variant = ''

    # Check if we understand the version
    v = version.parse_string(version, 'guess')

    # TODO run that a bit, test

    manifest = Manifest(product, release, arch, variant, version, checkpoint)

    return manifest

def write_to_string(manifest, **kwargs):

    """Write a Manifest to file.
    """

    data = manifest._asdict()
    return json.dumps(data, **kwargs)
