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

# Toggle keypresses client

set -eu

if mleds status | grep -q "running_client: keypresses"; then
    echo "Keypresses is running, stop it."
    mleds stop_client keypresses
else
    echo "Keypresses is stopped, start it."
    mleds run_client keypresses
fi
