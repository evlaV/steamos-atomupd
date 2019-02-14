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

from steamosupdate.image import Image
from steamosupdate.imagepool import _get_update_candidates
from steamosupdate.update import UpdateCandidate

imgdata = {
    'product': 'steamos',
    'release': 'clockwerk',
    'variant': 'xyz',
    'arch'   : 'amd64',
    'version': 'SET-ME',
    'buildid': '20190214',
}

def mk_image(imgdata):
    return Image.from_dict(imgdata)

def mk_update_candidate(imgdata):
    return UpdateCandidate(Image.from_dict(imgdata),
                           'random-string-supposed-to-be-an-update-path')

class GetUpdateCandidatesTestCase(unittest.TestCase):

    def test_get_update_candidates(self):
        d  = dict(imgdata)
        d1 = dict(imgdata)
        d2 = dict(imgdata)
        d3 = dict(imgdata)

        d['version']  = '2.0'
        d1['version'] = '2.0'
        d2['version'] = '2.1'
        d3['version'] = '2.2'

        i  = mk_image(d)
        c1 = mk_update_candidate(d1)
        c2 = mk_update_candidate(d2)
        c3 = mk_update_candidate(d3)

        # only the last image is an update candidate
        res =_get_update_candidates([ c1, c2, c3 ], i, False)
        self.assertTrue(res == [ c3 ])

        # checkpoint + last image
        d2['checkpoint'] = True
        c2 = mk_update_candidate(d2)
        res =_get_update_candidates([ c1, c2, c3 ], i, False)
        self.assertTrue(res == [ c2, c3 ])

        # checkpoint + last image (no change)
        d1['checkpoint'] = True
        c1 = mk_update_candidate(d1)
        res =_get_update_candidates([ c1, c2, c3 ], i, False)
        self.assertTrue(res == [ c2, c3 ])

        # checkpoint only (as last image is unstable)
        d3['version'] = '2.2-rc1'
        c3 = mk_update_candidate(d3)
        res =_get_update_candidates([ c1, c2, c3 ], i, False)
        self.assertTrue(res == [ c2 ])

        # checkpoint only + last image (as we want unstable)
        d3['version'] = '2.2-rc1'
        c3 = mk_update_candidate(d3)
        res =_get_update_candidates([ c1, c2, c3 ], i, True)
        self.assertTrue(res == [ c2, c3 ])

        # no update candidates (already at latest)
        d['version'] = '2.2-rc1'
        i = mk_image(d)
        res =_get_update_candidates([ c1, c2, c3 ], i, True)
        self.assertTrue(res == [])

if __name__ == '__main__':
    unittest.main()
