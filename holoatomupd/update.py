# SPDX-License-Identifier: LGPL-2.1+
#
# Copyright © 2018-2026 Collabora Ltd
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

# Needed until PEP 563 string-based annotations is not enabled by default
# (scheduled for Python 3.13)
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from holoatomupd.image import Image, BuildId, Version
from holoatomupd.utils import parse_lwc_exempts


class UpdateType(Enum):
    """
    Used to select which type of update we are looking for
    """

    standard = auto()
    """ The canonical update """
    forced = auto()
    """ The update should be forced, even if that results in a downgrade """
    unexpected_buildid = auto()
    """
    The image buildid should not be taken into consideration, this is used to
    generate generic fallback updates
    """
    second_last = auto()
    """
    We don't want the latest update, but instead the penultimate. This option implies
    'unexpected_buildid'.
    """

    def is_fallback(self) -> bool:
        """
        Check if the provided update_type is a fallback. I.e. a generic update that shouldn't
        take into consideration the origin image build ID nor its variant.
        """
        return self in (UpdateType.unexpected_buildid, UpdateType.second_last)


@dataclass
class UpdateCandidate:
    """An update candidate

    An update candidate is simply an image with an update path.
    If this is a lightweight checkpoint, we also store the eventual exempt images list.
    """

    image: Image
    update_path: str
    exempts: list[tuple[Version, BuildId]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UpdateCandidate:
        """Create an UpdateCandidate from a dictionary

        Raise exceptions if the dictionary doesn't contain the expected keys,
        or if values are not valid.
        """

        image = Image.from_dict(data['image'])
        update_path = data['update_path']

        # This is not a required field. If this candidate is not a lightweight checkpoint,
        # there will be no "exempts from" images
        exempts_data = data.get('exempt_from', [])
        exempts = parse_lwc_exempts(exempts_data)

        return cls(image, update_path, exempts)

    def to_dict(self, update_type=UpdateType.standard) -> dict[str, Any]:
        """Export an UpdateCandidate to a dictionary"""
        return {
            'image': self.image.to_dict(),
            'update_path': self.update_path,
            **(
                # Write the exempt section only if we actually have an exempt list for
                # lightweight checkpoints (lwc), and only if this is a fallback update.
                # If it is a canonical update, and we have a lwc, there is no need to send
                # the exempt info to the clients. We already know from the server side that
                # the lwc is needed.
                {'exempt_from': [f"{v}:{b}" for v, b in self.exempts]}
                if self.exempts and update_type.is_fallback() else {}
            )
        }

    def __repr__(self) -> str:
        return "{}, {}".format(self.image, self.update_path)


class UpdatePath:

    """An update path

    An update path is a list of update candidates, sorted. It's created for
    a particular image, and it represents all the updates that this image
    should apply in order to be up-to-date.

    An update path can be imported/exported as a dictionary:

      {
        'minor': {
          'release': 'holo',
          'candidates': [ CANDIDATE1, CANDIDATE2, ... ]
        }
      }
    """

    def __init__(self, release: str, replacement_eol_variant: str, candidates: list[UpdateCandidate],
                 update_type=UpdateType.standard):
        self.release = release
        self.replacement_eol_variant = replacement_eol_variant
        self.candidates = []
        self.update_type = update_type

        if not candidates:
            return

        self.candidates = sorted(candidates, key=lambda c: c.image)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UpdatePath:
        """Create an UpdatePath from a dictionary

        Raise exceptions if the dictionary doesn't contain the expected keys,
        or if values are not valid.
        """

        # We expect the UpdatePath to be under the "minor" key for legacy reasons
        data = data.get('minor', data)
        release = data['release']
        replacement_eol_variant = data.get('replacement_eol_variant', '')
        candidates = []

        for cdata in data['candidates']:
            candidate = UpdateCandidate.from_dict(cdata)
            candidates.append(candidate)

        return cls(release, replacement_eol_variant, candidates)

    def to_dict(self) -> dict[str, Any]:
        """Export an UpdatePath to a dictionary"""

        data = {}
        array = []
        for candidate in self.candidates:
            cdata = candidate.to_dict(self.update_type)
            array.append(cdata)

        # For legacy reasons we need to wrap the list of update candidates around "minor".
        # Initially the update system was designed with support for both "minor" and "major"
        # upgrades. However, that design has been deprecated in favor of gating major upgrades
        # behind checkpoints.
        data['minor'] = {'release': self.release, 'candidates': array}
        if self.replacement_eol_variant:
            data['minor']['replacement_eol_variant'] = self.replacement_eol_variant

        return data
