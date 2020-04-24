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

import argparse
import configparser
import json
import logging
import os
import signal
import sys
import time

from steamosatomupd.image import Image
from steamosatomupd.imagepool import ImagePool

logging.basicConfig(format='%(levelname)s:%(filename)s:%(lineno)s: %(message)s')
log = logging.getLogger(__name__)

# Default config
DEFAULT_FLASK_HOSTNAME = 'localhost'
DEFAULT_FLASK_PORT = 5000
DEFAULT_SERVE_UNSTABLE = False

# Global
IMAGE_POOL = None
IMAGES_DIR = None
SNAPSHOTS = None
UNSTABLE = None
PRODUCTS = None
RELEASES = None
VARIANTS = None
ARCHS = None

#
# Flask server
#

from flask import Flask, abort, request
app = Flask(__name__)

@app.route('/')
def foo():

    """Handle requests from client"""

    log.debug("Request: {}".format(request.args))
    if not IMAGE_POOL:
        return ''

    # Make an image out of the request arguments. An exception might
    # be raised, which results in returning 400 to the client.
    image = Image.from_dict(request.args)

    # Get update candidates
    update = IMAGE_POOL.get_updates(image)
    if not update:
        return ''

    # Return to client
    data = update.to_dict()
    log.debug("Reply: {}".format(data))

    return json.dumps(data)

#
# Update server
#

def handle_sigusr1(signum, frame):
    assert signum == signal.SIGUSR1
    if not IMAGE_POOL:
        return

    print('{}'.format(IMAGE_POOL), flush=True)

def handle_sigusr2(signum, frame):
    assert signum == signal.SIGUSR2

    start = time.time()
    image_pool = ImagePool(IMAGES_DIR, SNAPSHOTS, UNSTABLE, PRODUCTS, RELEASES,
                           VARIANTS, ARCHS)
    end = time.time()
    elapsed = end - start
    print("Image pool created in {0:.3f} seconds".format(elapsed))
    print("--- Image Pool ---")
    print('{}'.format(image_pool))
    print("------------------")
    sys.stdout.flush()

    global IMAGE_POOL
    IMAGE_POOL = image_pool

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
            },
            'Images': {
                'Unstable': DEFAULT_SERVE_UNSTABLE,
            }})

        with open(args.config, 'r') as f:
            config.read_file(f)

        # Create image pool

        try:
            images_dir = config['Images']['PoolDir']
            snapshots = config['Images'].getboolean('Snapshots')
            unstable = config['Images'].getboolean('Unstable')
            products = config['Images']['Products'].split()
            releases = config['Images']['Releases'].split()
            variants = config['Images']['Variants'].split()
            archs    = config['Images']['Archs'].split()
        except KeyError:
            log.error("Please provide a valid configuration file")
            sys.exit(1)

        # We strongly expect releases to be an ordered list. We could sort
        # it ourselves, but we can also just refuse an unsorted list, and
        # take this chance to warn user that we care about releases being
        # ordered (because we might use release names to compare to image,
        # and a clockwerk image (3.x) is below a doom (4.x) image).

        if sorted(releases) != releases:
            log.error("Releases in configuration file must be ordered!")
            sys.exit(1)

        # Save some stuff for later

        global IMAGES_DIR
        global SNAPSHOTS
        global UNSTABLE
        global PRODUCTS
        global RELEASES
        global VARIANTS
        global ARCHS
        IMAGES_DIR = images_dir
        SNAPSHOTS = snapshots
        UNSTABLE = unstable
        PRODUCTS = products
        RELEASES = releases
        VARIANTS = variants
        ARCHS = archs
        self.config = config

        # Handle signals

        signal.signal(signal.SIGUSR1, handle_sigusr1)
        signal.signal(signal.SIGUSR2, handle_sigusr2)
        os.kill(os.getpid(), signal.SIGUSR2)

    def run(self):

        hostname = self.config['Server']['Host']
        port = int(self.config['Server']['Port'])
        app.run(host=hostname, port=port)



def main():
    server = UpdateServer()
    exit_code = server.run()
    sys.exit(exit_code)
