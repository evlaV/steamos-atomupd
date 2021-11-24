#!/bin/sh
# Copyright 2021 Collabora Ltd
# SPDX-License-Identifier: MIT

set -eu

export DEBIAN_FRONTEND=noninteractive
apt-get -y update >&2
apt-get -y install git >&2

if [ -n "${CI_COMMIT_TAG-}" ]; then
    VERSION="${CI_COMMIT_TAG}"
else
    VERSION="$(git describe --long --tags || echo unknown)"
fi
echo "${VERSION#v}"
