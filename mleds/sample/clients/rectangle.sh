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

declare message

# Write a rectangle
# Usage: rectangle.sh x y width height direction fill value time
#
# Example:
#     $ ./rectangle.sh 1 1 10 3 "#0f2808" "#aaff0a" right false 100 2 urgent
#
#     print a rectangle:
#         Starting at position 1,1.
#         Sith width and height 10x3.
#         Sith a gradient using the specified start and end colors, direction and
#         percentage. Paint only the borders, do not fill.
#         During 2 seconds, on the urgent priority.
message="
    action=add_movie
    name=rectangle
    copy_movie=blank
    times=${10}
    rectangle=${1} ${2} ${3} ${4} ${5} ${6} ${7} ${8} ${9}
    end=true

    action=play_movie
    name=rectangle
    priority=${11}
    end=true

    action=disconnect
    end=true
"
echo "${message}" | nc -U "${SOCKET}"
