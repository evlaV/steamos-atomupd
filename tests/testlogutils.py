# SPDX-License-Identifier: LGPL-2.1+
#
# Copyright © 2018-2026 Collabora Ltd
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
import unittest

from holoatomupd.log_utils import DedupFilter


class DedupFilterTestCase(unittest.TestCase):
    log_name = 'holoatomupd.tests.dedup'

    def setUp(self):
        self.log = logging.Logger(self.log_name, level=logging.DEBUG)
        self.log.addFilter(DedupFilter())

    def test_duplicates(self):
        with self.assertLogs(self.log, level='DEBUG') as cm:
            self.log.warning('same message')
            self.log.warning('same message')
            self.log.warning('same message')
            self.log.debug('another one')
            self.log.debug('another one')

        self.assertEqual(cm.output, [
            f'WARNING:{self.log_name}:same message',
            f'DEBUG:{self.log_name}:another one',
        ])

    def test_log_levels(self):
        with self.assertLogs(self.log, level='DEBUG') as cm:
            self.log.warning('hello')
            self.log.debug('hello')
            self.log.warning('hello')

        self.assertEqual(cm.output, [
            f'WARNING:{self.log_name}:hello',
            f'DEBUG:{self.log_name}:hello',
        ])

    def test_log_with_args(self):
        with self.assertLogs(self.log, level='DEBUG') as cm:
            self.log.warning('msg %s', 1)
            self.log.warning('msg %s', 1)
            self.log.warning('msg %s', 2)

        self.assertEqual(cm.output, [
            f'WARNING:{self.log_name}:msg 1',
            f'WARNING:{self.log_name}:msg 2',
        ])


if __name__ == '__main__':
    unittest.main()
