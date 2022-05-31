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

# This script doesn't serve json live it only writes static json
# files to disk for serving with some other web server, etc.

import argparse
import configparser
import json
import logging
import sys
from copy import deepcopy
from pathlib import Path
from typing import Union

from steamosatomupd.image import Image, BuildId
from steamosatomupd.imagepool import ImagePool
from steamosatomupd.update import UpdateCandidate

logging.basicConfig(format='%(levelname)s:%(filename)s:%(lineno)s: %(message)s')
log = logging.getLogger(__name__)

# Default config
DEFAULT_SERVE_UNSTABLE = False


class UpdateParser:
    """Image pool with static update JSON files"""

    def get_update(self, image: Image, update_path: Union[Path, None],
                   requested_variant='') -> dict:
        """Get the update candidates from the provided image"""

        # Get update candidates
        update = self.image_pool.get_updates(image, update_path, requested_variant)
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

    def _write_update_json(self, image_update: UpdateCandidate, requested_variant: str,
                           update_jsons: set[Path]) -> None:
        """Get the available updates and write them in a JSON

        The updates will also be checked against an image that has an
        old/invalid/unknown buildid and the variant.json will be written up one level.
        """

        image = image_update.image
        out_valid = Path(image.product, image.arch, image.get_version_str(), requested_variant,
                         f'{image.buildid}.json')
        out_invalid = Path(image.product, image.arch, image.get_version_str(),
                           f'{requested_variant}.json')
        # Create a copy because we don't want to change the caller's image
        image_invalid = deepcopy(image)
        image_invalid.buildid = BuildId.from_string('19000101')

        for img, update_path, out in [(image, Path(image_update.update_path), out_valid),
                                      (image_invalid, None, out_invalid)]:
            if out in update_jsons:
                log.debug('"%s" has been already written, skipping...', out)
                continue

            update_jsons.add(out)

            out.parent.mkdir(parents=True, exist_ok=True)

            jsonresult = json.dumps(self.get_update(img, update_path, requested_variant),
                                    sort_keys=True, indent=4)
            print(f"--- Jsonresult for {json.dumps(img.to_dict())} with variant "
                  f"{requested_variant} is {jsonresult} ---")
            with open(out, 'w', encoding='utf-8') as file:
                file.write(jsonresult)

    def parse_all(self) -> int:
        """Create file structure as needed based on known images"""

        image_updates = self.image_pool.get_image_updates_found()
        supported_variants = self.image_pool.get_supported_variants()
        update_jsons: set[Path] = set()
        for image_update in image_updates:
            for requested_variant in supported_variants:
                self._write_update_json(image_update, requested_variant, update_jsons)

        return 0


def main(args=None):
    """"Creates the image pool with static update JSON files"""
    server = UpdateParser(args)
    exit_code = server.parse_all()
    return exit_code
