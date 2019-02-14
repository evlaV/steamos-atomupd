# SPDX-License-Identifier: LGPL-2.1+
#
# Copyright © 2018-2019 Collabora Ltd
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

from steamosupdate.image import Image
from steamosupdate.imagepool import ImagePool

logging.basicConfig(format='%(levelname)s:%(filename)s:%(lineno)s: %(message)s')
log = logging.getLogger(__name__)

# Default config
DEFAULT_FLASK_HOSTNAME = 'localhost'
DEFAULT_FLASK_PORT = 5000

# Global
IMAGE_POOL = None

#
# Flask server
#

from flask import Flask, abort, request
app = Flask(__name__)

@app.route('/')
def foo():

    """Handle requests from client"""

    log.debug("Request: {}".format(request.args))

    # TODO Add a test case for want_unstable

    # Is the client interested in unstable versions?
    want_unstable = request.args.get('want-unstable', False)

    # Make an image out of the request arguments. An exception might
    # be raised, which results in returning 400 to the client.
    image = Image.from_dict(request.args)

    # Get update candidates
    update = IMAGE_POOL.get_updates(image, want_unstable)
    if not update:
        return ''

    # Return to client
    data = update.to_dict()
    log.debug("Reply: {}".format(data))

    return json.dumps(data)

#
# Update server
#

class UpdateServer:

    def __init__(self):

        # Arguments

        parser = argparse.ArgumentParser(
            description = "SteamOS Update Server")
        parser.add_argument('-c', '--config', metavar='FILE', required=True,
            help="configuration file")
        parser.add_argument('-d', '--debug', action='store_true',
            help="show debug messages")

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
            snapshots = config['Images'].getboolean('Snapshots')
            products = config['Images']['Products'].split()
            releases = config['Images']['Releases'].split()
            variants = config['Images']['Variants'].split()
            archs    = config['Images']['Archs'].split()
        except KeyError:
            log.error("Please provide a valid configuration file")
            sys.exit(1)

        # We strongly expect releases to be an ordered list. We could sort
        # it ourselves, but it's even better to refuse an un-ordered list.
        # That's the best opportunity we have to let the user know about our
        # particular expectations on releases.

        if sorted(releases) != releases:
            log.error("Releases in configuration file must be ordered!")
            sys.exit(1)

        start = time.time()
        image_pool = ImagePool(images_dir, snapshots, products, releases,
                               variants, archs)
        end = time.time()
        elapsed = end - start

        print("Image pool created in {0:.3f} seconds".format(elapsed))
        print("--- Image Pool ---")
        print("{}".format(image_pool))
        print("------------------")

        # Save some stuff for later

        global IMAGE_POOL
        IMAGE_POOL = image_pool
        self.config = config

    def run(self):

        hostname = self.config['Server']['Host']
        port = int(self.config['Server']['Port'])
        app.run(host=hostname, port=port)



def main():
    server = UpdateServer()
    exit_code = server.run()
    sys.exit(exit_code)
