# SPDX-License-Identifier: LGPL-2.1+
#
# Copyright © 2022 Collabora Ltd
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

import os
from dataclasses import dataclass
import subprocess
import sys
import unittest
from pathlib import Path

CONFIG_PARENT = Path('./examples')
EXPECTATION_PARENT = Path('./tests')
EXPECTATION_SUB_DIR = Path('steamos')

# Always add cwd to the sys path
sys.path.insert(1, os.getcwd())


@dataclass
class ServerData:
    msg: str
    config: str
    expectation: str


server_data = [
    ServerData(
        msg='Static server with release images',
        config='server-releases.conf',
        expectation='staticexpected',
    ),
    ServerData(
        msg='Static server with snapshot images',
        config='server-snapshots.conf',
        expectation='staticsnapexpected',
    ),
]


class StaticServerTestCase(unittest.TestCase):

    # Do not cut out the assertion error diff messages
    maxDiff = None

    def test_static_server(self):
        # First build example files
        p = subprocess.run(['./examples/build-image-hierarchy.sh'],
                           check=False,
                           stderr=subprocess.STDOUT,
                           stdout=subprocess.PIPE,
                           text=True)
        self.assertEqual(p.stdout, "Hierarchy created under 'examples-data/images'\n")
        self.assertEqual(p.returncode, 0)

        # First import staticserver
        try:
            from steamosatomupd import staticserver
        except ModuleNotFoundError as e:
            print('\n'.join([
              "Module not found: {}.".format(e),
              "If you're running from the source tree, set the",
              "environment variable IN_SOURCE_TREE and try again.",
            ]), file=sys.stderr)
            sys.exit(1)

        for data in server_data:
            with self.subTest(msg=data.msg):
                subprocess.run(['rm', '-fR', './steamos'])
                args = ['--config', str(CONFIG_PARENT / data.config)]
                staticserver.main(args)

                # Then compare result with expected result
                p = subprocess.run(['diff', '-rq', './steamos',
                                    str(EXPECTATION_PARENT / data.expectation / EXPECTATION_SUB_DIR)],
                                   check=False,
                                   stderr=subprocess.STDOUT,
                                   stdout=subprocess.PIPE,
                                   text=True)
                self.assertEqual(p.stdout, '')
                self.assertEqual(p.returncode, 0)


if __name__ == '__main__':
    # Run static server on test config
    # Compare output with expected results
    unittest.main()
