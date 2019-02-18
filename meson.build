# SPDX-License-Identifier: LGPL-2.1+

project('steamos-update',
  version: '0.1',
  license: 'LGPLv2.1+',
)

prefix = get_option('prefix')
bindir = join_paths(prefix, get_option('bindir'))
datadir = join_paths(prefix, get_option('datadir'))
moduledir = join_paths(prefix, 'lib', 'python3', 'dist-packages')
systemdunitdir = join_paths(prefix, 'lib', 'systemd', 'system')

install_subdir('steamosupdate', install_dir: moduledir)

python = find_program('python3', required: false)
test('Unit tests', python,
  args: ['-m', 'unittest', '-v'],
  workdir: meson.current_source_dir(),
)

subdir('bin')
subdir('data')
