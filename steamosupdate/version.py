# SPDX-License-Identifier: LGPL-2.1+
#
# Copyright © 2018 Collabora Ltd
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

# A version is associated to an image.
#
# Under the hood, two different, non-compatible version schemes are supported:
# semantic versions and date-based versions.
#
# Released images are expected to come with semantic versioning:
#   3.0, 3.1-rc2        ie. MAJOR[.MINOR][.MICRO][-WHATEVER][+BUILD]
#
# Daily images are expected to come with date-based versioning:
#   20181105.1          ie. DATE.INCREMENT

from datetime import datetime
import semantic_version

class SemanticVersion(semantic_version.Version):

    def is_unstable(self):
        return not self.prerelease is None

class DateBasedVersion:

    def __init__(self, text):

        self.date = None
        self.inc = 0

        fields = text.split('.')
        if len(fields) == 2 and len(fields[0]) == 8:
            # This will raise ValueError if need be
            date = datetime.strptime(fields[0], '%Y%m%d')
            inc = int(fields[1])
        else:
            raise ValueError("the version string should be something like YYYYMMDD.N")

        self.date = date
        self.inc = inc

    def __eq__(self, other):
        return ((self.date, self.inc) == (other.date, other.inc))

    def __ne__(self, other):
        return ((self.date, self.inc) != (other.date, other.inc))

    def __lt__(self, other):
        return ((self.date, self.inc) <  (other.date, other.inc))

    def __le__(self, other):
        return ((self.date, self.inc) <= (other.date, other.inc))

    def __gt__(self, other):
        return ((self.date, self.inc) >  (other.date, other.inc))

    def __ge__(self, other):
        return ((self.date, self.inc) >= (other.date, other.inc))

    def __str__(self):
        return "{}.{}".format(self.date.strftime('%Y%m%d'), self.inc)

    def is_unstable(self):
        # 'unstable' doesn't exist in our date-based versioning scheme,
        # every version is 'stable' :)
        return False

VERSIONING_SCHEMES = {
    'date-based': DateBasedVersion,
    'semantic'  : SemanticVersion,
}

def parse_string(version_string, versioning_scheme):

    """Make a version object out of a version string.
    """

    avail = None

    if versioning_scheme in VERSIONING_SCHEMES:
        cls = VERSIONING_SCHEMES[versioning_scheme]
        obj = cls(version_string) # raise value error if need be
        return obj

    elif versioning_scheme == 'guess':
        # Try versioning schemes in the following order
        schemes = [ 'date-based', 'semantic' ]
        for s in schemes:
            assert s in VERSIONING_SCHEMES
            cls = VERSIONING_SCHEMES[s]
            try:
                obj = cls(version_string)
                return obj
            except ValueError:
                continue

        raise ValueError("invalid version: {}".format(version_string))

    else:
        raise ValueError("invalid versioning scheme: {}".format(versioning_scheme))
