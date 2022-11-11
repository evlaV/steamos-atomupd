#!/usr/bin/env bash

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

set -eu

if [ "${STEAMOS_ATOMUPD_SKIP_DESYNC-}" = 1 ]; then
    echo "skipping building desync"
else
    export GOPATH=/go
    git clone https://github.com/folbricht/desync.git /tmp/desync
    cd /tmp/desync/cmd/desync
    # Latest commit on master, bump if necessary
    git checkout b54576813acfc9718fce77a30eb05f878a157f89
    go install
    cp /go/bin/desync /usr/bin/desync
    cd -
    rm -rf /tmp/desync
fi

if [ "${STEAMOS_ATOMUPD_SKIP_RAUC-}" = 1 ]; then
    echo "skipping building rauc"
else
    # We need at least RAUC 1.7
    # Once it hits the Debian repositories, just install that instead
    git clone https://github.com/rauc/rauc.git /tmp/rauc
    cd /tmp/rauc
    # RAUC v1.7 tag
    git checkout a0974f4eda3dd0938587c2b5d6026f2cc45cc361
    ./autogen.sh
    ./configure --prefix=/usr
    make
    make install
    cd -
    rm -rf /tmp/rauc
fi
