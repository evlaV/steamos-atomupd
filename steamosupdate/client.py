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

# TODO implementation
# - go over TUF things, bring in the easiest bits to improve security,
#   where it makes sense

import argparse
from collections import namedtuple
import configparser
import json
import logging
import os
import shutil
import sys

import steamosupdate.manifest as mnf
import steamosupdate.version as version
import steamosupdate.updatefile as updatefile

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

def download_update_file(url, manifest, want_unstable):

    import tempfile
    import urllib.parse
    import urllib.request

    # TODO Security, either enforce https, either the file is signed
    # TODO Add hardware details to the query string?
    # TODO Should we also say if running unattended or not? Is it of
    #      any interest for the server?

    params = {
        'product': manifest.product,
        'release': manifest.release,
        'arch':    manifest.arch,
        'version': manifest.version,
        'variant': manifest.variant,
        'want-unstable': want_unstable,
    }

    query_string = urllib.parse.urlencode(params)
    url = url + '?' + query_string

    with urllib.request.urlopen(url) as response:
        with tempfile.NamedTemporaryFile(delete=False) as f:
            data = response.read()
            f.write(data)

    return f.name

def _process_release_node(node, expected_release=None):

    """Process a releasae node, which at the moment means:
    - raise errors if keys are not found
    - sort the list of releases candidates
    """

    # Ensure the release is as expected
    release = node['release']
    if expected_release and expected_release != release:
        raise ValueError("unexpected release: {}".format(release))

    # Sort release candidates (modify input!)
    candidates = node['candidates']

    def _get_candidate_version_parsed(candidate):
        return version.parse_string(candidate['version'], 'guess')

    node['candidates'] = sorted(candidates, key=_get_candidate_version_parsed)

    return node

def parse_update_file(filename, manifest):

    """Parse an update file

    We might raise key error, or json error
    """

    with open(filename, 'r') as f:
        data = json.load(f)

    # TODO We're supposed to run unattended, should we validate that?
    #      (like, there should be no X/Wayland or something)
    # TODO Should we check that the versions proposed by the server are
    #      above our own version, or should we trust the server blindly?
    # TODO Should we have a better validation of the data send by the
    #      server?

    curr_update = None
    if 'current' in data:
        try:
            curr_update = _process_release_node(data['current'],
                                                expected_release=manifest.release)
        except Exception as e:
            log.debug("Failed to process the 'current' release node: {}".format(e))


    next_update = None
    if 'next' in data:
        try:
            next_update = _process_release_node(data['next'])
        except Exception as e:
            log.debug("Failed to process 'next' update node: {}".format(e))

    return curr_update, next_update

def do_update(images_url, image_path):

    import subprocess
    import urllib.parse

    url = urllib.parse.urljoin(images_url, image_path)
    completed_process = subprocess.run(['rauc', 'status'])



class UpdateClient:

    def __init__(self):
        pass

    def run(self):

        # Arguments

        parser = argparse.ArgumentParser(
            description = "SteamOS Update Client")
        parser.add_argument('-d', '--debug', action='store_true',
            help="show debug messages")
        parser.add_argument('-c', '--config',
            metavar='FILE', default=DEFAULT_CONFIG_FILE,
            help="configuration file (default: {})".format(DEFAULT_CONFIG_FILE))
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

        # Get the current manifest file

        if args.mk_manifest_file:
            log.debug("Making manifest from current system")
            manifest = mnf.make_from_running_os()
        else:
            manifest_file = config['Host']['Manifest']
            log.debug("Using manifest: {}".format(manifest_file))
            manifest = mnf.make_from_file(manifest_file)

        # Download update file, unless one is given in args

        if args.update_file:
            update_file = args.update_file
        else:
            url = config['Server']['QueryUrl']
            want_unstable = bool(config['Host']['WantUnstable'])
            try:
                log.debug("Downloading update file (want-unstable={}): {}".format(want_unstable, url))
                tmpfile = download_update_file(url, manifest, want_unstable)
            except Exception as e:
                log.error("Failed to download update file: {}".format(e))
                return 1

            log.debug("Downloaded to tmpfile: {}".format(tmpfile))

            update_file = os.path.join(runtime_dir, UPDATE_FILENAME)

            if os.stat(tmpfile).st_size != 0:
                log.info("Server returned something, guess an update is available")
                log.debug("Renaming tmpfile to: {}".format(update_file))
                shutil.move(tmpfile, update_file)
            else:
                log.info("Server returned nothing, guess we're up to date")
                os.remove(tmpfile)
                if os.path.exists(update_file):
                    os.remove(update_file)
                return 0

        # Parse update file

        log.debug("Parsing update file: {}".format(update_file))

        try:
            minor_update, major_update = parse_update_file(update_file, manifest)
        except Exception as e:
            log.error("Failed to parse update file: {}".format(e))
            return 1

        def log_update(upd):
            log.debug("An update is available for release '{}'".format(upd['release']))
            if len(upd['candidates']) > 0:
                c = upd['candidates'][0]
                v = c['version']
                p = c['path']
                log.debug("> going to version: {}".format(v))
                log.debug("> update path: {}".format(p))
            if len(upd['candidates']) > 1:
                n = len(upd['candidates'])
                c = upd['candidates'][-1]
                v = c['version']
                log.debug("> final destination: {}".format(n))
                log.debug("> total number of updates: {}".format(n))

        if minor_update:
            log_update(minor_update)

        if major_update:
            log_update(major_update)

        if not minor_update and not major_update:
            log.debug("No update candidate found, even though the server returned something");
            log.debug("Kind of unexpected TBH")
            # Should we remove the update file then?
            return 0

        # Bail out if needed

        if args.query_only:
            log.info("Running with 'query-only', we're out")
            return 0

        # Apply update

        if major_update:
            upd = major_update
        elif minor_update:
            upd = minor_update

        assert upd

        log.debug("Applying update NOW")

        images_url = config['Server']['ImagesUrl']
        image_path = upd['candidates'][0]['path']
        if not images_url.endswith('/'):
            images_url += '/'
        do_update(images_url, image_path)

        # TODO Should we return meaningful exit codes?


def main():
    client = UpdateClient()
    exit_code = client.run()
    sys.exit(exit_code)
