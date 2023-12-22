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
import configparser
import io
import json
import shutil
import tempfile
import urllib.parse
from contextlib import redirect_stdout
from dataclasses import dataclass, field
import unittest
from pathlib import Path
from typing import List
from unittest.mock import patch

from steamosatomupd.image import BuildId, Image
from steamosatomupd.update import Update
from steamosatomupd import client

data_path = Path(__file__).parent.resolve() / 'client_data'
rauc_conf_dir = Path(__file__).parent.resolve() / 'rauc_conf_dir'


@dataclass
class UpdateData:
    msg: str
    update_file: Path
    config: Path = data_path / 'client.conf'
    manifest: Path = data_path / '20211225_manifest.json'
    minor_updates: List[BuildId] = field(default_factory=list)
    major_updates: List[BuildId] = field(default_factory=list)
    return_code: int = 0
    impossible_update: bool = False


update_data = [
    UpdateData(
        msg='No updates',
        update_file=data_path / 'update_empty.json',
    ),
    UpdateData(
        msg='Non fixable update loop',
        update_file=data_path / 'update_loop.json',
        impossible_update=True,
    ),
    UpdateData(
        msg='One major update',
        update_file=data_path / 'update_one_major.json',
        major_updates=[BuildId.from_string('20220307.5')],
    ),
    UpdateData(
        msg='One minor update',
        update_file=data_path / 'update_one_minor.json',
        minor_updates=[BuildId.from_string('20220227.3')],
    ),
    UpdateData(
        msg='One minor and one major update',
        update_file=data_path / 'update_one_minor_one_major.json',
        minor_updates=[BuildId.from_string('20220120.1')],
        major_updates=[BuildId.from_string('20220202.1')],
    ),
    UpdateData(
        msg='Update to the same version',
        update_file=data_path / 'update_same_version.json',
    ),
    UpdateData(
        msg='Update to the same version for both minor and major',
        update_file=data_path / 'update_same_version_minor_and_major.json',
    ),
    UpdateData(
        msg='Three minor updates, the first if for the same version',
        update_file=data_path / 'update_three_minors.json',
        minor_updates=[
            BuildId.from_string('20220101.1'),
            BuildId.from_string('20220227.3'),
        ],
    ),
    UpdateData(
        msg='Same version update plus another minor updates',
        update_file=data_path / 'update_two_minors.json',
        minor_updates=[BuildId.from_string('20220227.3')],
    )
]


class LoopPrevention(unittest.TestCase):
    @patch('steamosatomupd.client.set_rauc_conf')
    @patch('os.geteuid')
    def test_updates(self, geteuid, set_rauc_conf):
        for data in update_data:
            with self.subTest(msg=data.msg):
                geteuid.return_value = 0
                set_rauc_conf.return_value = None

                # Create a tmp copy of the update file because, before
                # returning, the client main will delete the file
                tmp = tempfile.NamedTemporaryFile(delete=False)
                shutil.copy2(data.update_file, tmp.name)

                args = [
                    '--config', str(data.config),
                    '--manifest-file', str(data.manifest),
                    '--update-file', tmp.name,
                    '--query-only',
                ]

                if data.impossible_update:
                    with self.assertRaises(ValueError):
                        client.main(args)
                    continue

                f = io.StringIO()
                with redirect_stdout(f), self.assertRaises(SystemExit) as se:
                    client.main(args)
                self.assertEqual(data.return_code, se.exception.code)
                out = f.getvalue()

                if not out:
                    self.assertFalse(data.minor_updates)
                    self.assertFalse(data.major_updates)
                    continue

                update_json = json.loads(out)
                self.assertIsNotNone(update_json)

                update = Update.from_dict(update_json)

                candidates = update.minor.candidates if update.minor else []
                self.assertEqual(len(data.minor_updates), len(candidates))
                for i, c in enumerate(candidates):
                    self.assertEqual(data.minor_updates[i], c.image.buildid)

                candidates = update.major.candidates if update.major else []
                self.assertEqual(len(data.major_updates), len(candidates))
                for i, c in enumerate(candidates):
                    self.assertEqual(data.major_updates[i], c.image.buildid)


@dataclass
class RaucConfData:
    msg: str
    rauc_config: Path
    seed_index: Path = Path()
    desync_in_use: bool = False
    config_error: bool = False


rauc_conf_data = [
    RaucConfData(
        msg='Using Casync',
        rauc_config=rauc_conf_dir / 'casync.conf',
    ),
    RaucConfData(
        msg='Using Desync',
        rauc_config=rauc_conf_dir / 'desync.conf',
        seed_index=Path('/var/lib/steamos-atomupd/rootfs.caibx'),
        desync_in_use=True,
    ),
    RaucConfData(
        msg='Using Desync with seed option not at the beginning',
        rauc_config=rauc_conf_dir / 'desync_reordered.conf',
        seed_index=Path('/var/lib/steamos-atomupd/rootfs.caibx'),
        desync_in_use=True,
    ),
    RaucConfData(
        msg='Using Desync without seed',
        rauc_config=rauc_conf_dir / 'desync_without_seed.conf',
        desync_in_use=True,
        config_error=True,
    ),
    RaucConfData(
        msg='Missing Casync entry',
        rauc_config=rauc_conf_dir / 'missing_casync_entry.conf',
    ),
]


class RaucConfigParsing(unittest.TestCase):
    @patch('steamosatomupd.client.get_rauc_config')
    @patch('steamosatomupd.client.set_rauc_conf')
    @patch('os.geteuid')
    def test_parsing_rauc_conf(self, geteuid, set_rauc_conf, get_rauc_config):
        for data in rauc_conf_data:
            with self.subTest(msg=data.msg):
                geteuid.return_value = 0
                # Instead of the hard-coded '/etc/rauc/system.conf', we patch
                # get_rauc_config() to use the config specified in the tests
                config = configparser.ConfigParser()
                config.read(data.rauc_config)
                get_rauc_config.return_value = config
                set_rauc_conf.return_value = None

                client.parse_rauc_install_args.cache_clear()
                client.is_desync_in_use.cache_clear()
                client.get_active_slot_index.cache_clear()

                self.assertEqual(client.is_desync_in_use(), data.desync_in_use)

                if data.config_error or not data.desync_in_use:
                    with self.assertRaises(RuntimeError):
                        client.get_active_slot_index()
                else:
                    self.assertEqual(client.get_active_slot_index(), data.seed_index)


progress_data = {
    # The expected usual progress output
    "Attempt 1: Validating   13.40% 00m06s": "0.67%",
    "Attempt 1: Validating   35.55% 00m04s": "1.78%",
    "Attempt 1: Validating   100.00% 6s": "5.00%",
    "Attempt 1: Assembling   4.00% 01m33s": "8.80% 01m33s",
    "Attempt 1: Assembling   34.22% 01m02s": "37.51% 01m02s",
    "Attempt 1: Assembling   85.45% 00m13s": "86.18% 00m13s",
    "Attempt 1: Assembling   100.00% 01m38s": "100.00%",

    # This is instead the output when the seed is invalid
    "Attempt 1: Validating   22.44% 00m05s": "1.12%",
    "Attempt 1: Chunking Seed 1   0.00%": "5.00%",
    "Attempt 1: Chunking Seed 1   10.20% 00m15s": "5.51%",
    "Attempt 1: Chunking Seed 1   100.00% 12s": "10.00%",
    "Attempt 2: Validating   19.38% 00m05s": "10.97%",
    "Attempt 2: Validating   100.00% 4s": "15.00%",
    "Attempt 2: Assembling   7.00% 01m29s": "20.95% 01m29s",
    "Attempt 2: Assembling   30.22% 01m02s": "40.69% 01m02s",
    "Attempt 2: Assembling   75.45% 00m13s": "79.13% 00m13s",
    "Attempt 2: Assembling   97.88% 00m01s": "98.20% 00m01s",
    "Attempt 2: Assembling   100.00% 01m30s": "100.00%",
}


class RaucProgressParsing(unittest.TestCase):
    def test_parsing_rauc_desync_progress(self):
        for line, parsed in progress_data.items():
            with redirect_stdout(io.StringIO()) as f:
                client.parse_desync_progress(line)
            self.assertEqual(f.getvalue().strip(), parsed)


@dataclass
class DownloadUpdateData:
    msg: str
    image_data: dict[str, str]
    meta_attempts: int = 1
    # These are the production server that we use for Jupiter
    meta_url: str = 'https://steamdeck-atomupd.steamos.cloud/meta'
    query_url: str = 'https://steamdeck-atomupd.steamos.cloud/updates'


download_update_data = [
    DownloadUpdateData(
        msg="Known valid image",
        image_data={
            'product': 'steamos',
            'release': 'holo',
            'variant': 'steamdeck',
            'arch': 'amd64',
            'version': '3.5.5',
            'buildid': '20231116.2',
            'checkpoint': 'false',
            'estimated_size': '0',
        },
    ),

    DownloadUpdateData(
        msg="Unknown image",
        # The first URL should return 404, and the generic fallback should succeed
        meta_attempts=2,
        image_data={
            'product': 'steamos',
            'release': 'holo',
            'variant': 'steamdeck',
            'arch': 'amd64',
            'version': '3.5.0',
            'buildid': '20000101.9000',
            'checkpoint': 'false',
            'estimated_size': '0',
        },
    ),
]


class DownloadUpdateJSON(unittest.TestCase):
    def test_update_request(self):
        for data in download_update_data:
            with self.subTest(msg=data.msg):
                image = Image.from_dict(data.image_data)

                with self.assertLogs(level='DEBUG') as lo:
                    meta_update_file = client.download_update_from_rest_url(data.meta_url, image)

                self.assertTrue(meta_update_file)
                attempts = sum('Trying URL' in line for line in lo.output)

                self.assertEqual(attempts, data.meta_attempts)

                with open(meta_update_file, 'r', encoding='utf-8') as f:
                    update_json = json.load(f)

                self.assertTrue(update_json)
                self.assertTrue(Update.from_dict(update_json))


if __name__ == '__main__':
    unittest.main()
