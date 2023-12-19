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
import contextlib
from datetime import datetime
import fcntl
import json
import logging
import os
import shutil
import signal
import sys
from difflib import ndiff
from pathlib import Path

import pyinotify # type: ignore

from steamosatomupd.imagepool import ImagePool
from steamosatomupd.update import UpdateCandidate, UpdateType

logging.basicConfig(format='%(levelname)s:%(filename)s:%(lineno)s: %(message)s')
log = logging.getLogger(__name__)
wm = pyinotify.WatchManager()

# Default config
DEFAULT_SERVE_UNSTABLE = False
TRIGGER_FILE = "updated.txt"


@contextlib.contextmanager
def lockpathfile(filepath):
    """ Create a fcntl lock for the given file if possible."""
    with os.fdopen(
        os.open(filepath, os.O_RDWR | os.O_CREAT | os.O_TRUNC, mode=0o666),
        mode="r+",
        buffering=1,
        encoding="utf-8",
        newline="",
    ) as f:
        try:
            fcntl.lockf(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        pid = os.getpid()
        f.write(f"{pid}\n")
        yield True
        fcntl.lockf(f, fcntl.LOCK_UN)
        try:
            os.unlink(filepath)
        except OSError:
            pass


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

            # Copy the trigger file from foo/updated.txt to /meta/<foo>-updated.txt to trigger
            # the next step
            dirname = os.path.dirname(event.pathname)
            type_name = os.path.basename(dirname)

            # We want to copy to cwd/<type_name>-updated.txt
            targetpath = os.path.join(os.getcwd(), '-'.join([type_name, 'updated.txt']))
            log.info("Copying updated.txt to %s", targetpath)
            shutil.copy2(event.pathname, targetpath)

            # Also write timestamp into top level updated.txt file
            iso_date = datetime.now().astimezone().replace(microsecond=0).isoformat() + "\n"
            updated_path = os.path.join(os.getcwd(), 'updated.txt')
            with open(updated_path, "w", encoding='utf-8') as updated_file:
                updated_file.write(iso_date)

    def __init__(self, args=None):
        super().__init__()

        # Arguments

        parser = argparse.ArgumentParser(description="SteamOS Update Server")
        parser.add_argument('-c', '--config', metavar='FILE', required=True,
                            help="configuration file")
        parser.add_argument('-r', '--run-daemon', action='store_true', dest='daemon',
                            help="Run as a daemon. Don't quit when done parsing.")

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

    @staticmethod
    def _write_update_for_image(update_json: str, json_path: Path):
        json_path.parent.mkdir(parents=True, exist_ok=True)

        if json_path.is_file():
            with open(json_path, 'r', encoding='utf-8') as old:
                old_lines = old.readlines()
                new_lines = update_json.splitlines(keepends=True)
                if old_lines == new_lines:
                    log.debug('"%s" has not changed, skipping...', json_path)
                    return
                if log.level <= logging.INFO:
                    ndiff_out = ndiff(old_lines, new_lines)
                    differences = [li for li in ndiff_out if li[0] != ' ']
                    log.info('Replacing "%s":\n%s', json_path, ''.join(differences))

        with open(json_path, 'w', encoding='utf-8') as file:
            file.write(update_json)

    def _write_update_json(self, image_update: UpdateCandidate, requested_variant: str,
                           json_path: Path, update_jsons: set[Path],
                           update_type=UpdateType.standard, estimate_download_size=False) -> None:
        """Get the available updates and write them in a JSON"""

        image = image_update.image
        update_path = Path(image_update.update_path)

        if json_path in update_jsons:
            log.debug('"%s" has been already written, skipping...', json_path)
            return

        update_jsons.add(json_path)

        update = self.image_pool.get_updates(image, update_path, requested_variant, update_type,
                                             estimate_download_size)
        update_dict = update.to_dict() if update else {}

        self._write_update_for_image(json.dumps(update_dict, sort_keys=True, indent=4), json_path)

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
        # List of update JSONs that point to the penultimate images available.
        # The ${variant}.second_last.json will be written up one level, compared to the usual
        # directory
        second_last_update_jsons: set[Path] = set()

        # Number of images for which we should pre-estimate the download size.
        # This is an arbitrary number chosen to be not big enough to slow down the static
        # server execution needlessly. At the current release rate, this should cover
        # 1 year of updates. If a client has a base image so old that wasn't
        # included in the server pre-estimation, it will perform an estimation itself,
        # which usually takes up to 10 seconds to complete.
        index_cutoff = 150

        image_updates.sort(key=lambda x: x.image, reverse=True)

        for index, image_update in enumerate(image_updates):
            image = image_update.image

            # If this is a checkpoint, we include the estimated download size regardless of how old
            # it is, because it's likely a considerable amount of devices will pass through this one.
            estimate_download_size = index < index_cutoff or image.is_checkpoint()

            for requested_variant in supported_variants:
                json_path = Path(image.get_update_path(requested_variant))
                json_path_fallback = Path(image.get_update_path(requested_variant, fallback=True))
                json_path_second_last = Path(image.get_update_path(requested_variant, second_last=True))

                if image.shadow_checkpoint:
                    if json_path.exists():
                        log.error("We have a meta JSON file for the shadow checkpoint '%s'.\n"
                                  "Are you trying to convert a regular image into a shadow checkpoint?\n"
                                  "This is not allowed! Shadow checkpoints are special images.", image)
                        return 1

                    # Shadow checkpoints are not real images.
                    # It is not possible for users to be running them.
                    continue

                self._write_update_json(image_update, requested_variant, json_path, update_jsons,
                                        UpdateType.standard, estimate_download_size)

                # Skip the download size estimation for the generic fallbacks, because we have no
                # way of knowing what's the base image the client is using.
                self._write_update_json(image_update, requested_variant, json_path_fallback,
                                        fallback_update_jsons, UpdateType.unexpected_buildid)
                self._write_update_json(image_update, requested_variant, json_path_second_last,
                                        second_last_update_jsons, UpdateType.second_last)

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
    try:
        server = UpdateParser(args)
    except RuntimeError as re:
        log.error(re)
        sys.exit(1)

    # Lock so we don't ever end up with multiple staticserver.py parsing
    # a single image pool.
    lock_path = os.path.join(os.getcwd(), ".lockfile.lock")
    with lockpathfile(lock_path) as lockstatus:
        if not lockstatus:
            log.warning("==== Another instance of staticserver is writing into this meta path, aborting.")
            sys.exit(1)
        else:
            log.info("==== Created lock file at: %s", lock_path)
            exit_code = server.parse_all()

            if exit_code != 0:
                sys.exit(exit_code)

            if server.daemon:
                notifier = pyinotify.Notifier(wm, server)
                mask = pyinotify.IN_CREATE | pyinotify.IN_ATTRIB
                # Watch each of the subfolders of the PoolDir but none deeper
                paths = server.paths_to_watch()
                for path in paths:
                    wm.add_watch(path, mask, rec=False)

                notifier.loop()

            return exit_code
