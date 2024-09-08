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

declare -g -a __return_array
declare -g __return
declare -g __rl_battery_name
declare -g __rl_computer_model
declare -g __rl_hidraw_device
declare -g __rl_input_device_keyboard
declare -g -a models
declare -g -A model_hidraws
declare -g -A model_input_device_keyboards
declare -g -A model_battery_names
declare -g -A model_gpu_scheduler_paths

# shellcheck disable=SC2034
models=(
    "MNT Pocket Reform with i.MX8MP Module"
)

model_hidraws=(
    ["MNT Pocket Reform with i.MX8MP Module"]="MNT Pocket Reform Input"
)

model_input_device_keyboards=(
    ["MNT Pocket Reform with i.MX8MP Module"]="/dev/input/by-id/usb-MNT_Pocket_Reform_Input_RP2040-event-kbd"
)

model_battery_names=(
    ["MNT Pocket Reform with i.MX8MP Module"]="BAT0"
)

model_gpu_scheduler_paths=(
    ["MNT Pocket Reform with i.MX8MP Module"]="/sys/devices/platform/soc@0/32700000.interconnect/devfreq/32700000.interconnect"
)

computer_model_get() {
    # Return the computer model on __return variable.
    #
    # Examples:
    #     "MNT Pocket Reform with i.MX8MP Module"
    local text
    if [[ -n "${__rl_computer_model:-}" ]]; then
        true # cached
    else
        read -r -d "" text </proc/device-tree/model
        __rl_computer_model="${text}"
    fi
    __return="${__rl_computer_model}"
}

hidraw_device_get() {
    # Return the name of the hidraw device under /dev or returns exit code 1.
    # This function is cached.
    #
    # Example:
    #     set __return to "hidraw0"
    local device
    local computer_model
    local text

    if [[ -n "${__rl_hidraw_device:-}" ]]; then
        __return="${__rl_hidraw_device}" # cached
        return 0
    fi

    while :; do
        computer_model_get && computer_model="${__return}"

        if [[ -d /sys/class/hidraw ]]; then

            cd /sys/class/hidraw || return 1
            for device in *; do
                if [[ -f "${device}/device/uevent" ]]; then
                    readarray text <"${device}/device/uevent"
                    if [[ "${text[*]}" == *"${model_hidraws["${computer_model}"]}"* ]]; then
                        cd - >/dev/null || return 1
                        __rl_hidraw_device="/dev/${device}"
                        __return="/dev/${device}"
                        return 0
                    fi
                fi
            done
            cd - >/dev/null || return 1

        fi
        echo "Waiting for hidraw device to be up ..."
        sleep 1
    done
}

hidraw_leds_set() {
    # Set keyboard leds colour.
    #
    # Args:
    #     r(int): green colour, range 0-255.
    #     g(int): green colour, range 0-255.
    #     b(int): green colour, range 0-255.
    #
    # Example:
    #     hidraw_leds_set 10 0 255
    local hidraw_device
    local r g b
    hidraw_device_get && hidraw_device="${__return}"
    # Get hexadecimal from decimal
    printf -v r "%02x" "${1}"
    printf -v g "%02x" "${2}"
    printf -v b "%02x" "${3}"

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
    #     hidraw_leds_transition 0 0 64   0 0 128  10 10
    local wait
    local -i r1 g1 b1 r2 g2 b2 steps step
    r1="${1}" g1="${2}" b1="${3}" r2="${4}" g2="${5}" b2="${6}" steps="${7}" wait="${8}"

    for ((step = 1; step <= steps; step++)); do
        hidraw_leds_set \
            "$((r1 + (r2 - r1) * step / steps))" \
            "$((g1 + (g2 - g1) * step / steps))" \
            "$((b1 + (b2 - b1) * step / steps))"
        sleep "${wait}"
    done
}

battery_name_get() {
    # Return the battery for this computer model
    #
    # Example:
    #     BAT0
    local computer_model
    if [[ -n "${__rl_battery_name:-}" ]]; then
        true # cached
    else
        computer_model_get && computer_model="${__return}"
        __rl_battery_name="${model_battery_names["${computer_model}"]}"

        while ! [[ -d "/sys/class/power_supply/${__rl_battery_name}" ]]; do
            echo "Waiting for Reform battery to be up..."
            sleep 1
        done
    fi
    __return="${__rl_battery_name}"
}

battery_capacity_get() {
    # Return the remaining capacity in percentage (integer).
    # shellcheck disable=SC2154
    local battery_name

    battery_name_get && battery_name="${__return}"
    read -r __return <"/sys/class/power_supply/${battery_name}/capacity"
}

input_device_keyboard_get() {
    # Return the computer input device on /dev/input/by-id/...
    #
    # Example:
    #     /dev/input/by-id/usb-MNT_Pocket_Reform_Input_RP2040-event-kbd
    local computer_model
    if [[ -n "${__rl_input_device_keyboard:-}" ]]; then
        true # cached
    else
        computer_model_get && computer_model="${__return}"
        __rl_input_device_keyboard="${model_input_device_keyboards["${computer_model}"]}"

        while ! [[ -e "${__rl_input_device_keyboard}" ]]; do
            echo "Waiting for Reform keyboard input device device to be up..."
            sleep 1
        done
    fi
    __return="${__rl_input_device_keyboard}"
}

gpu_frequency_get() {
    local model

    computer_model_get && model="${__return}"
    read -r __return <"${model_gpu_scheduler_paths["${model}"]}/cur_freq"
}

gpu_frequency_set() {
    local -i frequency
    local model

    frequency="${1}"
    computer_model_get && model="${__return}"

    case "${frequency}" in
        "200000000")
            echo "200000000" >"${model_gpu_scheduler_paths["${model}"]}/min_freq"
            echo "200000000" >"${model_gpu_scheduler_paths["${model}"]}/max_freq"
            echo "1000000000" >"${model_gpu_scheduler_paths["${model}"]}/max_freq"
            ;;
        "1000000000")
            echo "1000000000" >"${model_gpu_scheduler_paths["${model}"]}/min_freq"
            echo "1000000000" >"${model_gpu_scheduler_paths["${model}"]}/max_freq"
            echo "200000000" >"${model_gpu_scheduler_paths["${model}"]}/min_freq"
            ;;
    esac
}
