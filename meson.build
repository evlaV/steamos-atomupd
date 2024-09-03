# SPDX-License-Identifier: LGPL-2.1+

project('steamos-atomupd',
  version: '0.1',
  license: 'LGPLv2.1+',
)

prefix = get_option('prefix')
bindir = join_paths(prefix, get_option('bindir'))
datadir = join_paths(prefix, get_option('datadir'))
moduledir = join_paths(prefix, 'lib', 'python3', 'dist-packages')
completionsdir = join_paths(prefix, get_option('datadir'), 'bash-completion', 'completions')
systemdunitdir = join_paths(prefix, 'lib', 'systemd', 'system')

install_subdir('steamosatomupd',
  exclude_directories: ['__pycache__'],
  install_dir: moduledir,
)

install_subdir('completions',
  install_dir: completionsdir,
)

python = find_program('python3', required: false)

if get_option('tests_coverage')
    unit_args = ['-m', 'coverage', 'run', '-m', 'unittest', '-v']
else
    unit_args = ['-m', 'unittest', '-v']
endif

test('Unit tests', python,
  args: unit_args,
  workdir: meson.current_source_dir(),
)

subdir('bin')
subdir('data')
