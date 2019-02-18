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
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

from steamosupdate.image import Image
from steamosupdate.manifest import Manifest
from steamosupdate.update import Update

logging.basicConfig(format='%(levelname)s:%(filename)s:%(lineno)s: %(message)s')
log = logging.getLogger(__name__)

# Hard-coded defaults
UPDATE_FILENAME = 'update.json'

# Default args
DEFAULT_CONFIG_FILE = '/etc/steamos-update/client.conf'

# Default config
DEFAULT_MANIFEST      = '/usr/manifest.json'
DEFAULT_RUNTIME_DIR   = '/run/steamos-update'
DEFAULT_WANT_UNSTABLE = 'false'

def download_update_file(url, image, want_unstable):
    """Download an update file from the server

    The parameters for the request are the details of the image that
    the caller is running, and a flag to say if we want unstable images
    or not.

    The server is expected to return a JSON string, which is then parsed
    by the client, in order to validate it. Then it's printed out to a
    temporary file, and the filename is returned.

    If the server returns an empty string, then we return None.

    Exceptions might be raised here and there...
    """

    data = image.to_dict()
    data['want-unstable'] = want_unstable

    params = urllib.parse.urlencode(data)
    url = url + '?' + params

    with urllib.request.urlopen(url) as response:
        jsonstr = response.read()

    if not jsonstr:
        return None

    update_data = json.loads(jsonstr)
    update = Update.from_dict(update_data)

    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write(update.to_string())

    return f.name

def do_update(images_url, update_path):
    """Update the system"""

    if not images_url.endswith('/'):
        images_url += '/'

    # Set TMPDIR to /tmp
    #
    # This is a precaution, as casync makes a very heavy use of TMPDIR,
    # and uses /var/tmp by default. One issue is that we could run out
    # of inodes on /var, depending on the size and usage of the partition
    # backing /var. Another issue is that, if some unexpected failure
    # happens and casync leaves thousands of tmp files behind, we might
    # end up filling the /var partition. Using /tmp solves these two issues.

    rauc_env = os.environ.copy()
    rauc_env['TMPDIR'] = '/tmp'

    # Remount /tmp with max memory and inodes number
    #
    # This is possible as long as /tmp is backed by a tmpfs.
    # We need this precaution as casync makes a heavy use of its tmpdir.
    # It needs enough memory to store the chunks it downloads, and it
    # also needs A LOT of inodes.

    c = subprocess.run(['mount',
                        '-o', 'remount,size=100%,nr_inodes=1g',
                        '/tmp', '/tmp'],
                       stderr=subprocess.STDOUT,
                       stdout=subprocess.PIPE,
                       universal_newlines=True)

    if c.returncode != 0:
        log.warning("Failed to remount /tmp: {}: {}".format(c.returncode, c.stdout))
        # Let's keep going and hope that /tmp can handle the load

    # Let's update now

    url = urllib.parse.urljoin(images_url, update_path)

    log.info("Installing update from {}".format(url))

    with subprocess.Popen(['rauc', 'install', url],
                          env=rauc_env,
                          stderr=subprocess.STDOUT,
                          stdout=subprocess.PIPE,
                          universal_newlines=True) as p:
        for line in p.stdout:
            print(line, end='')

    if p.returncode != 0:
        raise RuntimeError("Failed to install bundle: {}: {}".format(p.returncode, p.stdout))



class UpdateClient:

    def __init__(self):
        pass

    def run(self):

        # Arguments

        parser = argparse.ArgumentParser(
            description = "SteamOS Update Client")
        parser.add_argument('-c', '--config',
            metavar='FILE', default=DEFAULT_CONFIG_FILE,
            help="configuration file (default: {})".format(DEFAULT_CONFIG_FILE))
        parser.add_argument('-d', '--debug', action='store_true',
            help="show debug messages")
        parser.add_argument('--query-only', action='store_true',
            help="only query if an update is available")
        parser.add_argument('--mk-manifest-file', action='store_true',
            help="don't use existing manifest file, make one instead")
        parser.add_argument('--update-file',
            help="update from given file, instead of downloading it from server")

        if len(sys.argv) < 2:
            sys.argv.append('-h')

        args = parser.parse_args()

        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)

        # Config file

        log.debug("Parsing config from file: {}".format(args.config))

        config = configparser.ConfigParser()

        config.read_dict({
            'Host': {
                'Manifest': DEFAULT_MANIFEST,
                'RuntimeDir': DEFAULT_RUNTIME_DIR,
                'WantUnstable': DEFAULT_WANT_UNSTABLE,
            }})

        with open(args.config, 'r') as f:
            config.read_file(f)

        assert config['Server']['QueryUrl']
        assert config['Server']['ImagesUrl']

        # Create runtime dir

        runtime_dir = config['Host']['RuntimeDir']
        if not os.path.isdir(runtime_dir):
            log.debug("Creating runtime dir {}".format(runtime_dir))
            os.makedirs(runtime_dir)

        # Download update file, unless one is given in args

        if args.update_file:
            update_file = args.update_file
        else:
            update_file = os.path.join(runtime_dir, UPDATE_FILENAME)

            # Get details about the current image
            if args.mk_manifest_file:
                log.debug("Getting image from current OS")
                image = Image.from_os()
            else:
                manifest_file = config['Host']['Manifest']
                log.debug("Getting image from manifest: {}".format(manifest_file))
                manifest = Manifest.from_file(manifest_file)
                image = manifest.image

            # Download the update file to a tmp file
            url = config['Server']['QueryUrl']
            want_unstable = config['Host'].getboolean('WantUnstable')
            try:
                log.debug("Downloading update file (want-unstable={}): {}".format(want_unstable, url))
                tmpfile = download_update_file(url, image, want_unstable)
            except Exception as e:
                log.error("Failed to download update file: {}".format(e))
                return -1

            # Handle the result
            if tmpfile:
                log.info("Server returned something, guess an update is available")
                shutil.move(tmpfile, update_file)
            else:
                log.info("Server returned nothing, guess we're up to date")
                if os.path.exists(update_file):
                    os.remove(update_file)
                return 0

        # Parse update file

        log.debug("Parsing update file: {}".format(update_file))

        with open(update_file, 'r') as f:
            update_data = json.load(f)

        update = Update.from_dict(update_data)

        if not update:
            log.debug("No update candidate, even though the server returned something")
            log.debug("This is very unexpected, please inspect '{}'".format(update_file))
            return -1

        # Log a bit

        def log_update(upd):
            log.debug("An update is available for release '{}'".format(upd.release))
            n_imgs = len(upd.candidates)
            if n_imgs > 0:
                cand = upd.candidates[0]
                img = cand.image
                log.debug("> going to version: {} ({})".format(img.version, img.buildid))
                log.debug("> update path: {}".format(cand.update_path))
            if n_imgs > 1:
                cand = upd.candidates[-1]
                img = cand.image
                log.debug("> final destination: {} ({})".format(img.version, img.buildid))
                log.debug("> total number of updates: {}".format(n_imgs))

        if update.minor:
            log_update(update.minor)

        if update.major:
            log_update(update.major)

        # Bail out if needed

        if args.query_only:
            log.info("Running with 'query-only', we're out")
            return 0

        # Apply update

        # TODO We probably want to check that the current release matches
        #      our current release, just as a safety check
        # TODO If we're supposed to run unattended, should we validate that?
        #      (like, there should be no X/Wayland or something)
        # TODO Should we check that the versions proposed by the server are
        #      above our own version, or should we trust the server blindly?

        if update.major:
            upd = update.major
        elif update.minor:
            upd = update.minor

        assert upd

        log.debug("Applying update NOW")

        images_url = config['Server']['ImagesUrl']
        update_path = upd.candidates[0].update_path
        try:
            do_update(images_url, update_path)
        except Exception as e:
            log.error("Failed to install update file: {}".format(e))
            return -1

        # Return 1 as we performed an update
        return 1



def main():
    client = UpdateClient()
    exit_code = client.run()
    sys.exit(exit_code)
