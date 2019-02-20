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

import unittest

from steamosatomupd.image import Image

imgdata = {
    'product': 'steamos',
    'release': 'clockwerk',
    'variant': 'rauc',
    'arch'   : 'amd64',
    'version': 'snapshot',
    'buildid': '20180214',
    'checkpoint': False,
}

class BuildIdTestCase(unittest.TestCase):

    def test_invalid_buildids(self):
        d = dict(imgdata)

        d['buildid'] = 'INVALID-BUILD-ID'
        with self.assertRaises(ValueError):
            i = Image.from_dict(d)

        d['buildid'] = '20189999'
        with self.assertRaises(ValueError):
            i = Image.from_dict(d)

        d['buildid'] = '20180214.-6'
        with self.assertRaises(ValueError):
            i = Image.from_dict(d)

        d['buildid'] = '20180214.12.34'
        with self.assertRaises(ValueError):
            i = Image.from_dict(d)

    def test_buildid_comparisons(self):
        d1 = dict(imgdata)
        d2 = dict(imgdata)

        d1['buildid'] = '20190214'
        d2['buildid'] = '20190214.0'
        self.assertTrue(Image.from_dict(d1) == Image.from_dict(d2))
        self.assertTrue(Image.from_dict(d1) <= Image.from_dict(d2))
        self.assertTrue(Image.from_dict(d1) >= Image.from_dict(d2))

        d1['buildid'] = '20190214'
        d2['buildid'] = '20190214.1'
        self.assertTrue(Image.from_dict(d1) != Image.from_dict(d2))
        self.assertTrue(Image.from_dict(d1) <  Image.from_dict(d2))
        self.assertTrue(Image.from_dict(d2) >  Image.from_dict(d1))

        d1['buildid'] = '20190214'
        d2['buildid'] = '20190215'
        self.assertTrue(Image.from_dict(d1) != Image.from_dict(d2))
        self.assertTrue(Image.from_dict(d1) <  Image.from_dict(d2))
        self.assertTrue(Image.from_dict(d2) >  Image.from_dict(d1))

class VersionTestCase(unittest.TestCase):

    def test_valid_versions(self):
        d = dict(imgdata)

        d['version'] = 'snapshot'
        Image.from_dict(d)

        d['version'] = '3'
        Image.from_dict(d)

        d['version'] = '3.0'
        Image.from_dict(d)

    def test_invalid_versions(self):
        d = dict(imgdata)

        d['version'] = 'valentine'
        with self.assertRaises(ValueError):
            i = Image.from_dict(d)

    def test_version_comparisons(self):
        d1 = dict(imgdata)
        d2 = dict(imgdata)

        d1['version'] = '3'
        d2['version'] = '3.0'
        self.assertTrue(Image.from_dict(d1) == Image.from_dict(d2))
        self.assertTrue(Image.from_dict(d1) <= Image.from_dict(d2))
        self.assertTrue(Image.from_dict(d1) >= Image.from_dict(d2))

        d1['version'] = '3'
        d2['version'] = '3.1'
        self.assertTrue(Image.from_dict(d1) != Image.from_dict(d2))
        self.assertTrue(Image.from_dict(d1) <  Image.from_dict(d2))
        self.assertTrue(Image.from_dict(d2) >  Image.from_dict(d1))

        d1['version'] = '4.2-rc1'
        d2['version'] = '4.2'
        self.assertTrue(Image.from_dict(d1) != Image.from_dict(d2))
        self.assertTrue(Image.from_dict(d1) <  Image.from_dict(d2))
        self.assertTrue(Image.from_dict(d2) >  Image.from_dict(d1))

class MiscTestCase(unittest.TestCase):

    def test_snaphot(self):
        d = dict(imgdata)

        d['version'] = 'snapshot'
        self.assertTrue(Image.from_dict(d).is_snapshot())

        d['version'] = '3.6'
        self.assertFalse(Image.from_dict(d).is_snapshot())

    def test_stable(self):
        d = dict(imgdata)

        d['version'] = '3.2'
        self.assertTrue(Image.from_dict(d).is_stable())

        d['version'] = '3.6-rc1'
        self.assertFalse(Image.from_dict(d).is_stable())

        d['version'] = 'snapshot'
        self.assertFalse(Image.from_dict(d).is_stable())

if __name__ == '__main__':
    unittest.main()
