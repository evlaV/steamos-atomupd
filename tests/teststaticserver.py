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
from subprocess import run
import sys
import time
import unittest

# Always add cwd to the sys path
sys.path.insert(1, os.getcwd())

class StaticServerTestCase(unittest.TestCase):

    def test_static_server(self):
        # First build example files
        p = run(['./examples/build-image-hierarchy.sh'])

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

        # Then run staticserver with example file
        args = ["--config", "./examples/server-releases.conf"]
        staticserver.main(args)

        # time.sleep(1)
        
        # Then compare result with expected result
        p = run(['diff', '-rq', './steamos', './tests/staticexpected/steamos'])
        
        self.assertTrue(p.returncode == 0)

if __name__ == '__main__':
    # Run static server on test config
    # Compare output with expected results
    unittest.main()
