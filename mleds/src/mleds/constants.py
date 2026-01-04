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

import enum

PROGRAM_NAME = "mleds"
HEX_COLOR_LENGTH = 6
KEYBOARD_ROWS = 6
KEYBOARD_COLUMNS = 12
PIXELS_PER_FRAME = KEYBOARD_COLUMNS * KEYBOARD_ROWS
COLOR_BLACK = [0, 0, 0]
COLOR_WHITE = [255, 255, 255]
NO_TIMEOUT = 0.0
TIMEOUT_DISABLE = -1.0
DEFAULT_FRAME_DURATION = NO_TIMEOUT
PROGRAM_VERSION = "0.0.2"


class Priority(enum.StrEnum):
    background = "background"
    foreground = "foreground"
    urgent = "urgent"
