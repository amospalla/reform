# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025 Jordi Marqués <jordi.amospalla.es>
#
# This file is part of simple-menu.
#
# simple-menu is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# simple-menu is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# simple-menu. If not, see <https://www.gnu.org/licenses/>.

from typing import Literal

PROGRAM_NAME = "simple-menu"
PROGRAM_VERSION = "0.0.1"

TOKEN_SEPARATORS = [
    "::",  # First level
    ",,",  # Second level
    ";;",  # Third level
]

QUIT_EXIT_CODE = 250

interface_t = Literal[
    "fzf",
    "rofi",
]

interface_choices = (
    "auto",
    "fzf",
    "rofi",
)


text_substitutions = {
    "<ok>": "✓",  # ✓ 
    "<paused>": "",
    "<stopped>": "󰓛",  #   󰓛
    "<error>": "✖",
    "<warning>": "",  # 
    "<running>": "",  #   
    "<playing>": "󰝚",  #   󰝚
    "<recording>": "󰻂",
    "<microphone>": "󰍬",
    "<microphone-muted>": "󰍭",
    "<volume-min>": "󰕿",
    "<volume-med>": "󰖀",
    "<volume-max>": "󰕾",
    "<volume-muted>": "󰖁",
    "<upper>": "",
    "<lower>": "",
    "<poweroff>": "⏻",
    "<reload>": "",
    "<speaker>": "󰓃",
    "<speaker-muted>": "󰓄",
    "<configuration>": "",
    "<change>": "",
    "<folder>": "",
    "<menu>": "",  # Used by menu
    "<action>": "󱐋",  # Used by menu
    "<notification>": "",  # Used by menu
}
