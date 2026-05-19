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

import json
import logging
import tempfile
import unittest
from collections import defaultdict
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path

from holoatomupd.image import Image
from holoatomupd.imagepool import ImagePool, _get_chunks_store_path, _get_update_candidates
from holoatomupd.update import UpdateCandidate, UpdateType
from tests.createmanifests import build_image_hierarchy

imgdata = {
    'product': 'steamos',
    'release': 'clockwerk',
    'variant': 'steamdeck',
    'arch'   : 'amd64',
    'version': 'SET-ME',
    'buildid': '20190214',
}

def mk_image(imgdata):
    return Image.from_dict(imgdata)

def mk_update_candidate(imgdata):
    return UpdateCandidate(Image.from_dict(imgdata),
                           'random-string-supposed-to-be-an-update-path', 'chunks_path')

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
        res = _get_update_candidates([ c1, c2, c3 ], i, UpdateType.standard, defaultdict(list))
        self.assertTrue(res == [ c3 ])

        # checkpoint + last image
        d2['introduces_checkpoint'] = 1
        d2['requires_checkpoint'] = 0
        d3['requires_checkpoint'] = 1
        c2 = mk_update_candidate(d2)
        c3 = mk_update_candidate(d3)
        res = _get_update_candidates([ c1, c2, c3 ], i, UpdateType.standard, defaultdict(list))
        self.assertTrue(res == [ c2, c3 ])

        # no update candidates (already at latest)
        d['version'] = '2.2'
        d['requires_checkpoint'] = 1
        i = mk_image(d)
        res = _get_update_candidates([ c1, c2, c3 ], i, UpdateType.standard, defaultdict(list))
        self.assertTrue(res == [])

class MalformedImagesTestCase(unittest.TestCase):

    malformed_image = Path('releases/steamdeck/20220411.1/steamdeck-20220411.1-3.2')

    def setUp(self):
        images = tempfile.TemporaryDirectory()
        self.addCleanup(images.cleanup)
        self.images_dir = Path(images.name)
        build_image_hierarchy(self.images_dir)

    def _create_pool(self):
        config = ConfigParser()
        config['Images'] = {
            'PoolDir': str(self.images_dir / 'releases'),
            'Product': 'steamos',
            'Release': 'holo',
            'Variants': 'steamdeck steamdeck-rc steamdeck-beta',
            'Branches': 'stable rc beta',
            'Archs': 'amd64',
        }
        return ImagePool(config)

    @staticmethod
    def _get_buildids(pool):
        return [str(candidate.image.buildid) for candidate in pool.image_updates_found]

    def test_missing_rauc_bundle(self):
        # An image manifest without its RAUC bundle
        (self.images_dir / f'{self.malformed_image}.raucb').unlink()

        with self.assertLogs('holoatomupd.imagepool', level=logging.WARNING) as lo:
            pool = self._create_pool()

        self.assertTrue(any(f'{self.malformed_image.name}.manifest.json' in line and 'malformed' in line
                            for line in lo.output), lo.output)

        buildids = self._get_buildids(pool)
        self.assertNotIn('20220411.1', buildids)
        self.assertIn('20220401.1', buildids)

    def test_missing_manifest(self):
        # A RAUC bundle without its image manifest, it should be simply skipped
        (self.images_dir / f'{self.malformed_image}.manifest.json').unlink()

        with self.assertNoLogs('holoatomupd.imagepool', level=logging.WARNING):
            pool = self._create_pool()

        buildids = self._get_buildids(pool)
        self.assertNotIn('20220411.1', buildids)
        self.assertIn('20220401.1', buildids)

    def test_malformed_manifest(self):
        # An image manifest that is missing a required field
        image_manifest = self.images_dir / f'{self.malformed_image}.manifest.json'

        manifest_data = json.loads(image_manifest.read_text())
        manifest_data.pop("arch")
        image_manifest.write_text(json.dumps(manifest_data))

        with self.assertLogs('holoatomupd.imagepool', level=logging.WARNING) as lo:
            pool = self._create_pool()

        self.assertTrue(any(f'{self.malformed_image.name}.manifest.json' in line and 'Failed to create' in line
                            for line in lo.output), lo.output)

        buildids = self._get_buildids(pool)
        self.assertNotIn('20220411.1', buildids)
        self.assertIn('20220401.1', buildids)


@dataclass
class FileSpec:
    path: str
    is_dir: bool = False
    symlink_to: str | None = None

@dataclass
class ChunksStoreData:
    msg: str
    files: list[FileSpec]
    manifest: str
    expected_store_path: str = ""
    expected_value_error: bool = False

def create_files(root: Path, specs: list[FileSpec]) -> None:
    for spec in specs:
        full_path = root / spec.path
        if spec.symlink_to is not None:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.symlink_to(spec.symlink_to)
        elif spec.is_dir:
            full_path.mkdir(parents=True, exist_ok=True)
        else:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text("")

chunks_store_data = [
    ChunksStoreData(
        msg="Store next to the image, and one in the parent directory",
        files=[
            FileSpec("store.castr", is_dir=True),
            FileSpec("20260519.1000/steamdeck-20260519.1000.castr", is_dir=True),
            FileSpec("20260519.1000/steamdeck-20260519.1000.manifest.json"),
        ],
        manifest="20260519.1000/steamdeck-20260519.1000.manifest.json",
        expected_store_path="20260519.1000/steamdeck-20260519.1000.castr",
    ),

    ChunksStoreData(
        msg="Store only in the parent directory",
        files=[
            FileSpec("store.castr", is_dir=True),
            FileSpec("20260519.1000/steamdeck-20260519.1000.manifest.json"),
        ],
        manifest="20260519.1000/steamdeck-20260519.1000.manifest.json",
        expected_store_path="store.castr",
    ),

    ChunksStoreData(
        msg="Store with symlink",
        files=[
            FileSpec("store.castr", is_dir=True),
            FileSpec("20260519.1000/steamdeck-20260519.1000.castr", symlink_to="../store.castr"),
            FileSpec("20260519.1000/steamdeck-20260519.1000.manifest.json"),
        ],
        manifest="20260519.1000/steamdeck-20260519.1000.manifest.json",
        expected_store_path="store.castr",
    ),

    ChunksStoreData(
        msg="Missing store",
        files=[
            FileSpec("wrong_store", is_dir=True),
            FileSpec("20260519.1000/steamdeck-20260519.1000.manifest.json"),
        ],
        manifest="20260519.1000/steamdeck-20260519.1000.manifest.json",
        expected_value_error=True,
    ),

    ChunksStoreData(
        msg="Multiple stores",
        files=[
            FileSpec("store.castr", is_dir=True),
            FileSpec("20260519.1000/steamdeck-20260519.1000.castr", symlink_to="../store.castr"),
            FileSpec("20260519.1000/steamdeck-20260519.1000_v2.castr", symlink_to="../store.castr"),
            FileSpec("20260519.1000/steamdeck-20260519.1000.manifest.json"),
        ],
        manifest="20260519.1000/steamdeck-20260519.1000.manifest.json",
        expected_value_error=True,
    ),

    ChunksStoreData(
        msg="Store in two directories up",
        files=[
            FileSpec("store.castr", is_dir=True),
            FileSpec("3.10/20260519.1000/steamdeck-20260519.1000.manifest.json"),
        ],
        manifest="3.10/20260519.1000/steamdeck-20260519.1000.manifest.json",
        expected_store_path="store.castr",
    ),
]


class GetChunksStorePathTestCase(unittest.TestCase):
    def test_chunks_store_path(self):
        for data in chunks_store_data:
            with self.subTest(msg=data.msg), tempfile.TemporaryDirectory() as images_dir:
                create_files(Path(images_dir), data.files)

                if data.expected_value_error:
                    with self.assertRaises(ValueError):
                        _get_chunks_store_path(images_dir, str(Path(images_dir) / data.manifest))
                else:
                    result = _get_chunks_store_path(images_dir, str(Path(images_dir) / data.manifest))
                    self.assertEqual(result, data.expected_store_path)

    def test_chunks_store_outside_images_dir(self):
        # Store with symlink pointing outside the images directory

        files = [
            FileSpec("store.castr", is_dir=True),
            FileSpec("images/store.castr", is_dir=True),
            FileSpec("images/20260519.1000/steamdeck-20260519.1000.castr", symlink_to="../../store.castr"),
            FileSpec("images/20260519.1000/steamdeck-20260519.1000.manifest.json"),
        ]

        with tempfile.TemporaryDirectory() as root_dir:
            create_files(Path(root_dir), files)
            images_dir = Path(root_dir) / "images"
            with self.assertRaises(ValueError):
                _get_chunks_store_path(str(images_dir),
                                       str(Path(images_dir) / "20260519.1000/steamdeck-20260519.1000.manifest.json"))



if __name__ == '__main__':
    unittest.main()
