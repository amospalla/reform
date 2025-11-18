#!/usr/bin/env bash

# Copyright (c) 2025 Jordi Marqués
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


# This script monitors cpu and memory usage (using vmstat).

# The first keyboard row is filled, from left to right, with the cpu usage,
# the third row is filled with the memory usage.
#
# It plays on background priority.

set -eu

# Ask mleds where its socket is.
SOCKET="$(mleds show_socket)"

send_message() {
    # Using netcat
    echo "${1}" | nc -U "${SOCKET}"

    # Using socat
    # echo "${1}" | socat - "UNIX-CONNECT:${SOCKET}"
}

main() {
    local line
    local -a tokens
    local -i cpu_used mem_used
    local -i mem_total
    local -i interval
    local color_cpu_min
    local color_cpu_max
    local color_mem_min
    local color_mem_max
    local fill="false"

    interval=2
    color_cpu_min="#0a0500"
    color_cpu_max="#400000"
    color_mem_min="#010204"
    color_mem_max="#1a2373"

    mem_total="$(grep MemTotal /proc/meminfo | awk '{print $2}')"

    vmstat "${interval}" --one-header --no-first | while read -r line; do
        IFS=" " read -r -a tokens <<<"${line}"
        [[ "${#tokens[@]}" -eq 18 ]] || continue # skip header
        if [[ "${tokens[14]}" == "id" ]]; then   # skip header
            continue
        fi
        cpu_used="$((100 - ${tokens[14]}))"
        mem_used=$(((mem_total - ${tokens[3]} - ${tokens[4]} - ${tokens[5]}) * 100 / mem_total))

        # First rectangle shows cpu and takes the first column. Starts at x=0,y=0, and
        # has a size of 12x1 pixels. It shows from left to right.
        #
        # The second rectangle is shown on the third row keyboard and shows memory
        # usage.
        send_message "
            action=add_movie
            name=system_monitor
            copy_movie=blank
            times=3
            rectangle=0 0 12 1 ${color_cpu_min} ${color_cpu_max} right ${fill} ${cpu_used}
            rectangle=0 2 12 1 ${color_mem_min} ${color_mem_max} right ${fill} ${mem_used}
            end=true

            action=play_movie
            name=system_monitor
            priority=background
            end=true
            
            action=disconnect
            end=true
        "
    done
}

main "${@}"
