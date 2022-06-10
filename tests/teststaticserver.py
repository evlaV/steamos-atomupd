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

import logging
import os
import shutil
from dataclasses import dataclass
import subprocess
import sys
import unittest
from difflib import ndiff
from pathlib import Path
from typing import Union
from unittest.mock import patch

CONFIG_PARENT = Path('./examples')
EXPECTATION_PARENT = Path('./tests')
META_OUTPUT_DIR = Path('steamos')

# Always add cwd to the sys path
sys.path.insert(1, os.getcwd())


@dataclass
class ServerData:
    msg: str
    config: str
    expectation: str
    mock_leftovers: Union[Path, None] = None
    mock_ndiff: Union[Path, None] = None
    replaced_leftovers: bool = False
    unchanged_lefovers: bool = False


server_data = [
    ServerData(
        msg='Static server with release images',
        config='server-releases.conf',
        expectation='staticexpected',
        mock_leftovers=EXPECTATION_PARENT / 'staticexpected_mock_leftover',
        mock_ndiff=EXPECTATION_PARENT / 'staticexpected_mock_ndiff',
        unchanged_lefovers=True,
    ),
    ServerData(
        msg='Static server with snapshot images',
        config='server-snapshots.conf',
        expectation='staticsnapexpected',
    ),
    ServerData(
        msg='Static server with snapshot and release images',
        config='server-releases-and-snaps.conf',
        expectation='static_rel_and_snap_expected',
        mock_leftovers=EXPECTATION_PARENT / 'static_rel_and_snap_mock_leftover',
        mock_ndiff=EXPECTATION_PARENT / 'static_rel_and_snap_mock_ndiff',
        replaced_leftovers=True,
        unchanged_lefovers=True,
    ),
]


class StaticServerTestCase(unittest.TestCase):

    # Do not cut out the assertion error diff messages
    maxDiff = None

    @patch('steamosatomupd.utils.DEFAULT_RAUC_CONF', Path('./examples/rauc/system.conf'))
    def test_static_server(self):
        # First build example files
        p = subprocess.run(['./examples/build-image-hierarchy.sh'],
                           check=False,
                           stderr=subprocess.STDOUT,
                           stdout=subprocess.PIPE,
                           text=True)
        self.assertEqual(p.stdout, "Hierarchy created under 'examples-data/images'\n")
        self.assertEqual(p.returncode, 0)

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
                subprocess.run(['rm', '-fR', META_OUTPUT_DIR])

                if data.mock_leftovers:
                    shutil.copytree(data.mock_leftovers / META_OUTPUT_DIR, META_OUTPUT_DIR)

                args = ['--debug', '--config', str(CONFIG_PARENT / data.config)]
                with self.assertLogs('steamosatomupd.staticserver', level=logging.DEBUG) as lo:
                    staticserver.main(args)

                print('\n'.join(lo.output))

                replaced_files = any(line for line in lo.output if 'Replacing' in line)
                self.assertEqual(replaced_files, data.replaced_leftovers, replaced_files)

                unchanged_files = any(line.endswith('has not changed, skipping...') for line in lo.output)
                self.assertEqual(unchanged_files, data.unchanged_lefovers, unchanged_files)

                if data.mock_ndiff:
                    # Assert that the diff between the new files and the leftovers is correctly
                    # printed in output
                    output_string = ''.join(lo.output)
                    for file in data.mock_ndiff.rglob('*.json'):
                        with open(file, 'r', encoding='utf-8') as expected:
                            expected_lines = expected.readlines()
                            differences = ''.join([li.lstrip() for li in expected_lines if not li.startswith('  ')])
                            self.assertIn(differences, output_string)

                # Then compare result with expected result
                p = subprocess.run(['diff', '-rq', META_OUTPUT_DIR,
                                    str(EXPECTATION_PARENT / data.expectation / META_OUTPUT_DIR)],
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
