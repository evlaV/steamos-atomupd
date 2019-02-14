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

import semantic_version
import unittest

from steamosupdate.image import Image
from steamosupdate.update import Update

oldimgdata = {
    'product': 'steamos',
    'release': 'clockwerk',
    'variant': 'rauc',
    'arch'   : 'amd64',
    'version': '3.0',      # <---
    'buildid': '20190214'
}

newimgdata = {
    'product': 'steamos',
    'release': 'clockwerk',
    'variant': 'rauc',
    'arch'   : 'amd64',
    'version': '3.1',      # <---
    'buildid': '20190218'
}

upddata = {
    'minor': {
        'release': 'valentine',
        'candidates': [
            {
                'image': newimgdata,
                'update_path': 'some-path',
            }, {
                'image': oldimgdata,
                'update_path': 'some-path',
            }
        ]
    }
}

class UpdateTestCase(unittest.TestCase):

    def test_candidates_sorted(self):
        d = dict(upddata)

        # The update data MIGHT contain an UNSORTED array of update candidates.
        # We made sure in the declaration above that it's indeed unsorted.
        candidates = d['minor']['candidates']
        v1str = candidates[0]['image']['version']
        v2str = candidates[1]['image']['version']
        v1 = semantic_version.Version.coerce(v1str)
        v2 = semantic_version.Version.coerce(v2str)
        self.assertTrue(v1 > v2)

        # An update object MUST contain a SORTED array of update candidates.
        update = Update.from_dict(d)
        candidates = update.minor.candidates
        self.assertTrue(sorted(candidates, key=lambda c: c.image) == candidates)
        self.assertTrue(candidates[0].image < candidates[1].image)

if __name__ == '__main__':
    unittest.main()
