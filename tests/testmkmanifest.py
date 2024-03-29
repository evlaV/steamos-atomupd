# SPDX-License-Identifier: LGPL-2.1+
#
# Copyright © 2023-2024 Collabora Ltd
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

import io
import textwrap
import unittest
from contextlib import redirect_stdout
from dataclasses import dataclass
from unittest.mock import patch, mock_open

from steamosatomupd import mkmanifest

STANDARD_ENTRIES = ('ANSI_COLOR="1;35"\n'
                    'HOME_URL="https://www.steampowered.com/"\n'
                    'DOCUMENTATION_URL="https://support.steampowered.com/"\n'
                    'SUPPORT_URL="https://support.steampowered.com/"\n'
                    'BUG_REPORT_URL="https://support.steampowered.com/"')


@dataclass
class OsReleaseData:
    variant_id: str
    version_id: str
    build_id: str
    branch_id: str = ''
    name: str = 'SteamOS'
    pretty_name: str = 'SteamOS'
    version_codename: str = 'holo'
    id: str = 'steamos'
    id_like: str = 'arch'
    logo: str = 'steamos'
    additional_entries: str = STANDARD_ENTRIES


@dataclass
class ManifestData:
    os_release: OsReleaseData
    expected_manifest: str
    product_override: str = ''
    release_override: str = ''
    variant_override: str = ''
    branch_override: str = ''
    default_update_branch: str = ''
    arch_override: str = ''
    version_override: str = ''
    buildid_override: str = ''
    introduces_checkpoint_override: int = 0
    requires_checkpoint_override: int = 0
    server_manifest: bool = False


manifest_data = [
    ManifestData(
        os_release=OsReleaseData(
            variant_id='steamdeck-main',
            version_id='3.6',
            build_id='20231213.1000',
        ),
        expected_manifest=textwrap.dedent("""\
            {
              "product": "steamos",
              "release": "holo",
              "variant": "steamdeck-main",
              "arch": "amd64",
              "version": "3.6.0",
              "buildid": "20231213.1000"
            }"""),
    ),

    ManifestData(
        os_release=OsReleaseData(
            variant_id='steamdeck-beta',
            version_id='3.6.5',
            build_id='20240103.100',
        ),
        introduces_checkpoint_override=2,
        requires_checkpoint_override=1,
        expected_manifest=textwrap.dedent("""\
            {
              "product": "steamos",
              "release": "holo",
              "variant": "steamdeck-beta",
              "arch": "amd64",
              "version": "3.6.5",
              "buildid": "20240103.100",
              "introduces_checkpoint": 2,
              "requires_checkpoint": 1
            }"""),
    ),

    ManifestData(
        os_release=OsReleaseData(
            variant_id='steamdeck-beta',
            version_id='3.6.5',
            build_id='20240103.100',
        ),
        product_override='steamos_episode2',
        release_override='holo_episode2',
        variant_override='steamdeck-bc',
        arch_override='i386',
        version_override='snapshot',
        buildid_override='20240103.101',
        requires_checkpoint_override=1,
        server_manifest=True,
        expected_manifest=textwrap.dedent("""\
            {
              "product": "steamos_episode2",
              "release": "holo_episode2",
              "variant": "steamdeck-bc",
              "arch": "i386",
              "version": "snapshot",
              "buildid": "20240103.101",
              "requires_checkpoint": 1
            }"""),
    ),

    ManifestData(
        # Create a manifest from an os-release that doesn't have the necessary fields.
        # It works because we override the missing parts
        os_release=OsReleaseData(
            variant_id='',
            version_id='',
            build_id='',
        ),
        product_override='steamos_episode2',
        release_override='holo_episode2',
        variant_override='steamdeck-bc',
        arch_override='i386',
        version_override='snapshot',
        buildid_override='20240103.101',
        requires_checkpoint_override=1,
        expected_manifest=textwrap.dedent("""\
            {
              "product": "steamos_episode2",
              "release": "holo_episode2",
              "variant": "steamdeck-bc",
              "arch": "i386",
              "version": "snapshot",
              "buildid": "20240103.101",
              "requires_checkpoint": 1
            }"""),
    ),

    ManifestData(
        os_release=OsReleaseData(
            variant_id='steamdeck',
            version_id='3.7.3',
            build_id='20240120.1',
            branch_id='stable',
        ),
        default_update_branch='stable',
        server_manifest=True,
        expected_manifest=textwrap.dedent("""\
            {
              "product": "steamos",
              "release": "holo",
              "variant": "steamdeck",
              "branch": "stable",
              "default_update_branch": "stable",
              "arch": "amd64",
              "version": "3.7.3",
              "buildid": "20240120.1"
            }"""),
    ),

    ManifestData(
        os_release=OsReleaseData(
            variant_id='steamdeck',
            version_id='3.7.3',
            build_id='20240120.1',
        ),
        branch_override='beta',
        default_update_branch='stable',
        server_manifest=True,
        expected_manifest=textwrap.dedent("""\
            {
              "product": "steamos",
              "release": "holo",
              "variant": "steamdeck",
              "branch": "beta",
              "default_update_branch": "stable",
              "arch": "amd64",
              "version": "3.7.3",
              "buildid": "20240120.1"
            }"""),
    ),

    ManifestData(
        os_release=OsReleaseData(
            variant_id='steamdeck',
            version_id='3.7.5',
            build_id='20240125.1',
            branch_id='stable',
        ),
        branch_override='main',
        default_update_branch='main',
        expected_manifest=textwrap.dedent("""\
            {
              "product": "steamos",
              "release": "holo",
              "variant": "steamdeck",
              "default_update_branch": "main",
              "arch": "amd64",
              "version": "3.7.5",
              "buildid": "20240125.1"
            }"""),
    ),
]


class MkManifestsTestCase(unittest.TestCase):

    def test_making_manifest(self):
        for data in manifest_data:
            os_release = (f'NAME="{data.os_release.name}"\n'
                          f'PRETTY_NAME="{data.os_release.pretty_name}"\n'
                          f'VERSION_CODENAME={data.os_release.version_codename}\n'
                          f'ID={data.os_release.id}\n'
                          f'ID_LIKE={data.os_release.id_like}\n'
                          f'LOGO={data.os_release.logo}\n'
                          f'{data.os_release.additional_entries}\n')
            if data.os_release.variant_id:
                os_release += f'VARIANT_ID={data.os_release.variant_id}\n'
            if data.os_release.version_id:
                os_release += f'VERSION_ID={data.os_release.version_id}\n'
            if data.os_release.build_id:
                os_release += f'BUILD_ID={data.os_release.build_id}\n'
            if data.os_release.branch_id:
                os_release += f'{data.os_release.id.upper()}_DEFAULT_BRANCH={data.os_release.branch_id}\n'

            args = []
            if data.product_override:
                args.extend(['--product', data.product_override])
            if data.release_override:
                args.extend(['--release', data.release_override])
            if data.variant_override:
                args.extend(['--variant', data.variant_override])
            if data.branch_override:
                args.extend(['--branch', data.branch_override])
            if data.default_update_branch:
                args.extend(['--default-update-branch', data.default_update_branch])
            if data.arch_override:
                args.extend(['--arch', data.arch_override])
            if data.version_override:
                args.extend(['--version', data.version_override])
            if data.buildid_override:
                args.extend(['--buildid', data.buildid_override])
            if data.introduces_checkpoint_override > 0:
                args.extend(['--introduces-checkpoint', str(data.introduces_checkpoint_override)])
            if data.requires_checkpoint_override > 0:
                args.extend(['--requires-checkpoint', str(data.requires_checkpoint_override)])
            if data.server_manifest:
                args.extend(['--server-manifest'])

            with self.subTest(), patch('builtins.open', mock_open(read_data=os_release)):
                f = io.StringIO()
                with redirect_stdout(f):
                    mkmanifest.main(args)
                manifest = f.getvalue()
                self.assertEqual(data.expected_manifest.strip('\n'), manifest.strip('\n'))


if __name__ == '__main__':
    unittest.main()
