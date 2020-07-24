#!/bin/bash
# -*- mode: sh; indent-tabs-mode: nil; sh-basic-offset: 4; -*-
# vim: et sts=4 sw=4

#  SPDX-License-Identifier: LGPL-2.1+
#
#  Copyright © 2020 Collabora Ltd.
#
#  This file is part of steamos-atomupd.
#
#  steamos-atomupd is free software; you can redistribute it and/or modify it
#  under the terms of the GNU Lesser General Public License as published by the
#  Free Software Foundation; either version 2.1 of the License, or (at your
#  option) any later version.

set -e
set -u

progress() {
    if plymouth --ping 2>/dev/null
    then
        plymouth system-update --progress "$1"
    fi
    echo "$1%"
}

while [[ "$#" -ne 0 ]]
do
    if [[ "$1" =~ ^(-h|--help)$ ]]
    then
        echo "Usage: ${0##*/} [-h|--help] [--debug]"
        exit 0
    elif [[ "$1" == "--debug" ]]
    then
        debug=true
    else
        echo "$1: Invalid argument" >&2
        exit 1
    fi
    shift
done

while read -r -a words
do
    # Empty line: skip it!
    if [[ "${#words[@]}" -eq 0 ]]
    then
        continue
    fi

    # Print the journal to stderr
    if [[ "${debug:-}" ]]
    then
        echo "${words[@]}" >&2
    fi

    # Slot needs to be updated with /run/rauc/bundle/*.img.caibx
    if [[ "${words[0]}" =~ "Slot" ]]
    then
        slot="${words[6]##*/}"
        slot="${slot%*.img.caibx}"
    # Seeding... ##%
    elif [[ "${words[0]}" =~ "seeding" ]] && [[ "${slot:-}" == "rootfs" ]]
    then
        if [[ "${words[1]}" =~ [0-9]+%$ ]]
        then
            percentage="${words[1]%\%}"
            percentage="$(((percentage*25*90/100)/100))"
            percentage="$((percentage+5))"
            progress "$percentage" "${words[@]}"
        fi
    # Downloading chunks ##%
    elif [[ "${words[0]}" == "downloading" ]] && [[ "${slot:-}" == "rootfs" ]]
    then
        if [[ "${words[2]}" =~ [0-9]+%$ ]]
        then
            percentage="${words[2]%\%}"
            percentage="$(((percentage*75*90/100)/100))"
            percentage="$((percentage+5+(25*90/100)))"
            progress "$percentage" "${words[@]}"
        fi
    # installing: ...: All slots updated
    elif [[ "${words[0]}" == "installing" ]] &&
         [[ "${words[*]:2}" == "All slots updated" ]]
    then
        percentage="95"
        progress "$percentage" "${words[@]}"
    # installing: ...: finished
    elif [[ "${words[0]}" == "installing" ]] &&
         [[ "${words[*]:2}" == "finished" ]]
    then
        percentage="99"
        progress "$percentage" "${words[@]}"
    # installing: ...: started
    elif [[ "${words[0]}" == "installing" ]] &&
         [[ "${words[*]:2}" == "started" ]]
    then
        if plymouth --ping 2>/dev/null
        then
            plymouth change-mode --system-upgrade
            percentage="0"
            progress "$percentage" "${words[@]}"
        fi
    # installing: ...: failed: ...
    elif [[ "${words[0]}" == "installing" ]] &&
         [[ "${words[*]:2}" =~ "failed: " ]]
    then
        if plymouth --ping 2>/dev/null
        then
            plymouth change-mode --boot-up
            plymouth display-message --text="Error: System upgrade failed!"
        fi
    # installing: ...: succeeded
    elif [[ "${words[0]}" == "installing" ]] &&
         [[ "${words[*]:2}" == "succeeded" ]]
    then
        percentage="100"
        progress "$percentage" "${words[@]}"
        if plymouth --ping 2>/dev/null
        then
            plymouth change-mode --boot-up
            plymouth display-message --text="System upgrade completed!"
        fi
    # Stopped Rauc Update Service.
    elif [[ "${words[*]}" == "Stopped Rauc Update Service." ]]
    then
        if plymouth --ping 2>/dev/null
        then
            plymouth change-mode --boot-up
            plymouth display-message --text=
        fi
    # Started Rauc Update Service.
    elif [[ "${words[*]}" == "Started Rauc Update Service." ]]
    then
        if plymouth --ping 2>/dev/null
        then
            plymouth change-mode --system-upgrade
            percentage="0"
            progress "$percentage" "${words[@]}"
        fi
    fi
done < <(journalctl --unit rauc.service --follow --output cat)
