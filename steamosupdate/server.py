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

import argparse
import configparser
import json
import logging
import os
import sys
import time

import steamosupdate.images as images
import steamosupdate.manifest as mnf
import steamosupdate.updatefile as updatefile

logging.basicConfig(format='%(levelname)s:%(filename)s:%(lineno)s: %(message)s')
log = logging.getLogger(__name__)

# Default args
DEFAULT_CONFIG_FILE = '/etc/steamos-update/server.conf'

# Default config
DEFAULT_FLASK_HOSTNAME = 'localhost'
DEFAULT_FLASK_PORT = 5000

# Global
IMAGE_POOL = None
VERSIONING_SCHEME = None

#
# Flask server
#

from flask import Flask, abort, request
app = Flask(__name__)

@app.route('/')
def foo():

    """Handle requests from client wondering if an update is available.

    The answer might have up to two "release nodes":
    - 'current' list updates available in the current release
    - 'next' list updates available in the next release

    The answer looks like this:

        {
          'current': {
             'release': 'clockwerk',
             'candidates': [ '3.8' ]
          },
          'next': {
             'release': 'doom',
             'candidates': [ '4.0', '4.3' ]
          }
        }
    """

    log.info("Req: {}".format(request.args))

    # Make a manifest out of the request arguments. An exception might
    # be raised, which results in returning 400 to the client.
    manifest = mnf.make_from_data(request.args)

    # Check if this manifest describes a supported image.
    if not IMAGE_POOL.support_manifest(manifest):
        return ''

    # Create image. In case some values are not valid, a ValueError
    # exception is raised, which results in 400 for the client.
    image = images.Image(manifest, VERSIONING_SCHEME)

    # Is the client interested in unstable versions?
    try:
        want_unstable = bool(request.args['want-unstable'])
    except KeyError:
        want_unstable = False

    # Get update candidates
    data = {}

    release, candidates = IMAGE_POOL.get_updates_current(image, want_unstable)
    if candidates:
        data['current'] = updatefile.make_release_node(release, candidates)

    release, candidates = IMAGE_POOL.get_updates_next(image, want_unstable)
    if candidates:
        data['next'] = updatefile.make_release_node(release, candidates)

    # Return that to the client
    log.debug("Data: {}".format(data))
    return json.dumps(data)



class UpdateServer:

    def __init__(self):

        # Arguments

        parser = argparse.ArgumentParser(
            description = "SteamOS Update Server")
        parser.add_argument('-d', '--debug',
            action='store_true',
            help="show debug messages")
        parser.add_argument('-c', '--config',
            metavar='FILE', default=DEFAULT_CONFIG_FILE,
            help="configuration file (default: {})".format(DEFAULT_CONFIG_FILE))

        args = parser.parse_args()

        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)

        # Config file

        log.debug("Parsing config from file: {}".format(args.config))

        config = configparser.ConfigParser()

        config.read_dict({
            'Server': {
                'Host': DEFAULT_FLASK_HOSTNAME,
                'Port': DEFAULT_FLASK_PORT,
            }})

        with open(args.config, 'r') as f:
            config.read_file(f)

        # Create image pool

        try:
            images_dir = config['Images']['PoolDir']
            versioning_scheme  = config['Images']['VersioningScheme']
            products = config['Images']['Products'].split()
            releases = config['Images']['Releases'].split()
            archs    = config['Images']['Archs'].split()
            variants = config['Images']['Variants'].split()
        except KeyError:
            log.error("Please provide a valid configuration file")
            sys.exit(1)

        # We strongly expect releases to be an ordered list. We could
        # sort it ourselves, but it's even better to refuse. That's the
        # best opportunity we have to let user know about our particular
        # expectations on release.

        if sorted(releases) != releases:
            log.error("Releases in configuration file must be ordered!")
            sys.exit(1)

        start = time.time()
        image_pool = images.ImagePool(images_dir, versioning_scheme, products, releases,
                                      archs, variants)
        end = time.time()
        elapsed = end - start

        print("Image pool created in {0:.3f} seconds".format(elapsed))
        print("--- Image Pool ---")
        print("{}".format(image_pool))

        # Save some stuff for later

        global IMAGE_POOL
        IMAGE_POOL = image_pool
        global VERSIONING_SCHEME
        VERSIONING_SCHEME = versioning_scheme
        self.config = config

    def run(self):

        hostname = self.config['Server']['Host']
        port = int(self.config['Server']['Port'])
        app.run(host=hostname, port=port)



def main():
    server = UpdateServer()
    exit_code = server.run()
    sys.exit(exit_code)
