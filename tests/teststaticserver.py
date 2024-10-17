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
import contextlib
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass, field
import signal
import subprocess
import sys
import time
import unittest
from difflib import ndiff
from pathlib import Path
from unittest.mock import patch

from tests.createmanifests import build_image_hierarchy

EXPECTATION_PARENT = Path('./tests')

# Always add cwd to the sys path
sys.path.insert(1, os.getcwd())

log = logging.getLogger(__name__)


@dataclass
class RemoteInfoConfig:
    variants: tuple[str, ...] = ()
    branches: tuple[str, ...] = ()


@dataclass
class ServerConfig:
    pool_dir: str
    branches: tuple[str, ...]
    branches_to_consider: dict[str, list[str]] = field(default_factory=dict)
    unstable: bool = True
    strict_pool_validation: bool = True
    remote_info_config: RemoteInfoConfig = field(default_factory=RemoteInfoConfig)
    variants: tuple[str, ...] = ('steamdeck',)
    variants_eol: tuple[str, ...] = ()
    products: tuple[str, ...] = ('steamos',)
    releases: tuple[str, ...] = ('holo',)
    archs: tuple[str, ...] = ('amd64',)


@dataclass
class ServerData:
    msg: str
    config: ServerConfig
    expectation: str
    changed_expectation: str = ""
    mock_leftovers: Path | None = None
    mock_ndiff: Path | None = None
    replaced_leftovers: bool = False
    unchanged_lefovers: bool = False
    removed_image_warning: bool = False
    run_as_daemon: bool = False
    exit_code: int = 0
    log_message: str = ""


server_data = [
    ServerData(
        msg='Static server with release images',
        config=ServerConfig(
            pool_dir='releases',
            branches=('stable', 'beta', 'rc'),
            branches_to_consider={
                'rc': ['stable'],
                'beta': ['stable', 'rc'],
            },
            remote_info_config=RemoteInfoConfig(
                variants=('steamdeck',),
                branches=('stable', 'beta', 'rc'),
            ),
        ),
        expectation='staticexpected',
        mock_leftovers=EXPECTATION_PARENT / 'staticexpected_mock_leftover',
        mock_ndiff=EXPECTATION_PARENT / 'staticexpected_mock_ndiff',
        unchanged_lefovers=True,
        removed_image_warning=True,
    ),
    ServerData(
        msg='Static server with snapshot images',
        config=ServerConfig(
            pool_dir='snapshots',
            branches=('stable', 'beta'),
            remote_info_config=RemoteInfoConfig(
                variants=('steamdeck',),
                branches=('stable', 'beta'),
            ),
        ),
        expectation='staticsnapexpected',
    ),
    ServerData(
        msg='Static server with snapshot and release images',
        config=ServerConfig(
            pool_dir='releases-and-snaps',
            branches=('stable', 'beta', 'main', 'rc'),
            branches_to_consider={
                'rc': ['stable'],
                'beta': ['stable', 'rc'],
            },
        ),
        expectation='static_rel_and_snap_expected',
        mock_leftovers=EXPECTATION_PARENT / 'static_rel_and_snap_mock_leftover',
        mock_ndiff=EXPECTATION_PARENT / 'static_rel_and_snap_mock_ndiff',
        replaced_leftovers=True,
        unchanged_lefovers=True,
    ),
    ServerData(
        msg='Static server with release images running as daemon',
        config=ServerConfig(
            pool_dir='releases',
            branches=('stable', 'beta', 'rc'),
            branches_to_consider={
                'rc': ['stable'],
                'beta': ['stable', 'rc'],
            },
            remote_info_config=RemoteInfoConfig(
                variants=('steamdeck',),
                branches=('stable', 'beta', 'rc'),
            ),
        ),
        expectation='staticexpected',
        changed_expectation='staticdaemonexpected2',
        mock_leftovers=EXPECTATION_PARENT / 'staticexpected_mock_leftover',
        unchanged_lefovers=True,
        removed_image_warning=True,
        run_as_daemon=True,
    ),
    ServerData(
        msg='Static server with snapshot images',
        config=ServerConfig(
            pool_dir='releases-and-snaps2',
            branches=('stable', 'beta'),
            branches_to_consider={'beta': ['stable']},
            remote_info_config=RemoteInfoConfig(
                variants=('steamdeck',),
                branches=('stable', 'beta'),
            ),
        ),
        expectation='static_rel_and_snap2_expected',
    ),
    ServerData(
        msg='Static server with snapshot and release images 3',
        config=ServerConfig(
            pool_dir='releases-and-snaps3',
            branches=('stable', 'beta', 'main', 'rc', 'bc'),
            branches_to_consider={
                'rc': ['stable'],
                'beta': ['stable', 'rc'],
                'bc': ['stable', 'rc', 'beta'],
                'main': ['stable', 'rc', 'beta', 'bc'],
            },
        ),
        expectation='static_rel_and_snap3_expected',
    ),
    ServerData(
        msg='Static server with snapshot and release images 4',
        config=ServerConfig(
            pool_dir='releases-and-snaps4',
            branches=('stable', 'beta', 'rc'),
            branches_to_consider={
                'rc': ['stable'],
                'beta': ['stable', 'rc'],
            },
        ),
        expectation='static_rel_and_snap4_expected',
    ),
    ServerData(
        msg='Static server with snapshot and release images 5',
        config=ServerConfig(
            pool_dir='releases-and-snaps5',
            branches=('stable', 'beta', 'rc'),
            branches_to_consider={
                'rc': ['stable'],
                'beta': ['stable', 'rc'],
            },
        ),
        expectation='static_rel_and_snap5_expected',
    ),
    ServerData(
        msg='Server with a variant that does not match any of the images in the pool',
        config=ServerConfig(
            pool_dir='releases-and-snaps5',
            branches=('stable', 'beta', 'rc', 'missing'),
            branches_to_consider={
                'rc': ['stable'],
                'beta': ['stable', 'rc'],
            },
        ),
        expectation='',
        exit_code=1,
    ),
    ServerData(
        msg='Server with a variant that does not match any of the images in the pool, as daemon',
        config=ServerConfig(
            pool_dir='releases-and-snaps5',
            branches=('stable', 'beta', 'rc', 'missing'),
            branches_to_consider={
                'rc': ['stable'],
                'beta': ['stable', 'rc'],
            },
        ),
        expectation='',
        run_as_daemon=True,
        exit_code=1,
    ),
    ServerData(
        msg='Static server with a checkpoint image that goes directly from zero to two',
        config=ServerConfig(
            pool_dir='releases-checkpoints',
            branches=('stable', 'beta'),
            branches_to_consider={
                'rc': ['stable'],
                'beta': ['stable', 'rc'],
            },
        ),
        expectation='static_rel_checkpoints_expected',
    ),
    ServerData(
        msg='Static server with a retired checkpoint',
        config=ServerConfig(
            pool_dir='releases-retired-checkpoint',
            branches=('stable',),
        ),
        expectation='statis_retired_checkpoint',
    ),
    ServerData(
        msg='Static server with release images 2',
        config=ServerConfig(
            pool_dir='releases2',
            branches=('stable', 'beta'),
            branches_to_consider={'beta': ['stable']},
            remote_info_config=RemoteInfoConfig(
                variants=('steamdeck',),
                branches=('stable', 'beta'),
            ),
        ),
        expectation='staticexpected2',
    ),
    ServerData(
        msg='Simulate an image that got converted into a shadow checkpoint',
        config=ServerConfig(
            pool_dir='releases2',
            branches=('stable', 'beta'),
            branches_to_consider={'beta': ['stable']},
            remote_info_config=RemoteInfoConfig(
                variants=('steamdeck',),
                branches=('stable', 'beta'),
            ),
        ),
        expectation='staticexpected2',
        mock_leftovers=EXPECTATION_PARENT / 'staticexpected2_mock_leftover',
        exit_code=1,
    ),
    ServerData(
        msg='Static server with release images 3',
        config=ServerConfig(
            pool_dir='releases3',
            branches=('stable', 'staging'),
            branches_to_consider={'staging': ['stable']},
        ),
        expectation='staticexpected3',
    ),
    ServerData(
        msg='Static server with release images 4',
        config=ServerConfig(
            pool_dir='releases4',
            branches=('stable', 'staging'),
            branches_to_consider={'staging': ['stable']},
        ),
        expectation='staticexpected4',
    ),
    ServerData(
        msg='Static server with release images 5',
        config=ServerConfig(
            pool_dir='releases5',
            branches=('stable',),
        ),
        expectation='staticexpected5',
    ),
    ServerData(
        msg='Image with a broken manifest',
        config=ServerConfig(
            pool_dir='unexpected-manifest',
            branches=('stable',),
        ),
        expectation='',
        exit_code=1,
    ),
    ServerData(
        msg='Shadow image that is unexpectedly also marked as skip',
        config=ServerConfig(
            pool_dir='shadow-skip',
            branches=('stable',),
        ),
        expectation='',
        exit_code=1,
    ),
    ServerData(
        msg='Shadow image that is not introducing a checkpoint',
        config=ServerConfig(
            pool_dir='shadow-introduce',
            branches=('stable',),
        ),
        expectation='',
        exit_code=1,
    ),
    ServerData(
        msg='Two shadow checkpoints that introduce the same checkpoint',
        config=ServerConfig(
            pool_dir='shadow-multiple',
            branches=('stable',),
        ),
        expectation='',
        exit_code=1,
    ),
    ServerData(
        msg='Multiple images that introduce the same checkpoints',
        config=ServerConfig(
            pool_dir='checkpoint-multiple',
            branches=('stable',),
        ),
        expectation='',
        exit_code=1,
    ),
    ServerData(
        msg='Image with wrong checkpoint',
        config=ServerConfig(
            pool_dir='wrong-checkpoint',
            branches=('stable',),
        ),
        expectation='',
        exit_code=1,
    ),
    ServerData(
        msg='Image with wrong checkpoint 2',
        config=ServerConfig(
            pool_dir='wrong-checkpoint2',
            branches=('stable',),
        ),
        expectation='',
        exit_code=1,
    ),
    ServerData(
        msg='Duplicated image',
        config=ServerConfig(
            pool_dir='duplicated-image',
            branches=('stable', 'beta'),
        ),
        expectation='',
        exit_code=1,
    ),
    ServerData(
        msg='Checkpoint marked as skip',
        config=ServerConfig(
            pool_dir='skip-checkpoint',
            branches=('stable', 'beta'),
        ),
        expectation='skip_checkpoint_expected',
        log_message='WARNING:steamosatomupd.imagepool:The pool has a checkpoint for (steamdeck_stable, 1) marked as '
                    '\'skip\', but there isn\'t a canonical checkpoint to replace it.',
    ),
    ServerData(
        msg='Images with the new branch parameter',
        config=ServerConfig(
            pool_dir='branch1',
            branches=('stable', 'beta', 'rc'),
            branches_to_consider={
                'rc': ['stable'],
                'beta': ['stable', 'rc'],
            },
            remote_info_config=RemoteInfoConfig(
                variants=('steamdeck',),
                branches=('stable', 'beta', 'rc'),
            ),
        ),
        expectation='branch1_expected',
    ),
    ServerData(
        msg='Images with the new branch parameter',
        config=ServerConfig(
            pool_dir='branch1',
            branches=('stable', 'beta', 'rc'),
            branches_to_consider={
                'rc': ['stable'],
                'beta': ['stable', 'rc'],
            },
            remote_info_config=RemoteInfoConfig(
                variants=('steamdeck',),
                branches=('stable', 'beta', 'rc'),
            ),
        ),
        expectation='branch1_expected',
        run_as_daemon=True,
    ),
    ServerData(
        msg='Mix of old and new images',
        config=ServerConfig(
            pool_dir='branch-and-legacy-variant1',
            branches=('stable', 'beta'),
            branches_to_consider={'beta': ['stable']},
            remote_info_config=RemoteInfoConfig(
                variants=('steamdeck',),
                branches=('stable', 'beta'),
            ),
        ),
        expectation='branch_and_legacy_variant1_expected',
    ),
    ServerData(
        msg='Multiple branches and variants',
        config=ServerConfig(
            pool_dir='branch2',
            branches=('stable', 'beta'),
            variants=('steamdeck', 'vanilla'),
        ),
        expectation='branch2_expected',
    ),
    ServerData(
        msg='Same pool dir as before, with a variant marked as EOL',
        config=ServerConfig(
            pool_dir='branch2',
            branches=('stable', 'beta'),
            variants=('steamdeck', 'vanilla'),
            variants_eol=('vanilla:steamdeck',),
        ),
        expectation='branch2_eol_expected',
    ),
    ServerData(
        msg='Variant marked as EOL, even if is newer',
        config=ServerConfig(
            pool_dir='branch3_eol',
            branches=('stable',),
            variants=('steamdeck', 'vanilla', 'feature-x'),
            variants_eol=('vanilla:steamdeck', 'feature-x:steamdeck'),
            remote_info_config=RemoteInfoConfig(
                variants=('steamdeck', 'vanilla', 'feature-x'),
                branches=('stable',),
            ),
        ),
        expectation='branch3_eol_expected',
    ),
    ServerData(
        msg='Pool that still does not have all image branches',
        config=ServerConfig(
            pool_dir='branch1',
            branches=('stable', 'beta', 'rc', 'future'),
            branches_to_consider={
                'rc': ['stable'],
                'beta': ['stable', 'rc'],
            },
            strict_pool_validation=False,
            variants=('steamdeck', 'handheld')
        ),
        expectation='branch1_future_expected',
    ),
    ServerData(
        msg='There isn\'t a linear branches order',
        config=ServerConfig(
            pool_dir='branch4',
            branches=('stable', 'beta', 'rc', 'bc'),
            branches_to_consider={
                'rc': ['stable'],
                'beta': ['stable'],
                'bc': ['stable', 'beta'],
            },
        ),
        expectation='branch4_expected',
    ),
    ServerData(
        msg='There isn\'t a linear branches order',
        config=ServerConfig(
            pool_dir='branch4',
            branches=('stable', 'beta', 'rc', 'bc'),
            branches_to_consider={
                'rc': ['stable'],
                'beta': ['stable'],
                # This is a list of additional branches to consider, the order doesn't matter
                'bc': ['beta', 'stable'],
            },
        ),
        expectation='branch4_expected',
    ),
    ServerData(
        msg='Configuration missing the remote info branches list',
        config=ServerConfig(
            pool_dir='branch4',
            branches=('stable',),
            remote_info_config=RemoteInfoConfig(
                variants=('steamdeck', 'vanilla', 'feature-x'),
            ),
        ),
        expectation='',
        exit_code=1,
    ),
    ServerData(
        msg='Configuration missing the remote info variants list',
        config=ServerConfig(
            pool_dir='branch4',
            branches=('stable',),
            remote_info_config=RemoteInfoConfig(
                branches=('stable', 'beta'),
            ),
        ),
        expectation='',
        exit_code=1,
    ),
]


@contextlib.contextmanager
def cm_chdir(path: Path | str) -> None:
    """Wrapper around os.chdir with context manager"""
    old_cwd = Path.cwd()
    os.chdir(path)

    try:
        yield
    finally:
        os.chdir(old_cwd)


def run_diff(meta_dir: str, expectation: str) -> subprocess.CompletedProcess:
    return subprocess.run(['diff', '-rq', meta_dir,
                           '--exclude', '.lockfile.lock',
                           '--exclude', '*updated.txt',
                          str(EXPECTATION_PARENT / expectation)],
                          check=False,
                          stderr=subprocess.STDOUT,
                          stdout=subprocess.PIPE,
                          text=True)


class StaticServerTestCase(unittest.TestCase):

    # Do not cut out the assertion error diff messages
    maxDiff = None

    @patch('steamosatomupd.utils.DEFAULT_RAUC_CONF', Path.cwd() / 'tests/rauc/system.conf')
    def test_static_server(self):
        # If necessary for debugging, the option `delete=False` can be used to prevent
        # automatic deletion of the temporary directory. Also remember to comment out
        # `images.cleanup()` at the bottom
        images = tempfile.TemporaryDirectory()
        build_image_hierarchy(Path(images.name))

        try:
            from steamosatomupd import staticserver
        except ModuleNotFoundError as e:
            print('\n'.join([
              "Module not found: {}.".format(e),
              "If you're running from the source tree, set the",
              "environment variable IN_SOURCE_TREE and try again.",
            ]), file=sys.stderr)
            sys.exit(1)

        steamos_atomupd_dir = Path.cwd()

        for data in server_data:
            # If necessary for debugging, you can point meta_dir to a specific directory to avoid
            # cleaning it up when the execution ends
            with (
                self.subTest(msg=data.msg),
                tempfile.NamedTemporaryFile(mode='w', buffering=1) as tmp_config,
                tempfile.TemporaryDirectory() as meta_dir
            ):
                config = configparser.RawConfigParser()
                # Preserve case
                config.optionxform = str
                config['Images'] = {'PoolDir': os.path.join(images.name, data.config.pool_dir),
                                    'Unstable': data.config.unstable,
                                    'Products': ' '.join(data.config.products),
                                    'Releases': ' '.join(data.config.releases),
                                    'Variants': ' '.join(data.config.variants),
                                    'Branches': ' '.join(data.config.branches),
                                    'Archs': ' '.join(data.config.archs)}
                if data.config.branches_to_consider is not {}:
                    config['Images.BranchesToConsider'] = {}
                    for branch in data.config.branches_to_consider:
                        config['Images.BranchesToConsider'][branch] = ' '.join(data.config.branches_to_consider[branch])

                if not data.config.strict_pool_validation:
                    # Write it only if set to 'False' to test its default value
                    config['Images']['StrictPoolValidation'] = str(data.config.strict_pool_validation)

                if data.config.remote_info_config.variants or data.config.remote_info_config.branches:
                    config['Images.ProvideRemoteInfoConfig'] = {}
                    config['Images.ProvideRemoteInfoConfig']['Variants'] = ' '.join(data.config.remote_info_config.variants)
                    config['Images.ProvideRemoteInfoConfig']['Branches'] = ' '.join(data.config.remote_info_config.branches)

                if data.config.variants_eol:
                    config['Images']['VariantsEol'] = ' '.join(data.config.variants_eol)

                config.write(tmp_config)

                if data.mock_leftovers:
                    shutil.copytree(data.mock_leftovers, meta_dir, dirs_exist_ok=True)

                updated_path = os.path.join(meta_dir, "steamos-updated.txt")
                daemon: subprocess.Popen | None = None

                if data.run_as_daemon:
                    # We don't grab the output when running as a daemon, so we can't do assumptions
                    # regarding the ndiff
                    self.assertEqual(data.mock_ndiff, None)

                    my_env = os.environ
                    my_env["IN_SOURCE_TREE"] = "True"
                    daemon = subprocess.Popen([sys.executable, steamos_atomupd_dir / 'bin/steamos-atomupd-staticserver', '--run-daemon', '--debug', '--config', tmp_config.name],
                                              env=my_env, cwd=meta_dir)

                    # Give the static server time to set up it's watch, etc.
                    time.sleep(2)

                    if data.exit_code != 0:
                        # Wait for the daemon to terminate with an error
                        self.assertEqual(daemon.wait(timeout=5), data.exit_code)
                        continue

                    trigger_path = os.path.join(images.name, data.config.pool_dir, "steamos", "updated.txt")
                    log.info(f"TEST: Started static server as daemon, triggering file at {trigger_path}")

                    lastmtime = 0
                    if os.path.isfile(updated_path):
                        lastmtime = os.path.getmtime(updated_path)
                    newmtime = lastmtime

                    # Then compare result with expected result since running the daemon should parse the data
                    p = run_diff(meta_dir, data.expectation)
                    self.assertEqual(p.stdout, '')
                    self.assertEqual(p.returncode, 0)

                    # Trigger a new scan by touching the right file
                    open(trigger_path, 'a').close()

                    log.info("TEST: Touched trigger file, waiting for daemon to parse new data")

                    if os.path.isfile(updated_path):
                        newmtime = os.path.getmtime(updated_path)

                    # Now wait for it to indicate it has finished these by watching for updated.txt change
                    while newmtime == lastmtime:
                        time.sleep(1)
                        if os.path.isfile(updated_path):
                            newmtime = os.path.getmtime(updated_path)
                else:
                    args = ['--debug', '--config', tmp_config.name]

                    with self.assertLogs(level=logging.DEBUG) as lo, cm_chdir(meta_dir):
                        if data.exit_code != 0:
                            with self.assertRaises(SystemExit) as se:
                                staticserver.main(args)
                            self.assertEqual(se.exception.code, data.exit_code)
                            continue
                        else:
                            staticserver.main(args)

                    print('\n'.join(lo.output))

                    replaced_files = any(line for line in lo.output if 'Replacing' in line)
                    self.assertEqual(replaced_files, data.replaced_leftovers, replaced_files)

                    unchanged_files = any(line.endswith('has not changed, skipping...') for line in lo.output)
                    self.assertEqual(unchanged_files, data.unchanged_lefovers, unchanged_files)

                    deleted_images = any(line.endswith('with the "skip" option set') for line in lo.output)
                    self.assertEqual(deleted_images, data.removed_image_warning, deleted_images)

                    if data.log_message:
                        self.assertIn(data.log_message, lo.output)

                if data.mock_ndiff:
                    # Assert that the diff between the new files and the leftovers is correctly
                    # printed in output
                    output_string = ''.join(lo.output)
                    for file in data.mock_ndiff.rglob('*.json'):
                        with open(file, 'r', encoding='utf-8') as expected:
                            expected_lines = expected.readlines()
                            differences = ''.join([li.lstrip() for li in expected_lines if not li.startswith('  ')])
                            self.assertIn(differences, output_string)

                # Then compare result with expected result
                p = run_diff(meta_dir, data.expectation)
                self.assertEqual(p.stdout, '')
                self.assertEqual(p.returncode, 0)

                if data.changed_expectation:
                    # Now add some updates
                    build_image_hierarchy(Path(images.name), only_additional_images=True)

                    # Now compare result with previous expectation. since daemon
                    # should not have yet updated any metadata
                    p = run_diff(meta_dir, data.expectation)
                    self.assertEqual(p.stdout, '')
                    self.assertEqual(p.returncode, 0)

                    lastmtime = os.path.getmtime(updated_path)
                    newmtime = lastmtime

                    # Trigger a new scan by touching trigger file again
                    Path(trigger_path).touch()

                    # Wait for server to signal it has finished again by watching for updated.txt change again
                    while newmtime == lastmtime:
                        time.sleep(1)
                        newmtime = os.path.getmtime(updated_path)

                    # Then compare result with expected result
                    p = run_diff(meta_dir, data.changed_expectation)
                    self.assertEqual(p.stdout, '')
                    self.assertEqual(p.returncode, 0)

                if daemon:
                    # Now try to run a second instance and make sure the lockfile prevents it doing anything
                    my_env = os.environ
                    my_env["IN_SOURCE_TREE"] = "True"
                    second_daemon = subprocess.Popen([sys.executable,
                                                      steamos_atomupd_dir / 'bin/steamos-atomupd-staticserver',
                                                      '--run-daemon', '--debug', '--config', tmp_config.name],
                                                     env=my_env, cwd=meta_dir)

                    output = second_daemon.communicate()[0]
                    return_code = second_daemon.returncode

                    # Now make sure it quit as expected
                    self.assertEqual(return_code, 1)

                    log.info("TEST: daemon is running, so killing it")
                    os.kill(daemon.pid, signal.SIGINT)

        images.cleanup()


if __name__ == '__main__':
    # Run static server on test config
    # Compare output with expected results
    unittest.main()
