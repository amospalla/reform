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

set -eu

# Ask mleds where its socket is.
SOCKET="$(mleds path socket)"

get_next_frame() {
    # Generate and play a single frame where there is a rectangle with a given value.
    echo "
            action=add_movie
            name=test1_movie
            copy_movie=blank
            rectangle=0 0 12 5 #ff0000 #00ff00 ${direction} false ${value}
            end=true

            action=play_movie
            name=test1_movie
            priority=background
            end=true
        "
}

get_all_frames() {
    local direction
    local value

    for direction in "up" "down" "left" "right"; do
        for ((value = 0; value <= 100; value += 5)); do
            get_next_frame "${direction}" "${value}"
            sleep 0.02
        done
        for ((value = 100; value >= 0; value -= 5)); do
            get_next_frame "${direction}" "${value}"
            sleep 0.02
        done
    done

    # Ask the server to close the connection.
    echo "action=disconnect"
    echo "end=true"
}

main() {
    # Using netcat.
    get_all_frames | nc -U "${SOCKET}"

    # Using socat.
    # get_all_frames | socat - "UNIX-CONNECT:${SOCKET}"
}

main "${@}"
