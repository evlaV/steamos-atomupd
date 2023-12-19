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
from dataclasses import dataclass

from steamosatomupd.image import Image

imgdata = {
    'product': 'steamos',
    'release': 'clockwerk',
    'variant': 'steamdeck',
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
        d1['version'] = '3.0'
        d2['buildid'] = '20190214.0'
        d2['version'] = '3.0'
        self.assertTrue(Image.from_dict(d1) == Image.from_dict(d2))
        self.assertTrue(Image.from_dict(d1) <= Image.from_dict(d2))
        self.assertTrue(Image.from_dict(d1) >= Image.from_dict(d2))

        d2['version'] = 'snapshot'
        self.assertTrue(Image.from_dict(d1) == Image.from_dict(d2))
        self.assertTrue(Image.from_dict(d1) <= Image.from_dict(d2))
        self.assertTrue(Image.from_dict(d1) >= Image.from_dict(d2))

        d1['buildid'] = '20190214'
        d2['buildid'] = '20190214.1'
        d2['version'] = '3.0'
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

    def test_flask_args(self):
        d = dict(imgdata)

        # When the old dynamic server builds an image from the request parameters,
        # everything is a string.
        d['checkpoint'] = 'False'
        d['introduces_checkpoint'] = '0'
        d['requires_checkpoint'] = '1'
        d['shadow_checkpoint'] = 'false'
        d['estimated_size'] = '0'
        d['skip'] = 'True'

        image = Image.from_dict(d)
        self.assertEqual(image.introduces_checkpoint, 0)
        self.assertEqual(image.requires_checkpoint, 1)
        self.assertFalse(image.shadow_checkpoint)
        self.assertEqual(image.estimated_size, 0)
        self.assertTrue(image.skip)

    def test_manifest_args(self):
        d = dict(imgdata)

        d['checkpoint'] = False
        d['introduces_checkpoint'] = 2
        d['requires_checkpoint'] = 1
        d['shadow_checkpoint'] = True
        d['estimated_size'] = 12312345
        d['skip'] = False

        image = Image.from_dict(d)
        self.assertEqual(image.introduces_checkpoint, 2)
        self.assertEqual(image.requires_checkpoint, 1)
        self.assertTrue(image.shadow_checkpoint)
        self.assertEqual(image.estimated_size, 12312345)
        self.assertFalse(image.skip)


@dataclass
class ImageData:
    variant: str
    version: str
    buildid: str
    product: str = 'steamos'
    release: str = 'holo'
    arch: str = 'amd64'
    introduces_checkpoint: int = 0
    requires_checkpoint: int = 0
    shadow_checkpoint: bool = False
    skip: bool = False


@dataclass
class ImageStatus:
    image_data: ImageData
    update_path: str
    generic_update_path: str
    is_checkpoint: bool = False
    image_checkpoint: int = 0


image_status = [
    ImageStatus(
        image_data=ImageData(
            variant='steamdeck',
            version='3.6.4',
            buildid='20231201.1',
        ),
        update_path='steamos/amd64/3.6.4/steamdeck/20231201.1.json',
        generic_update_path='steamos/amd64/3.6.4/steamdeck.json',
    ),

    ImageStatus(
        image_data=ImageData(
            variant='steamdeck-beta',
            version='snapshot',
            buildid='20231002.100',
        ),
        update_path='steamos/amd64/snapshot/steamdeck-beta/20231002.100.json',
        generic_update_path='steamos/amd64/snapshot/steamdeck-beta.json',
    ),

    ImageStatus(
        image_data=ImageData(
            variant='steamdeck-main',
            version='3.7.1',
            buildid='20231205.1000',
            introduces_checkpoint=1,
            requires_checkpoint=0,
        ),
        update_path='steamos/amd64/3.7.1/steamdeck-main/20231205.1000.json',
        generic_update_path='steamos/amd64/3.7.1/steamdeck-main.cp1.json',
        is_checkpoint=True,
        image_checkpoint=1,
    ),

    ImageStatus(
        image_data=ImageData(
            variant='steamdeck-main',
            version='3.7.2',
            buildid='20231205.1001',
            introduces_checkpoint=0,
            requires_checkpoint=1,
        ),
        update_path='steamos/amd64/3.7.2/steamdeck-main/20231205.1001.json',
        generic_update_path='steamos/amd64/3.7.2/steamdeck-main.cp1.json',
        image_checkpoint=1,
    ),

    ImageStatus(
        image_data=ImageData(
            variant='steamdeck-main',
            version='3.7.5',
            buildid='20231206.1005',
            introduces_checkpoint=2,
            requires_checkpoint=1,
        ),
        update_path='steamos/amd64/3.7.5/steamdeck-main/20231206.1005.json',
        generic_update_path='steamos/amd64/3.7.5/steamdeck-main.cp2.json',
        is_checkpoint=True,
        image_checkpoint=2,
    ),
]


class ImageMethods(unittest.TestCase):
    def test_image_methods(self):
        for data in image_status:
            with self.subTest(msg=data.image_data.buildid):
                i_d = data.image_data
                image = Image.from_values(product=i_d.product, release=i_d.release, variant=i_d.variant, branch='',
                                          arch=i_d.arch, version_str=i_d.version, buildid_str=i_d.buildid,
                                          introduces_checkpoint=i_d.introduces_checkpoint,
                                          requires_checkpoint=i_d.requires_checkpoint,
                                          shadow_checkpoint=i_d.shadow_checkpoint, estimated_size=0, skip=i_d.skip)

                self.assertEqual(i_d.version, image.get_version_str())
                self.assertEqual(data.update_path, image.get_update_path())
                self.assertEqual(data.generic_update_path, image.get_update_path(fallback=True))
                self.assertEqual(data.is_checkpoint, image.is_checkpoint())
                self.assertEqual(data.image_checkpoint, image.get_image_checkpoint())


if __name__ == '__main__':
    unittest.main()
