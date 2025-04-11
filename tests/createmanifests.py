# SPDX-License-Identifier: LGPL-2.1+
#
# Copyright © 2023 Collabora Ltd
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
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class Variant(StrEnum):
    STEAMDECK = 'steamdeck'
    STEAMDECK_RC = 'steamdeck-rc'
    STEAMDECK_BETA = 'steamdeck-beta'
    STEAMDECK_BC = 'steamdeck-bc'
    STEAMDECK_MAIN = 'steamdeck-main'
    STEAMDECK_STAGING = 'steamdeck-staging'
    # Simulate a generic vanilla image type
    VANILLA = 'vanilla'
    # Simulate yet another variant type
    FEATURE_X = 'feature-x'


class Branch(StrEnum):
    STABLE = 'stable'
    RC = 'rc'
    BETA = 'beta'
    BC = 'bc'
    MAIN = 'main'
    STAGING = 'staging'
    LEGACY = ''


@dataclass
class Manifest:
    variant: str
    version: str
    buildid: str
    branch: str = Branch.LEGACY
    product: str = 'steamos'
    release: str = 'holo'
    arch: str = 'amd64'
    introduces_checkpoint: int = -1
    requires_checkpoint: int = -1
    # If None, "shadow_checkpoint" entry will not be included in the manifest
    shadow_checkpoint: bool | None = None
    # If None, "skip" entry will not be included in the manifest
    skip: bool | None = None
    deleted: bool = False
    # Create a manifest file that is empty
    empty: bool = False
    # Optional path to write the manifest into
    img_dir: str = None


@dataclass
class Hierarchy:
    directory_name: str
    manifests: list[Manifest]


images_hierarchies = [
    Hierarchy(
        directory_name='snapshots',
        manifests=[
            Manifest(Variant.STEAMDECK, 'snapshot', '20181102.1'),
            Manifest(Variant.STEAMDECK_BETA, 'snapshot', '20181102.100'),
            Manifest(Variant.STEAMDECK_RC, 'snapshot', '20220215.0'),
            Manifest(Variant.STEAMDECK, 'snapshot', '20181108.1'),
            Manifest(Variant.STEAMDECK_BETA, 'snapshot', '20181108.100'),
            # Simulate some .ci images
            Manifest(Variant.STEAMDECK, 'snapshot', '20181108.1', img_dir='steamdeck/.ci/snapshot'),
            Manifest(Variant.STEAMDECK_BETA, 'snapshot', '20181108.1', img_dir='steamdeck-beta/.ci/snapshot'),
        ]
    ),

    Hierarchy(
        directory_name='releases-checkpoints',
        manifests=[
            Manifest(Variant.STEAMDECK, '3.6', '20231112.1'),
            # Simulate an image that requires a checkpoint zero and provides directly the checkpoint 2
            Manifest(Variant.STEAMDECK, '3.6', '20231114.1', requires_checkpoint=0, introduces_checkpoint=2),
            Manifest(Variant.STEAMDECK, '3.6', '20231115.1', requires_checkpoint=2),

            Manifest(Variant.STEAMDECK_BETA, '3.6', '20231113.100', requires_checkpoint=0, introduces_checkpoint=1),
            Manifest(Variant.STEAMDECK_BETA, '3.6', '20231113.101', requires_checkpoint=1, introduces_checkpoint=2),
        ]
    ),

    Hierarchy(
        directory_name='releases-retired-checkpoint',
        manifests=[
            Manifest(Variant.STEAMDECK, '3.6', '20231112.1'),
            # Simulate a checkpoint that was quickly retired by using the "skip" option and
            # substituted with another one
            Manifest(Variant.STEAMDECK, '3.6', '20231113.1', requires_checkpoint=0, introduces_checkpoint=1, skip=True),
            Manifest(Variant.STEAMDECK, '3.6', '20231113.2', requires_checkpoint=0, introduces_checkpoint=1),
            Manifest(Variant.STEAMDECK, '3.6', '20231120.1', requires_checkpoint=1),
        ]
    ),

    Hierarchy(
        directory_name='releases',
        manifests=[
            Manifest(Variant.STEAMDECK, '3.1', '20220401.1'),
            Manifest(Variant.STEAMDECK, '3.1', '20220402.3', requires_checkpoint=0, introduces_checkpoint=1),
            Manifest(Variant.STEAMDECK, '3.2', '20220411.1', requires_checkpoint=1),
            # Simulate an update that we don't want to propose anymore
            Manifest(Variant.STEAMDECK, '3.2', '20220412.1', requires_checkpoint=1, skip=True),
            # Test the skip field explicitly set to false
            Manifest(Variant.STEAMDECK, '3.3', '20220423.1', requires_checkpoint=1, introduces_checkpoint=2, skip=False),

            Manifest(Variant.STEAMDECK_RC, '3.1', '20220401.5'),

            # Same checkpoint as in 'steamdeck'
            Manifest(Variant.STEAMDECK_BETA, '3.1', '20220402.103', requires_checkpoint=0, introduces_checkpoint=1),
            Manifest(Variant.STEAMDECK_BETA, '3.1', '20220405.100', requires_checkpoint=1),
            Manifest(Variant.STEAMDECK_BETA, '3.3', '20220423.100', requires_checkpoint=1, introduces_checkpoint=2),
            # Testing a new checkpoint that still hasn't been promoted to 'steamdeck'
            Manifest(Variant.STEAMDECK_BETA, '3.4', '20220501.100', requires_checkpoint=2, introduces_checkpoint=3),
        ]
    ),

    Hierarchy(
        directory_name='releases2',
        manifests=[
            Manifest(Variant.STEAMDECK, '3.5', '20230403.1'),
            Manifest(Variant.STEAMDECK, '3.5', '20230404.1', requires_checkpoint=0, introduces_checkpoint=1),
            Manifest(Variant.STEAMDECK, '3.5', '20230411.1', requires_checkpoint=1),
            Manifest(Variant.STEAMDECK, '3.6', '20230423.1', requires_checkpoint=1, introduces_checkpoint=3,
                     shadow_checkpoint=True),
            Manifest(Variant.STEAMDECK, '3.6', '20230425.1', requires_checkpoint=3),

            Manifest(Variant.STEAMDECK_BETA, '3.5', '20230402.100', requires_checkpoint=0, introduces_checkpoint=1),
            # Simulate a checkpoint 2 and then a checkpoint 3 that reverts it.
            # This is signaled by the fact that in "steamdeck" we have shadow checkpoints for those two.
            Manifest(Variant.STEAMDECK_BETA, '3.6', '20230412.100', requires_checkpoint=1, introduces_checkpoint=2),
            Manifest(Variant.STEAMDECK_BETA, '3.6', '20230412.101', requires_checkpoint=2),
            Manifest(Variant.STEAMDECK_BETA, '3.6', '20230413.100', requires_checkpoint=2, introduces_checkpoint=3),
        ]
    ),

    Hierarchy(
        directory_name='releases3',
        manifests=[
            Manifest(Variant.STEAMDECK, '3.5', '20230403.1'),
            Manifest(Variant.STEAMDECK, '3.5', '20230404.1', requires_checkpoint=0, introduces_checkpoint=1),
            Manifest(Variant.STEAMDECK, '3.5', '20230411.1', requires_checkpoint=1),

            Manifest(Variant.STEAMDECK_STAGING, '3.5', '20230501.10000', requires_checkpoint=1),
            Manifest(Variant.STEAMDECK_STAGING, '3.5', '20230507.10000', requires_checkpoint=1,
                     introduces_checkpoint=2),
        ]
    ),

    Hierarchy(
        directory_name='releases4',
        manifests=[
            Manifest(Variant.STEAMDECK, '3.5', '20230404.1', requires_checkpoint=0, introduces_checkpoint=1),
            Manifest(Variant.STEAMDECK, '3.5', '20230411.1', requires_checkpoint=1),
            Manifest(Variant.STEAMDECK, '3.6', '20230508.1', requires_checkpoint=1, introduces_checkpoint=2,
                     shadow_checkpoint=True),

            Manifest(Variant.STEAMDECK_STAGING, '3.5', '20230501.10000', requires_checkpoint=1),
            Manifest(Variant.STEAMDECK_STAGING, '3.6', '20230507.10000', requires_checkpoint=1,
                     introduces_checkpoint=2),
        ]
    ),

    Hierarchy(
        directory_name='releases5',
        manifests=[
            Manifest(Variant.STEAMDECK, '3.5', '20230404.1'),
            Manifest(Variant.STEAMDECK, '3.5', '20230411.1', requires_checkpoint=0, introduces_checkpoint=1),
            Manifest(Variant.STEAMDECK, '3.5', '20230412.1', requires_checkpoint=1),
            Manifest(Variant.STEAMDECK, '3.6', '20230413.1', requires_checkpoint=1),

            Manifest(Variant.STEAMDECK_BETA, '3.5', '20230405.100'),
            Manifest(Variant.STEAMDECK_BETA, '3.5', '20230405.101', requires_checkpoint=0, introduces_checkpoint=1),
            Manifest(Variant.STEAMDECK_BETA, '3.5', '20230406.100', requires_checkpoint=1),
            Manifest(Variant.STEAMDECK_BETA, '3.6', '20230421.100', requires_checkpoint=1),
            Manifest(Variant.STEAMDECK_BETA, '3.6', '20230422.100', requires_checkpoint=1),
        ]
    ),

    Hierarchy(
        directory_name='releases-and-snaps',
        manifests=[
            Manifest(Variant.STEAMDECK, 'snapshot', '20220201.1'),
            Manifest(Variant.STEAMDECK, 'snapshot', '20220225.1'),
            Manifest(Variant.STEAMDECK, '3.0', '20220303.2'),
            Manifest(Variant.STEAMDECK, '3.0', '20220303.3', skip=True, deleted=True),

            Manifest(Variant.STEAMDECK_RC, '3.0', '20220303.1'),

            Manifest(Variant.STEAMDECK_BETA, 'snapshot', '20220221.100'),
            Manifest(Variant.STEAMDECK_BETA, '3.1', '20220301.100'),

            Manifest(Variant.STEAMDECK_MAIN, '3.1', '20220302.1005'),
            Manifest(Variant.STEAMDECK_MAIN, '3.2', '20220304.1000'),
        ]
    ),

    Hierarchy(
        directory_name='releases-and-snaps2',
        manifests=[
            Manifest(Variant.STEAMDECK, 'snapshot', '20230201.1'),
            Manifest(Variant.STEAMDECK, '3.5', '20230303.1'),
            Manifest(Variant.STEAMDECK, '3.5', '20230401.1', requires_checkpoint=0, introduces_checkpoint=1),
            Manifest(Variant.STEAMDECK, '3.5', '20230411.1', requires_checkpoint=1),

            Manifest(Variant.STEAMDECK_BETA, 'snapshot', '20230303.100'),
            Manifest(Variant.STEAMDECK_BETA, '3.5', '20230401.100', requires_checkpoint=0, introduces_checkpoint=1),
            Manifest(Variant.STEAMDECK_BETA, '3.6', '20230727.100', requires_checkpoint=1),
        ]
    ),

    Hierarchy(
        directory_name='releases-and-snaps3',
        manifests=[
            Manifest(Variant.STEAMDECK, 'snapshot', '20230502.1'),
            # This simulates a new stable hotfix release, still not versioned yet
            Manifest(Variant.STEAMDECK, 'snapshot', '20230822.1'),

            Manifest(Variant.STEAMDECK_RC, 'snapshot', '20230503.1'),

            Manifest(Variant.STEAMDECK_BETA, '3.5', '20230715.100'),
            Manifest(Variant.STEAMDECK_BETA, '3.5', '20230806.100'),

            Manifest(Variant.STEAMDECK_BC, '3.6', '20230805.100'),

            Manifest(Variant.STEAMDECK_MAIN, '3.5', '20230714.1005'),
            Manifest(Variant.STEAMDECK_MAIN, '3.6', '20230804.1000'),
        ]
    ),

    Hierarchy(
        directory_name='releases-and-snaps4',
        manifests=[
            # This simulates the case where versioned images reached rel, but we never
            # released an updated rc
            Manifest(Variant.STEAMDECK, '3.5', '20230820.1'),

            Manifest(Variant.STEAMDECK_RC, 'snapshot', '20220303.1'),

            Manifest(Variant.STEAMDECK_BETA, '3.5', '20230815.100'),
        ]
    ),

    Hierarchy(
        directory_name='releases-and-snaps5',
        manifests=[
            Manifest(Variant.STEAMDECK, 'snapshot', '20230801.1'),

            Manifest(Variant.STEAMDECK_RC, '3.0', '20220303.1'),

            Manifest(Variant.STEAMDECK_BETA, '3.5', '20230815.100'),
            Manifest(Variant.STEAMDECK_BETA, '3.5', '20250411.100'),
        ]
    ),

    Hierarchy(
        directory_name='unexpected-manifest',
        manifests=[
            Manifest(Variant.STEAMDECK, '3.6.1', '20231104.1'),
            # Image manifest that is unexpectedly empty
            Manifest(Variant.STEAMDECK, '3.6.1', '20231104.2', empty=True),
        ]
    ),

    Hierarchy(
        directory_name='shadow-skip',
        manifests=[
            Manifest(Variant.STEAMDECK, '3.6.1', '20231104.1'),
            # Image that is both a shadow checkpoint and marked as skip
            Manifest(Variant.STEAMDECK, '3.6.1', '20231104.4', requires_checkpoint=0, introduces_checkpoint=1,
                     shadow_checkpoint=True, skip=True),
        ]
    ),

    Hierarchy(
        directory_name='shadow-introduce',
        manifests=[
            Manifest(Variant.STEAMDECK, '3.6.1', '20231104.1'),
            # Shadow checkpoint that doesn't introduce any checkpoint
            Manifest(Variant.STEAMDECK, '3.6.1', '20231104.4', shadow_checkpoint=True),
        ]
    ),

    Hierarchy(
        directory_name='shadow-multiple',
        manifests=[
            Manifest(Variant.STEAMDECK, '3.6.1', '20231104.1'),
            Manifest(Variant.STEAMDECK, '3.6.1', '20231105.1', requires_checkpoint=0, introduces_checkpoint=1,
                     shadow_checkpoint=True),
            # Another shadow checkpoint that introduces the same checkpoint
            Manifest(Variant.STEAMDECK, '3.6.1', '20231106.1', requires_checkpoint=0, introduces_checkpoint=1,
                     shadow_checkpoint=True),
        ]
    ),

    Hierarchy(
        directory_name='checkpoint-multiple',
        manifests=[
            Manifest(Variant.STEAMDECK, '3.6.1', '20231104.1'),
            Manifest(Variant.STEAMDECK, '3.6.1', '20231105.1', requires_checkpoint=0, introduces_checkpoint=1),
            # Another image that introduces the same checkpoint
            Manifest(Variant.STEAMDECK, '3.6.1', '20231106.1', requires_checkpoint=0, introduces_checkpoint=1),
        ]
    ),

    Hierarchy(
        directory_name='wrong-checkpoint',
        manifests=[
            Manifest(Variant.STEAMDECK, '3.6.1', '20231104.1', requires_checkpoint=3),
            # Image that introduces a checkpoint that is lower than what it requires
            Manifest(Variant.STEAMDECK, '3.6.1', '20231104.4', requires_checkpoint=3, introduces_checkpoint=2),
        ]
    ),

    Hierarchy(
        directory_name='wrong-checkpoint2',
        manifests=[
            Manifest(Variant.STEAMDECK, '3.6.1', '20231104.1', requires_checkpoint=3),
            # Image that introduces a checkpoint that is equal to what it requires
            Manifest(Variant.STEAMDECK, '3.6.1', '20231104.4', requires_checkpoint=3, introduces_checkpoint=3),
        ]
    ),

    Hierarchy(
        directory_name='duplicated-image',
        manifests=[
            Manifest(Variant.STEAMDECK, '3.6', '20231202.1', requires_checkpoint=0, introduces_checkpoint=1),
            Manifest(Variant.STEAMDECK, '3.6', '20231203.1', requires_checkpoint=1),
            # Image in another variant that doesn't have a unique version and buildid
            Manifest(Variant.STEAMDECK_BETA, '3.6', '20231202.1'),
        ]
    ),

    Hierarchy(
        directory_name='skip-checkpoint',
        manifests=[
            Manifest(Variant.STEAMDECK, '3.6.5', '20231201.1'),
            # Checkpoint marked as skip, but without another canonical checkpoint to replace it yet
            Manifest(Variant.STEAMDECK, '3.6.6', '20231202.1', requires_checkpoint=0, introduces_checkpoint=1, skip=True),
            Manifest(Variant.STEAMDECK_BETA, '3.6.6', '20231205.100', requires_checkpoint=0, introduces_checkpoint=1),
        ]
    ),

    Hierarchy(
        directory_name='branch1',
        manifests=[
            Manifest(Variant.STEAMDECK, '3.6.5', '20240104.1', branch=Branch.STABLE),
            Manifest(Variant.STEAMDECK, '3.6.6', '20240108.1', branch=Branch.STABLE),
            Manifest(Variant.STEAMDECK, '3.7.2', '20240115.1', branch=Branch.STABLE,
                     requires_checkpoint=0, introduces_checkpoint=1),
            Manifest(Variant.STEAMDECK, '3.7.3', '20240115.2', branch=Branch.STABLE, requires_checkpoint=1),

            Manifest(Variant.STEAMDECK, '3.6.5', '20240107.1', branch=Branch.RC),

            Manifest(Variant.STEAMDECK, '3.7.1', '20240115.100', branch=Branch.BETA,
                     requires_checkpoint=0, introduces_checkpoint=1),
            Manifest(Variant.STEAMDECK, '3.7.5', '20240120.100', branch=Branch.BETA, requires_checkpoint=1),
        ]
    ),

    Hierarchy(
        directory_name='branch-and-legacy-variant1',
        manifests=[
            Manifest(Variant.STEAMDECK, '3.6.1', '20231103.1'),
            Manifest(Variant.STEAMDECK, '3.6.1', '20231104.1'),
            Manifest(Variant.STEAMDECK_BETA, '3.6.1', '20231105.100'),

            Manifest(Variant.STEAMDECK, '3.6.8', '20240110.100', branch=Branch.BETA),
            Manifest(Variant.STEAMDECK, '3.7.1', '20240115.100', branch=Branch.BETA,
                     requires_checkpoint=0, introduces_checkpoint=1),
            Manifest(Variant.STEAMDECK, '3.7.5', '20240120.100', branch=Branch.BETA, requires_checkpoint=1),
            Manifest(Variant.STEAMDECK, '3.7.6', '20240120.101', branch=Branch.BETA, requires_checkpoint=1),
        ]
    ),

    Hierarchy(
        directory_name='branch2',
        manifests=[
            Manifest(Variant.STEAMDECK, '3.6.6', '20240108.1', branch=Branch.STABLE),
            Manifest(Variant.STEAMDECK, '3.7.2', '20240115.1', branch=Branch.STABLE,
                     requires_checkpoint=0, introduces_checkpoint=1),
            Manifest(Variant.STEAMDECK, '3.7.3', '20240115.2', branch=Branch.STABLE, requires_checkpoint=1),

            Manifest(Variant.STEAMDECK, '3.7.1', '20240115.100', branch=Branch.BETA,
                     requires_checkpoint=0, introduces_checkpoint=1),
            Manifest(Variant.STEAMDECK, '3.7.5', '20240120.100', branch=Branch.BETA, requires_checkpoint=1),

            Manifest(Variant.VANILLA, '3.6.7', '20240109.50', branch=Branch.STABLE),
            Manifest(Variant.VANILLA, '3.6.8', '20240109.55', branch=Branch.BETA),
        ]
    ),

    Hierarchy(
        directory_name='branch3_eol',
        manifests=[
            Manifest(Variant.STEAMDECK, '3.6.6', '20240108.1', branch=Branch.STABLE),
            Manifest(Variant.STEAMDECK, '3.7.1', '20240115.1', branch=Branch.STABLE),

            Manifest(Variant.VANILLA, '3.6.7', '20240109.50', branch=Branch.STABLE),
            Manifest(Variant.VANILLA, '3.7.5', '20240401.50', branch=Branch.STABLE),

            Manifest(Variant.FEATURE_X, '3.6.8', '20240320.60', branch=Branch.STABLE),
        ]
    ),

    Hierarchy(
        directory_name='branch4',
        manifests=[
            Manifest(Variant.STEAMDECK, '3.6.6', '20240801.1', branch=Branch.STABLE),

            Manifest(Variant.STEAMDECK, '3.6.7', '20240802.1', branch=Branch.RC),

            Manifest(Variant.STEAMDECK, '3.6.8', '20240805.100', branch=Branch.BETA),

            Manifest(Variant.STEAMDECK, '3.5.0', '20240707.111', branch=Branch.BC),
        ]
    ),
]

additional_images = [
    Hierarchy(
        directory_name='releases',
        manifests=[
            Manifest(Variant.STEAMDECK, '3.5', '20230705.1', requires_checkpoint=2, introduces_checkpoint=3),
        ]
    ),
]


def build_image_hierarchy(path: Path, only_additional_images=False) -> None:

    hierarchies = additional_images if only_additional_images else images_hierarchies

    for hierarchy in hierarchies:
        images_directory = path / hierarchy.directory_name

        for manifest in hierarchy.manifests:
            img_dir = images_directory / manifest.product / manifest.release / manifest.version / manifest.arch
            if manifest.img_dir:
                img_dir = images_directory / manifest.img_dir
            img_name = f'{manifest.product}-{manifest.release}-{manifest.buildid}-{manifest.version}-{manifest.arch}-{manifest.variant}'
            img_manifest = img_dir / f'{img_name}.manifest.json'
            img_raucb = img_dir / f'{img_name}.raucb'
            chunks_details = img_dir / f'{img_name}.chunks_details.json'
            mock_chunks_details = Path(__file__).parent.absolute() / 'rauc' / f'{img_name}.chunks_details.json'
            mock_raucb = Path(__file__).parent.absolute() / 'rauc' / f'{img_name}.raucb'

            img_dir.mkdir(parents=True, exist_ok=True)

            if manifest.empty:
                img_manifest.touch()
                continue

            json_data = {'product': manifest.product, 'release': manifest.release,
                         'variant': manifest.variant, 'arch': manifest.arch,
                         'version': manifest.version, 'buildid': manifest.buildid}

            if manifest.branch != Branch.LEGACY:
                json_data['branch'] = manifest.branch

            if manifest.requires_checkpoint > -1:
                json_data['requires_checkpoint'] = manifest.requires_checkpoint

            if manifest.introduces_checkpoint > -1:
                json_data['introduces_checkpoint'] = manifest.introduces_checkpoint

            if manifest.shadow_checkpoint is not None:
                json_data['shadow_checkpoint'] = manifest.shadow_checkpoint

            if manifest.skip is not None:
                json_data['skip'] = manifest.skip

            img_manifest.write_text(json.dumps(json_data, indent=4))

            if manifest.deleted or manifest.shadow_checkpoint:
                # Do not create the RAUC bundle file and the directory with the chunks,
                # as if they were removed to prevent an image to ever be installed
                continue

            if mock_raucb.is_file():
                # Use the mock raucb, if available
                img_raucb.symlink_to(mock_raucb)
            else:
                # Otherwise create an empty file as a placeholder
                img_raucb.touch()

            if mock_chunks_details.is_file():
                chunks_details.symlink_to(mock_chunks_details)

            (img_dir / f'{img_name}.castr').mkdir()
