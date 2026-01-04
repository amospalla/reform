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

import asyncio
import logging
from typing import TypedDict

from mleds.clients.base import Client
from mleds.constants import KEYBOARD_COLUMNS, KEYBOARD_ROWS, Priority
from mleds.read_keyboard import InputEventGenerator, evdev_events

MOVIE_NAME = "hidden_keypresses"
FRAME_TIME = 0.05
IDLE_STATE = 6

keyboard_event = asyncio.Event()
EVDEV_VALUE_HOLD = 2
EVDEV_ETYPE_KEYBOARD = 1

logger = logging.getLogger(__name__)


class Colors(TypedDict):
    color: list[int]
    next: int


class KeyPresses(Client):
    def __init__(self, *args, **kwargs) -> None:  # type:ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        type(self).priority = Priority[self.configuration.keypresses_priority]
        self.keys = [Key() for _ in range(KEYBOARD_COLUMNS * KEYBOARD_ROWS)]
        self.key_mappings: dict[str, list[Key]] = {}

        for index, key_symbols in enumerate(
            self.configuration.keypresses_keyboard_layout,
        ):
            for key_symbol in [value.upper() for value in key_symbols.split()]:
                if key_symbol == "UNSET":
                    continue
                self.key_mappings.setdefault(f"KEY_{key_symbol}", []).append(
                    self.keys[index],
                )

    async def run(self) -> None:
        await asyncio.gather(
            self.read_input_events(),
            self.update_matrix(),
        )

    async def read_input_events(self) -> None:
        logger.info("read_input_events(): Started.")

        async for _sec, _usec, etype, code, value in InputEventGenerator(
            self.configuration.keyboard_device,
        ):
            if etype == EVDEV_ETYPE_KEYBOARD and value != EVDEV_VALUE_HOLD:
                self.new_event(evdev_events[1][code], value)

    async def update_matrix(self) -> None:
        logger.info("KeyPresses.update_matrix(): Started")
        skip = True
        while True:
            if not skip:
                await self.send_message(message=self.next_message())
                self.update_key_colors()

            if skip:
                skip = False
                await keyboard_event.wait()
                keyboard_event.clear()
            else:
                try:
                    await asyncio.wait_for(
                        keyboard_event.wait(),
                        timeout=FRAME_TIME,
                    )
                    keyboard_event.clear()
                except TimeoutError:
                    if all(
                        (
                            key.colors_from is colors_depressed
                            or key.colors_from is colors_depressed_mods
                        )
                        and key.state == IDLE_STATE
                        for key in self.keys
                    ):
                        skip = True

    def update_key_colors(self) -> None:
        for key in self.keys:
            next_state_number = key.colors_from[key.state]["next"]  # type:ignore[literal-required]
            key.state = next_state_number
            key.color = key.colors_from[next_state_number]["color"]  # type:ignore[literal-required]

    def new_event(self, key_symbol: str, value: int) -> None:
        if key_symbol in self.key_mappings:
            for key in self.key_mappings[key_symbol]:
                key.new_event(key_symbol in MODS, value)
            keyboard_event.set()

    def next_message(self) -> list[str]:
        colors = " ".join(
            [
                f"#{key.color[0]:02X}{key.color[1]:02X}{key.color[2]:02X}"
                for key in self.keys
            ],
        )

        return [
            f"action=add_movie name={MOVIE_NAME} create_frames=true times=1.5 pixels=",
            colors,
            "end=true",
            f"action=play_movie name={MOVIE_NAME}",
            f"priority={self.configuration.keypresses_priority}",
            "end=true",
        ]


class Key:
    def __init__(self) -> None:
        self.colors_from = colors_depressed
        self.pressed = False
        self.state: int = IDLE_STATE
        self.color: list[int] = [0, 0, 0]
        self.is_mod = False

    def new_event(self, is_mod: bool, new_event: int | bool | None = None) -> None:
        if new_event is None:
            # If no new event is notified, means this key keeps the previous event,
            # either pressed or depressed.
            new_event = self.state

        if self.pressed and not new_event:
            if is_mod:
                self.colors_from = colors_depressed_mods
            else:
                self.colors_from = colors_depressed
            self.state = -1
            self.pressed = False
        elif not self.pressed and new_event:
            if is_mod:
                self.colors_from = colors_pressed_mods
            else:
                self.colors_from = colors_pressed

            self.state = -1
            self.pressed = True


colors_pressed: Colors = {
    -1: {"color": [0, 0, 0], "next": 0},  # type:ignore[misc]
    0: {"color": [40, 100, 0], "next": 1},
    1: {"color": [30, 100, 0], "next": 2},
    2: {"color": [20, 100, 0], "next": 3},
    3: {"color": [10, 100, 0], "next": 4},
    4: {"color": [0, 130, 20], "next": 5},
    5: {"color": [0, 110, 20], "next": 6},
    6: {"color": [0, 90, 20], "next": 7},
    7: {"color": [0, 70, 20], "next": 8},
    8: {"color": [0, 50, 0], "next": 9},
    9: {"color": [0, 40, 0], "next": 10},
    10: {"color": [0, 50, 0], "next": 11},
    11: {"color": [0, 70, 20], "next": 12},
    12: {"color": [0, 90, 20], "next": 13},
    13: {"color": [0, 110, 20], "next": 14},
    14: {"color": [0, 130, 40], "next": 15},
    15: {"color": [0, 150, 50], "next": 4},
}

colors_pressed_mods: Colors = {
    -1: {"color": [0, 0, 0], "next": 0},  # type:ignore[misc]
    0: {"color": [160, 80, 0], "next": 1},
    1: {"color": [160, 60, 0], "next": 2},
    2: {"color": [160, 40, 0], "next": 3},
    3: {"color": [160, 20, 0], "next": 4},
    4: {"color": [150, 0, 0], "next": 5},
    5: {"color": [130, 0, 0], "next": 6},
    6: {"color": [120, 0, 0], "next": 7},
    7: {"color": [80, 0, 0], "next": 8},
    8: {"color": [60, 0, 0], "next": 9},
    9: {"color": [40, 0, 0], "next": 10},
    10: {"color": [60, 0, 0], "next": 11},
    11: {"color": [80, 0, 0], "next": 12},
    12: {"color": [120, 0, 0], "next": 13},
    13: {"color": [130, 0, 0], "next": 14},
    14: {"color": [150, 0, 0], "next": 15},
    15: {"color": [180, 0, 0], "next": 4},
}

colors_depressed: Colors = {
    -1: {"color": [0, 0, 0], "next": 0},  # type:ignore[misc]
    0: {"color": [0, 100, 10], "next": 1},
    1: {"color": [0, 80, 10], "next": 2},
    2: {"color": [0, 60, 8], "next": 3},
    3: {"color": [0, 40, 6], "next": 4},
    4: {"color": [0, 20, 4], "next": 5},
    5: {"color": [0, 0, 0], "next": IDLE_STATE},  # Not idle, needs to print this color
    IDLE_STATE: {"color": [0, 0, 0], "next": IDLE_STATE},  # Means idle
}

colors_depressed_mods: Colors = {
    -1: {"color": [0, 0, 0], "next": 0},  # type:ignore[misc]
    0: {"color": [100, 0, 0], "next": 1},
    1: {"color": [80, 0, 0], "next": 2},
    2: {"color": [60, 0, 0], "next": 3},
    3: {"color": [40, 0, 0], "next": 4},
    4: {"color": [20, 0, 0], "next": 5},
    5: {"color": [0, 0, 0], "next": IDLE_STATE},  # Not idle, needs to print this color
    IDLE_STATE: {"color": [0, 0, 0], "next": IDLE_STATE},  # Means idle
}


MODS = {
    "KEY_LEFTALT",
    "KEY_LEFTCTRL",
    "KEY_LEFTMETA",
    "KEY_LEFTSHIFT",
    "KEY_RIGHTALT",
    "KEY_RIGHTCTRL",
    "KEY_RIGHTMETA",
    "KEY_RIGHTSHIFT",
}
