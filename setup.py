#!/usr/bin/env python

# SPDX-License-Identifier: LGPL-2.1+

from distutils.core import setup

setup(name='SteamOS Atomic Updater',
      version='0.20190711.0',
      description='SteamOS Atomic Update - Python library that is used by both the client and the server.',
      long_description=open('README.md', 'r').read(),
      author='Arnaud Rebillout',
      author_email='arnaud.rebillout@collabora.com',
      url='https://store.steampowered.com/steamos/',
      license='LGPL-2.1',
      packages=['steamosatomupd'],
     )
