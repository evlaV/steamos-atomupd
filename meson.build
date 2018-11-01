# SPDX-License-Identifier: LGPL-2.1+

project('steamos-update',
  version: '0.1',
  license: 'LGPLv2.1+',
)

prefix = get_option('prefix')
bindir = join_paths(prefix, get_option('bindir'))
datadir = join_paths(prefix, get_option('datadir'))
moduledir = join_paths(prefix, 'lib', 'python3', 'dist-packages')

install_subdir('steamosupdate', install_dir: moduledir)

subdir('bin')
