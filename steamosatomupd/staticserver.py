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
import os
import signal
import sys
from copy import deepcopy
from difflib import ndiff
from pathlib import Path
from typing import Union

import pyinotify # type: ignore

from steamosatomupd.image import Image, BuildId
from steamosatomupd.imagepool import ImagePool
from steamosatomupd.update import UpdateCandidate

logging.basicConfig(format='%(levelname)s:%(filename)s:%(lineno)s: %(message)s')
log = logging.getLogger(__name__)
wm = pyinotify.WatchManager()

# Default config
DEFAULT_SERVE_UNSTABLE = False
TRIGGER_FILE = "updated.txt"


class UpdateParser(pyinotify.ProcessEvent):
    """Image pool with static update JSON files"""

    def process_IN_ATTRIB(self, event):
        """Process a file attribute change event"""
        self.process_file_event(event)

    def process_IN_CREATE(self, event):
        """Process a file creation event"""
        self.process_file_event(event)

    def process_file_event(self, event):
        """Helper method to call from both create and attrib events"""
        if os.path.basename(event.pathname) == TRIGGER_FILE:
            log.info("Trigger created: %s", event.pathname)
            # Run another parse
            self.image_pool = ImagePool(self.config)
            exit_code = self.parse_all()

            if exit_code != 0:
                log.warning("Unable to parse image data, got exit code: %d", exit_code)

            # Delete trigger file
            os.remove(event.pathname)

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
        super().__init__()

        # Arguments

        parser = argparse.ArgumentParser(description="SteamOS Update Server")
        parser.add_argument('-c', '--config', metavar='FILE', required=True,
                            help="configuration file")
        parser.add_argument('-r', '--run-daemon', required=False, action='store_const',
                            dest='daemon', const=True, default=False,
                            help="Run as a daemon. Don't quit when done parsing.")
        parser.add_argument('-s', '--run-single', required=False, action='store_const',
                            dest='daemon', const=False, default=False,
                            help="Run as single application, not a daemon (default).")

        log_group = parser.add_mutually_exclusive_group()
        log_group.add_argument('-d', '--debug', action='store_const', dest='loglevel',
                               const=logging.DEBUG, default=logging.WARNING,
                               help="show debug messages")
        log_group.add_argument('-v', '--verbose', action='store_const', dest='loglevel',
                               const=logging.INFO,
                               help="be more verbose")

        args = parser.parse_args(args)
        logging.getLogger().setLevel(args.loglevel)

        # Config file

        log.debug("Parsing config from file: %s", args.config)

        config = configparser.ConfigParser()

        config.read_dict({
            'Images': {
                'Unstable': DEFAULT_SERVE_UNSTABLE,
            }})

        with open(args.config, 'r', encoding='utf-8') as f:
            config.read_file(f)

        self.daemon = args.daemon

        # Create image pool
        # Will sys.exit if invalid
        ImagePool.validate_config(config)

        self.config = config
        image_pool = ImagePool(config)
        self.image_pool = image_pool
        log.info("--- Image Pool ---")
        log.info(self.image_pool)
        log.info("------------------")

    def _write_update_json(self, image_update: UpdateCandidate, requested_variant: str,
                           update_jsons: set[Path], fallback_update_jsons: set[Path]) -> None:
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
            if out in update_jsons or out in fallback_update_jsons:
                log.debug('"%s" has been already written, skipping...', out)
                continue

            if update_path:
                update_jsons.add(out)
            else:
                fallback_update_jsons.add(out)

            out.parent.mkdir(parents=True, exist_ok=True)

            jsonresult = json.dumps(self.get_update(img, update_path, requested_variant),
                                    sort_keys=True, indent=4)
            log.debug("--- Jsonresult for %s with variant %s is %s",
                      json.dumps(img.to_dict()), requested_variant, jsonresult)

            if out.is_file():
                with open(out, 'r', encoding='utf-8') as old:
                    old_lines = old.readlines()
                    new_lines = jsonresult.splitlines(keepends=True)
                    if old_lines == new_lines:
                        log.debug('"%s" has not changed, skipping...', out)
                        continue
                    if log.level <= logging.INFO:
                        ndiff_out = ndiff(old_lines, new_lines)
                        differences = [li for li in ndiff_out if li[0] != ' ']
                        log.info('Replacing "%s":\n%s', out, ''.join(differences))

            with open(out, 'w', encoding='utf-8') as file:
                file.write(jsonresult)

    @staticmethod
    def _warn_json_leftovers(update_jsons: set[Path]) -> None:
        """Warn about any eventual JSON leftovers from images that are not available anymore

        The leftovers are only checked in the various `/product/arch/version/variant`
        handled by this static server instance.
        """

        evaluated_directories: set[Path] = set()

        for update_json in update_jsons:
            if update_json.parent in evaluated_directories:
                continue

            evaluated_directories.add(update_json.parent)

            for file in update_json.parent.glob('*.json'):
                if file in update_jsons:
                    continue
                log.warning('"%s" is likely a leftover, probably from a removed image!\n'
                            'This should be either manually removed (is that what you want?) or the deleted '
                            'image\'s JSON manifest should be reinstated with the "skip" option set', file)

    def paths_to_watch(self) -> list[str]:
        """Get paths to watch based on the pool_dir subdirectories"""
        ret_list = []

        # Get all subfolders of config.pool_dir
        pool_dir = self.image_pool.images_dir
        log.info("Watching subdirectories of %s", pool_dir)

        for file in os.listdir(pool_dir):
            d = os.path.join(pool_dir, file)
            if os.path.isdir(d):
                log.info("Watching %s", d)
                ret_list.append(d)

        return ret_list

    def parse_all(self) -> int:
        """Create file structure as needed based on known images"""

        image_updates = self.image_pool.get_image_updates_found()
        supported_variants = self.image_pool.get_supported_variants()
        update_jsons: set[Path] = set()
        # This is the list of update JSONs with invalid/unknown buildid, where the variant.json
        # will be written up one level, compared to the usual directory
        fallback_update_jsons: set[Path] = set()

        for image_update in image_updates:
            for requested_variant in supported_variants:
                self._write_update_json(image_update, requested_variant, update_jsons,
                                        fallback_update_jsons)

        # Pass the canonical update JSONs, because we want to check for leftovers only inside
        # the `/product/arch/version/variant` directories we are actually handling with this
        # server instance
        self._warn_json_leftovers(update_jsons)

        return 0


def signal_handler(_sig, _frame):
    """Handle SIG_INT signal"""
    log.warning("Caught signal, quitting.")
    sys.exit(0)


def main(args=None):
    """"Creates the image pool with static update JSON files"""
    signal.signal(signal.SIGINT, signal_handler)

    # Run once to parse any new images
    server = UpdateParser(args)
    exit_code = server.parse_all()

    if exit_code != 0:
        sys.exit(exit_code)

    if server.daemon:
        notifier = pyinotify.Notifier(wm, server)
        mask = pyinotify.IN_CREATE | pyinotify.IN_ATTRIB
        # Watch each of the subfolders of the PoolDir but none deeper
        paths = server.paths_to_watch()
        for path in paths:
            wm.add_watch(path, mask, rec=True)

        notifier.loop()

    return exit_code
