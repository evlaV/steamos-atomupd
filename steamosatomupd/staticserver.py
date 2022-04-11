# SPDX-License-Identifier: LGPL-2.1+
#
# Copyright © 2018-2021 Collabora Ltd
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

# This script doesn't serve json live it only writes static json
# files to disk for serving with some other web server, etc.

import argparse
import configparser
import json
import logging
import os
import sys

from steamosatomupd.image import Image
from steamosatomupd.imagepool import ImagePool

logging.basicConfig(format='%(levelname)s:%(filename)s:%(lineno)s: %(message)s')
log = logging.getLogger(__name__)

# Default config
DEFAULT_SERVE_UNSTABLE = False


class UpdateParser:
    """Image pool with static update JSON files"""

    def get_update(self, data: dict) -> dict:
        """Get the update candidates from the provided image dictionary"""

        # Make an image out of the request arguments. An exception might be
        # raised, which results in returning 400 to the client.
        image = Image.from_dict(data)
        if not image:
            return {}

        # Get update candidates
        update = self.image_pool.get_updates(image)
        if not update:
            return {}

        # Return to client
        data = update.to_dict()

        return data

    def __init__(self, args=None):

        # Arguments

        parser = argparse.ArgumentParser(description="SteamOS Update Server")
        parser.add_argument('-c', '--config', metavar='FILE', required=True,
                            help="configuration file")
        parser.add_argument('-d', '--debug', action='store_true',
                            help="show debug messages")

        args = parser.parse_args(args)

        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)

        # Config file

        log.debug("Parsing config from file: %s", args.config)

        config = configparser.ConfigParser()

        config.read_dict({
            'Images': {
                'Unstable': DEFAULT_SERVE_UNSTABLE,
            }})

        with open(args.config, 'r', encoding='utf-8') as f:
            config.read_file(f)

        # Create image pool

        # Will sys.exit if invalid
        ImagePool.validate_config(config)

        self.config = config
        image_pool = ImagePool(config)
        self.image_pool = image_pool
        print("--- Image Pool ---")
        print(f'{self.image_pool}')
        print("------------------")
        sys.stdout.flush()

    def parse_all(self) -> int:
        """Create file structure as needed based on known images"""

        images = self.image_pool.get_images_found()
        for image in images:
            # Make sure the product exists
            values = image.to_dict()

            product = values['product']
            variant = values['variant']
            arch = values['arch']
            buildid = values['buildid']
            version = values['version']

            os.makedirs(os.path.join(product, arch, version, variant), exist_ok=True)

            jsonresult = json.dumps(self.get_update(values), sort_keys=True, indent=4)

            print("--- Jsonresult for {} is {} ---".format(json.dumps(values), jsonresult))

            # Write .json files for each variation
            with open(os.path.join(product, arch, version, variant, f'{buildid}.json'),
                      'w', encoding='utf-8') as file:
                file.write(jsonresult)

            # Now check if buildid is old/invalid to write variant.json up one level
            values['buildid'] = '19000101'
            jsonresult = json.dumps(self.get_update(values), sort_keys=True, indent=4)
            print(f"--- Jsonresult for {json.dumps(values)} is {jsonresult} ---")

            with open(os.path.join(product, arch, version, f'{variant}.json'),
                      'w', encoding='utf-8') as file:
                file.write(jsonresult)

        return 0


def main(args=None):
    """"Creates the image pool with static update JSON files"""
    server = UpdateParser(args)
    exit_code = server.parse_all()
    return exit_code
