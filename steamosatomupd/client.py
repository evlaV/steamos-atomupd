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

import argparse
import configparser
import json
import logging
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import netrc
import urllib.error
import urllib.parse
import urllib.request
import multiprocessing
from functools import cache
from pathlib import Path
from typing import Union

from steamosatomupd.image import Image
from steamosatomupd.manifest import Manifest
from steamosatomupd.update import Update, UpdatePath

logging.basicConfig(format='%(levelname)s:%(filename)s:%(lineno)s: %(message)s')
log = logging.getLogger(__name__)

# Hard-coded defaults
UPDATE_FILENAME = 'update.json'

# Default args
DEFAULT_CONFIG_FILE = '/etc/steamos-atomupd/client.conf'

# Default config
DEFAULT_MANIFEST_FILE = '/etc/steamos-atomupd/manifest.json'
DEFAULT_RUNTIME_DIR = '/run/steamos-atomupd'

progress_process = multiprocessing.Process()


def sig_handler(_signum, _frame):
    """Handle SIGTERM and SIGINT"""

    if progress_process.is_alive():
        progress_process.kill()
    sys.exit(1)


def do_progress():
    """Print the progression using a journald"""

    journal = subprocess.Popen(['journalctl', '--unit=rauc.service', '--since=now',
                                '--output=cat', '--follow'],
                               stderr=subprocess.STDOUT,
                               stdout=subprocess.PIPE,
                               universal_newlines=True)

    using_desync = is_desync_in_use()
    slot = ""
    while journal.poll() is None:
        line = journal.stdout.readline().rstrip()
        log.debug(line)

        words = line.split()
        if len(words) == 0:
            continue

        if words[0] == "installing" and words[2] == "started":
            print("%d%%" % 0)
        elif words[0] == "installing" and words[2] == "finished":
            print("%d%%" % 100)
        elif words[0] == "installing" and words[2] == "succeeded":
            break
        elif words[0] == "installing" and words[2] == "failed:":
            break
        elif line == "stopping service" or line.startswith("Got exit signal"):
            break
        elif using_desync:
            if words[0].endswith('%') and len(words) < 3:
                print(line.strip())
        else:
            if words[0] == "Slot":
                slot = os.path.basename(os.path.splitext(words[6])[0])
                slot = os.path.splitext(slot)[0]
            elif slot == "rootfs" and ' '.join(words[0:-1]) == "seeding...":
                print("%d%%" % ((float(words[-1][:-1]) * 25 * 0.9 / 100) + 5))
            elif slot == "rootfs" and ' '.join(words[0:-1]) == "downloading chunks...":
                print("%d%%" % ((float(words[-1][:-1]) * 75 * 0.9 / 100) + 5 + (25 * 0.9)))
            elif words[0] == "installing" and ' '.join(words[2:]) == "All slots updated":
                print("%d%%" % 95)
        sys.stdout.flush()

    journal.terminate()


def initialize_http_authentication(url: str):
    """Parse '.netrc' and perform an HTTP basic authentication, if necessary"""

    netrcfile = os.path.expanduser("~/.netrc")
    if os.path.isfile(netrcfile):
        host = urllib.parse.urlparse(url).netloc
        auth = netrc.netrc(netrcfile).authenticators(host)
        if auth:
            login, _, password = auth
            manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
            manager.add_password(None, host, login, password if password else '')
            handler = urllib.request.HTTPBasicAuthHandler(manager)
            opener = urllib.request.build_opener(handler)
            urllib.request.install_opener(opener)


def write_json_to_file(json_str: str) -> str:
    """Write a JSON string to a temporary file

    The filename of the temporary file will be returned.
    """

    try:
        update_data = json.loads(json_str)
    except json.JSONDecodeError as e:
        log.warning("Unable to parse JSON from server: %s", e)
        return ""

    update = Update.from_dict(update_data)

    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write(update.to_string())

    return f.name


def download_update_from_rest_url(url: str) -> str:
    """Download an update file from the server

    The parameters for the request are the details of the image that
    the caller is running.

    The server is expected to return a JSON string, which is then parsed
    by the client, in order to validate it. Then it's printed out to a
    temporary file, and the filename is returned.

    An empty string will be returned if an error occurs.
    """

    log.debug("Downloading update file %s", url)

    initialize_http_authentication(url)

    jsonstr = ""

    tries = 0
    while not jsonstr:

        # Try up to 2 times, removing part of the path each time on 404 responses.
        # Paths look like <product>/<arch>/<version>/<variant>/<buildid>.json
        # Once we get up to <product>/<arch>/<version>/<variant>.json that's the
        # last thing we can check
        # Since a product with an unknown architecture version and variant makes no sense.
        if tries == 2:
            log.warning("Unable to get JSON from server")
            return ""

        tries += 1

        try:
            log.debug("Trying url: %s", url)
            with urllib.request.urlopen(url) as response:
                jsonstr = response.read()

        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            if isinstance(e, urllib.error.HTTPError) and e.code == 404:
                log.debug("Got 404 from server, trying again with less arguments")
                # Try the next level up in the url until we get a json string.
                urlparts = urllib.parse.urlparse(url)
                path = urlparts.path
                pathparts = path.split('/')
                pathparts = pathparts[:-1]

                nextpath = "/".join(pathparts)
                # Add the .json on this new shortened path
                nextpath += '.json'
                url = urlparts._replace(path=nextpath).geturl()
            else:
                log.warning("Unable to get JSON from server: %s", e)
                return ""

    return write_json_to_file(jsonstr)


def download_update_from_query_url(url: str) -> str:
    """Download an update file from the server with a query URL

    The parameters for the request are the details of the image that
    the caller is running.

    The server is expected to return a JSON string, which is then parsed
    by the client, in order to validate it. Then it's printed out to a
    temporary file, and the filename is returned.

    An empty string will be returned if either the server unexpectedly sent us
    an empty reply or if an error occurs.
    """

    log.debug("Downloading update file %s", url)

    initialize_http_authentication(url)

    try:
        with urllib.request.urlopen(url) as response:
            json_str = response.read()

    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        log.warning("Unable to get JSON from server: %s", e)
        return ""

    return write_json_to_file(json_str)


def create_index(replace: bool) -> None:
    """ Re-create index file, and its symlink, for the rootfs """

    seed_index = get_active_slot_index()
    if seed_index.exists() and not replace:
        return

    seed_index.unlink(missing_ok=True)

    rootfs_dir = get_rootfs_device()
    log.debug('Creating the index file for the active rootfs %s', rootfs_dir)
    subprocess.run(['desync', 'make', seed_index, rootfs_dir],
                   check=True,
                   stderr=subprocess.STDOUT,
                   stdout=subprocess.PIPE,
                   universal_newlines=True)

    # Create a symlink next to the index as required by `desync extract`.
    # We can pass only the index filename to the command.
    rootfs_symlink = seed_index.with_suffix('')
    rootfs_symlink.unlink(missing_ok=True)
    os.symlink(rootfs_dir, rootfs_symlink)


def do_update(url: str, quiet: bool) -> None:
    """Update the system"""

    global progress_process
    if is_desync_in_use():
        # TODO if we skip invalid seeds in Desync we can avoid recreating
        # the seed index
        create_index(replace=True)

    # Remount /tmp with max memory and inodes number
    #
    # This is possible as long as /tmp is backed by a tmpfs. We need
    # this precaution as casync makes a heavy use of its tmpdir in /tmp.
    # It needs enough memory to store the chunks it downloads, and it
    # also needs A LOT of inodes.

    log.debug('Remounting /tmp with max memory and inodes number')
    c = subprocess.run(['mount',
                        '-o', 'remount,size=100%,nr_inodes=1g',
                        '/tmp', '/tmp'],
                       check=False,
                       stderr=subprocess.STDOUT,
                       stdout=subprocess.PIPE,
                       universal_newlines=True)

    if c.returncode != 0:
        log.warning("Failed to remount /tmp: %i: %s", c.returncode, c.stdout)
        # Let's keep going and hope that /tmp can handle the load

    # Let's update now

    if not quiet:
        progress_process = multiprocessing.Process(target=do_progress)
        progress_process.start()
    log.debug('Installing the bundle')
    subprocess.run(['rauc', 'install', url],
                   check=True,
                   stderr=subprocess.STDOUT,
                   stdout=subprocess.PIPE,
                   universal_newlines=True)
    if not quiet and progress_process.is_alive():
        progress_process.join(5)
        if progress_process.is_alive():
            progress_process.terminate()


def estimate_download_size(runtime_dir: Path, update_url: str,
                           buildid: str, required_buildid: str) -> int:
    """Estimate the download size for the provided buildid.

    The estimation will be based against the required_buildid or, if not set,
    against the current active partition.

    Returns the estimated size in Bytes or zero if we were not able to estimate
    the download size.
    """
    if not is_desync_in_use():
        return 0

    destination = runtime_dir / buildid

    # If we already extracted this update bundle, don't do it again
    if not destination.exists():
        c = subprocess.run(['rauc', 'extract', update_url, destination],
                           check=False,
                           stderr=subprocess.STDOUT,
                           stdout=subprocess.PIPE,
                           text=True)

        if c.returncode != 0:
            # Estimating the download size is not a critical operation.
            # If it fails we try to continue anyway.
            log.warning("Failed to extract bundle: %i: %s", c.returncode, c.stdout)
            return 0

    update_index = destination / 'rootfs.img.caibx'
    if not update_index.exists():
        log.warning("The extracted bundle doesn't have the expected 'rootfs.img.caibx' file")
        return 0

    if required_buildid:
        seed = runtime_dir / required_buildid
        if not seed.exists():
            log.debug("Unable to estimate the download size because the "
                      "required base image bundle is missing")
            return 0
    else:
        # This image can be installed directly, use the current active
        # partition as a seed
        create_index(replace=False)
        seed = get_active_slot_index()

    c = subprocess.run(['desync', 'info', '--seed', seed, update_index],
                       check=False,
                       capture_output=True,
                       text=True)

    if c.returncode != 0:
        log.warning(
            "Failed to gather information about the update: %i: %s", c.returncode, c.stdout
        )
        return 0

    index_info = json.loads(c.stdout)
    return index_info.get("dedup-size-not-in-seed", 0)


def ensure_estimated_download_size(update_path: UpdatePath,
                                   images_url: str,
                                   runtime_dir: Path) -> UpdatePath:
    """Estimate the download size for all the candidates in update_path

    If an estimation is already present, it will not be recalculated.

    Returns an UpdatePath object that includes the estimated download sizes.
    """
    if not update_path:
        return update_path
    required_buildid = ""
    for i, candidate in enumerate(update_path.candidates):
        if candidate.image.estimated_size != 0:
            # If the server already provided an estimation for the
            # download size, we don't need to recalculate it
            continue
        update_url = urllib.parse.urljoin(images_url, candidate.update_path)
        update_path.candidates[i].image.estimated_size = estimate_download_size(
            runtime_dir,
            update_url,
            str(candidate.image.buildid),
            required_buildid
        )
        required_buildid = candidate.image.buildid

    return update_path


def prevent_update_loop(update_path: UpdatePath,
                        current_image: Image) -> Union[UpdatePath, None]:
    """Remove the current image from the list of update candidates

    If the server included the current image as the first update candidate, we
    remove it to avoid a possible infinite update loop.
    """
    if not update_path:
        return update_path

    skip_first_candidate = False

    for i, candidate in enumerate(update_path.candidates):
        if candidate.image != current_image:
            continue

        if i == 0:
            skip_first_candidate = True
            log.debug("The requested update will apply the same version that is "
                      "currently in use, skipping it.")
        else:
            # The current image cannot be within the candidates. This effectively
            # causes an update loop, which can not be resolved.
            raise ValueError("Update loop has been detected")

    if skip_first_candidate:
        update_path.candidates.pop(0)

    return update_path if update_path.candidates else None


def get_rootfs_device() -> Path:
    """ Get the rootfs device path from RAUC """

    log.debug('Getting the rootfs device by parsing the RAUC status')
    c = subprocess.run(['rauc', 'status', '--output-format=json'],
                       check=True,
                       capture_output=True,
                       text=True)

    status = json.loads(c.stdout)
    for s in status['slots']:
        # We expect just a single entry for every "slots" object
        slot_name = next(iter(s))
        if s[slot_name]['state'] == 'booted':
            return Path(s[slot_name]['device'])

    raise RuntimeError('Failed to parse the RAUC status output')


def get_rauc_config() -> configparser.ConfigParser:
    """ Return the RAUC system configuration """

    config = configparser.ConfigParser()
    config.read('/etc/rauc/system.conf')

    return config


@cache
def get_active_slot_index() -> Path:
    """ Get the active slot seed index path from the RAUC configuration

    An error will be raised if the RAUC config doesn't have the expected
    seed path listed in the install-args casync section
    """

    config = get_rauc_config()

    if 'casync' not in config:
        raise RuntimeError("The RAUC config doesn't have the expected 'casync' entry")

    install_args_values = config['casync'].get('install-args', fallback='')

    parser = argparse.ArgumentParser()
    parser.add_argument('--seed')
    install_args, _ = parser.parse_known_args(shlex.split(install_args_values))

    if not install_args.seed:
        raise RuntimeError('Failed to parse the seed index path from RAUC config')

    log.debug('The active slot seed index is located in: %s', install_args.seed)

    return Path(install_args.seed)


@cache
def is_desync_in_use() -> bool:
    """ Use RAUC configuration to check if Desync will be used """

    config = get_rauc_config()

    if 'casync' not in config:
        return False

    return config['casync'].getboolean('use-desync', fallback=False)


class UpdateClient:
    """Class used to search and apply system updates"""

    def __init__(self, args=None):
        self.args = args

    def run(self):
        """Execute the requested operations"""

        # Arguments

        parser = argparse.ArgumentParser(description="SteamOS Update Client")
        parser.add_argument('-c', '--config',
                            metavar='FILE', default=DEFAULT_CONFIG_FILE,
                            help="configuration file (default: {})".format(DEFAULT_CONFIG_FILE))
        parser.add_argument('-q', '--quiet', action='store_true',
                            help="hide output")
        parser.add_argument('-d', '--debug', action='store_true',
                            help="show debug messages")
        parser.add_argument('--query-only', action='store_true',
                            help="only query if an update is available")
        parser.add_argument('--estimate-download-size', action='store_true',
                            help="Include in the update file the estimated "
                                 "download size for each image candidate")
        parser.add_argument('--update-file',
                            help="update from given file, instead of "
                                 "downloading it from server")
        parser.add_argument('--update-from-url',
                            help="update to a specific RAUC bundle image")
        parser.add_argument('--update-version',
                            help="update to a specific buildid version. It will "
                                 "fail if either the update file doesn't contain "
                                 "this buildid or if it requires a base image that "
                                 "is newer than the current one")
        parser.add_argument('--variant',
                            help="use this 'variant' value instead of the one parsed "
                                 "from the manifest file")

        manifest_group = parser.add_mutually_exclusive_group()
        manifest_group.add_argument('--manifest-file',
                                    metavar='FILE',  # can't use default= here, see below
                                    help="manifest file (default: {})".format(DEFAULT_MANIFEST_FILE))
        manifest_group.add_argument('--mk-manifest-file', action='store_true',
                                    help="don't use existing manifest file, make one instead")

        args = parser.parse_args(self.args)

        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)

        # Config file

        log.debug("Parsing config from file: %s", args.config)

        config = configparser.ConfigParser()

        with open(args.config, 'r') as f:
            config.read_file(f)

        query_url = config.get('Server', 'QueryUrl', fallback="")
        meta_url = config.get('Server', 'MetaUrl', fallback="")

        # "NoOptionError" will be raised if this option is not available in
        # the config file
        images_url = config.get('Server', 'ImagesUrl')

        if not images_url:
            raise configparser.Error(
                'The option "ImagesUrl" cannot have an empty value')

        if not images_url.endswith('/'):
            images_url += '/'

        if not query_url and not meta_url:
            raise configparser.Error(
                'Either one of "QueryUrl" or "MetaUrl" must be provided and '
                'not with an empty value')

        runtime_dir = config.get('Host', 'RuntimeDir',
                                 fallback=DEFAULT_RUNTIME_DIR)
        if not os.path.isdir(runtime_dir):
            log.debug("Creating runtime dir %s", runtime_dir)
            os.makedirs(runtime_dir)

        if is_desync_in_use():
            seed_index = get_active_slot_index()
            if not seed_index.parent.is_dir():
                log.debug("Creating active slot index dir %s", seed_index.parent)
                os.makedirs(seed_index.parent)

        if args.update_from_url:
            log.debug("Installing an update from the given URL")
            try:
                do_update(args.update_from_url, args.quiet)
            except Exception as e:
                log.error("Failed to install update from URL: %s", e)
                return -1
            return 0

        # Handle the manifest file logic

        if args.mk_manifest_file:
            manifest_file = None
            log.debug("Not using any manifest file, making one instead")
        else:
            if args.manifest_file:
                manifest_file = args.manifest_file
            elif config.has_option('Host', 'Manifest'):
                manifest_file = config['Host']['Manifest']
            else:
                manifest_file = DEFAULT_MANIFEST_FILE
            log.debug("Using manifest file '%s'", manifest_file)

        # Get details about the current image
        if manifest_file:
            manifest = Manifest.from_file(manifest_file)
            current_image = manifest.image
        else:
            current_image = Image.from_os()

        # Replace the variant value with the one provided as an argument
        if args.variant:
            current_image.variant = args.variant

        # Download update file, unless one is given in args

        if args.update_file:
            update_file = args.update_file
        else:
            tmp_file = ""
            update_file = os.path.join(runtime_dir, UPDATE_FILENAME)

            # Cleanup an eventual previously downloaded update file
            Path(update_file).unlink(missing_ok=True)

            # Download the update file to a tmp file
            # If we have both MetaUrl and QueryUrl, try the meta first and use
            # the query as a fallback
            if meta_url:
                url = meta_url + '/' + current_image.to_update_path()
                tmp_file = download_update_from_rest_url(url)
            if images_url and not tmp_file:
                log.info("MetaURL is either missing or not working, falling "
                         "back to QueryURL")
                url = query_url + '?' + urllib.parse.urlencode(current_image.to_dict())
                tmp_file = download_update_from_query_url(url)

            if not tmp_file:
                return -1

            log.info("Server returned something, guess an update is available")
            shutil.move(tmp_file, update_file)

        # Parse update file

        log.debug("Parsing update file: %s", update_file)

        with open(update_file, 'r') as f:
            update_data = json.load(f)

        if not update_data:
            # With no available updates the server returns an empty JSON
            log.debug("We are up to date")
            return 0

        update = Update.from_dict(update_data)

        if not update:
            log.debug("No update candidate, even though the server returned something")
            log.debug("This is very unexpected, please inspect '%s'", update_file)
            return -1

        update.minor = prevent_update_loop(update.minor, current_image)
        update.major = prevent_update_loop(update.major, current_image)

        # Log a bit

        def log_update(upd):
            log.debug("An update is available for release '%s'", upd.release)
            n_imgs = len(upd.candidates)
            if n_imgs > 0:
                cand = upd.candidates[0]
                img = cand.image
                log.debug("> going to version: %s (%s)", img.version, img.buildid)
                log.debug("> update path: %s", cand.update_path)
            if n_imgs > 1:
                cand = upd.candidates[-1]
                img = cand.image
                log.debug("> final destination: %s (%s)", img.version, img.buildid)
                log.debug("> total number of updates: %i", n_imgs)

        if update.minor:
            log_update(update.minor)

        if update.major:
            log_update(update.major)

        if args.estimate_download_size:
            update.minor = ensure_estimated_download_size(update.minor,
                                                          images_url,
                                                          Path(runtime_dir))
            update.major = ensure_estimated_download_size(update.major,
                                                          images_url,
                                                          Path(runtime_dir))

        # Bail out if needed

        if args.query_only:
            if not args.quiet:
                print(json.dumps(update.to_dict(), indent=2))
            os.remove(update_file)
            return 0

        # Apply update

        # Ensure we're running from a read-only system

        # TODO We probably want to check that the current release matches
        #      our current release, just as a safety check
        # TODO If we're supposed to run unattended, should we validate that?
        #      (like, there should be no X/Wayland or something)
        # TODO Should we check that the versions proposed by the server are
        #      above our own version, or should we trust the server blindly?

        update_path = ""
        if update.major:
            candidate = update.major.candidates[0]
            if not args.update_version or args.update_version == str(candidate.image.buildid):
                update_path = candidate.update_path

        if not update_path and update.minor:
            candidate = update.minor.candidates[0]
            if not args.update_version or args.update_version == str(candidate.image.buildid):
                update_path = candidate.update_path

        if not update_path:
            if args.update_version:
                log.error("The requested update version is not a valid option")
                return -1
            else:
                log.debug("No update")
                return 0

        log.debug("Applying update NOW")

        try:
            update_url = urllib.parse.urljoin(images_url, update_path)
            do_update(update_url, args.quiet)
        except Exception as e:
            log.error("Failed to install update file: %s", e)
            return -1

        return 0


def main(args=None):
    """Search and/or apply system updates"""

    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)

    client = UpdateClient(args)
    ret = client.run()
    sys.exit(abs(ret))
