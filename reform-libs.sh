#!/usr/bin/env bash

# Copyright (c) 2024 Jordi Marqués
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

declare -g __return
declare -g -a __return_array

declare -g -a models=(
    "MNT Pocket Reform with i.MX8MP Module"
)

declare -g -A model_hidraws=(
    ["MNT Pocket Reform with i.MX8MP Module"]="MNT Pocket Reform Input"
)

hidraw_locate() {
    # Return the name of the hidraw device under /dev or returns exit code 1.
    #
    # Example:
    #     set __return to "hidraw0"
    local device
    local model
    local text

    get_model && model="${__return}"

    if [[ -d /sys/class/hidraw ]]; then

        cd /sys/class/hidraw || return 1
        for device in *; do
            if [[ -f "${device}/device/uevent" ]]; then
                readarray text <"${device}/device/uevent"
                if [[ "${text[*]}" == *"${model_hidraws["${model}"]}"* ]]; then
                    __return="/dev/${device}"
                    cd - >/dev/null || return 1
                    return 0
                fi
            fi
        done
        cd - >/dev/null || return 1

    fi
    return 1
}

hidraw_leds_set() {
    # Set keyboard leds colour.
    #
    # Args:
    #     hidraw_device(str): path to the hidraw device.
    #     r(int): green colour, range 0-255.
    #     g(int): green colour, range 0-255.
    #     b(int): green colour, range 0-255.
    #
    # Example:
    #     hidraw_leds_set /dev/hidraw0 10 0 255
    local hidraw_device
    local r g b
    hidraw_device="${1}"
    # Get hexadecimal from decimal
    printf -v r "%02x" "${2}"
    printf -v g "%02x" "${3}"
    printf -v b "%02x" "${4}"

    # TODO this "0a" makes printf fail
    if [[ "${g}" == "0a" ]]; then
        g="0b"
    fi
    # shellcheck disable=SC2059
    printf "xLRGB\x${b}\x${g}\x${r}" >"${hidraw_device}"
}

hidraw_leds_transition() {
    # Set leds transitioning from a start state to an end state.
    #
    # Args:
    #     hidraw_device(sr): path to the device.
    #     r1(int): start red colour, range 0-255.
    #     g1(int): start green colour, range 0-255.
    #     b1(int): start blue colour, range 0-255.
    #     r2(int): end red colour, range 0-255.
    #     g2(int): end green colour, range 0-255.
    #     b2(int): end blue colour, range 0-255.
    #     steps(int): transition steps.
    #     wait(int): time to wait between two steps (seconds)
    #
    # Example:
    #     hidraw_leds_transition /dev/hidraw0   0 0 64   0 0 128  10 10
    local hidraw_device wait
    local -i r1 g1 b1 r2 g2 b2 steps step
    hidraw_device="${1}"
    r1="${2}" g1="${3}" b1="${4}" r2="${5}" g2="${6}" b2="${7}"
    steps="${8}" wait="${9}"

    for ((step = 1; step <= steps; step++)); do
        hidraw_leds_set \
            "${hidraw_device}" \
            "$((r1 + (r2 - r1) * step / steps))" \
            "$((g1 + (g2 - g1) * step / steps))" \
            "$((b1 + (b2 - b1) * step / steps))"
        sleep "${wait}"
    done
}

battery_capacity_get() {
    # Return the remaining capacity in percentage (integer).
    # shellcheck disable=SC2154
    read -r __return <"/sys/class/power_supply/${battery_name}/capacity"
}

get_model() {
    # Return the computer model on __return variable.
    #
    # Examples:
    #     "MNT Pocket Reform with i.MX8MP Module"
    local text
    read -r -d "" text </proc/device-tree/model
    __return="${text}"
}
