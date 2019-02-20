# SPDX-License-Identifier: LGPL-2.1+

service = 'steamos-atomupd-server@.service'

service_conf = configuration_data()
service_conf.set('bindir', bindir)

configure_file(
  input: service + '.in',
  output: service,
  configuration: service_conf,
  install_dir: systemdunitdir,
)
