# Copyright (c) 2026 Jordi Marqués
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
import colorsys
import logging
import random
from copy import deepcopy
from random import randint
from time import perf_counter

from mleds.clients.base import Client
from mleds.constants import COLOR_BLACK, KEYBOARD_COLUMNS, KEYBOARD_ROWS, Priority
from mleds.read_keyboard import InputEventGenerator, evdev_events

logger = logging.getLogger(__name__)


# EVDEV ETYPE value when event is a keyboard event.
EVDEV_ETYPE_KEYBOARD = 1
# Playing board columns.
BOARD_COLS = KEYBOARD_ROWS - 1  # Ignore trackball row
# Playing board rows.
BOARD_ROWS = KEYBOARD_COLUMNS
# Number of new figures after which movement speed increases.
INCREASE_SPEED_FIGURES = 30
# Millisecond between led brightness change.
MOVE_BRIGHTNESS_TIME = 0.05
# Maximum puntuation.
MAX_POINTS = BOARD_ROWS * 18
# Earned points after clearing one row.
ONE_ROW_POINTS = 1
# Earned points after clearing two rows.
TWO_ROW_POINTS = 4
# Earned points after clearing three rows.
THREE_ROW_POINTS = 10


class Figure:
    """Class to define figures and their properties."""

    def __init__(
        self,
        name: str,
        values: list[list[tuple[int, int]]],
        rotation_collisions: list[list[tuple[int, int]]],
    ) -> None:
        self.name = name
        self.values = values
        self.rotation_collisions = rotation_collisions


class Board:
    """Class to store board used positions and colors."""

    def __init__(self) -> None:
        self.boolean: list[list[bool]] = []
        self.colors: list[list[list[int]]] = []
        for _ in range(BOARD_COLS):
            self.boolean.append([*[False] * BOARD_ROWS])
            self.colors.append([*[COLOR_BLACK] * BOARD_ROWS])


class Tetris(Client):
    def __init__(self, *args, **kwargs) -> None:  # type:ignore[no-untyped-def]
        super().__init__(*args, **kwargs)

        # Specify if board should be rotated. User configurable.
        self.rotate_board = self.configuration.tetris_rotate
        # Specifies if movement speed increases over time. User configurable.
        self.speed_increases = self.configuration.tetris_speed_increases
        # Keys mapped to move left/right, rotate and move down. User configurable.
        self.keys = self.configuration.tetris_keys
        self.key_left = self.configuration.tetris_keys[0]
        self.key_rotate = self.configuration.tetris_keys[1]
        self.key_down = self.configuration.tetris_keys[2]
        self.key_right = self.configuration.tetris_keys[3]

        # Queue where game is shown.
        type(self).priority = Priority.foreground

        # Event to notify game loop about new key events.
        self.key_event = asyncio.Event()

        # Key code and value after new event.
        self.key_event_code: str
        self.key_event_value: int = 0

        # When turn time reaches zero or user presses down key, turn ends. Used by loop.
        self.turn_ended = False

        # Tell print_board to give feedback when speed increases.
        self.show_movement_increased = False

        # Leds breathe, their intensity moves up and down.
        self.brightness_drift_position = 0
        self.brightness_drift_values = [
            0.6,
            0.65,
            0.7,
            0.75,
            0.8,
            0.85,
            0.9,
            0.95,
            1.0,
            0.95,
            0.9,
            0.85,
            0.8,
            0.75,
            0.7,
            0.65,
        ]

        self.initialize()

    def initialize(self) -> None:
        """Initialize new game."""
        self.board = Board()
        self.movement_time = self.configuration.tetris_speed
        self.figures_counter = 0
        self.points = 0
        self.new_figure()

    def new_figure(self) -> None:
        """Bring new figure into the board."""
        figures_list = list(figures.values())
        index = randint(0, len(figures_list) - 1)  # noqa: S311
        self.current_figure = figures_list[index]
        self.figure_position = [1, 0]

        self.figure_orientation = 0
        self.figure_color = self.new_color()
        self.figures_counter += 1
        # If self.speed_increases is True then each time figures counter increases by
        # INCREASE_SPEED_FIGURES, movement time gets decreased.
        if self.speed_increases and self.figures_counter % INCREASE_SPEED_FIGURES == 0:
            self.movement_time -= 0.1
            self.show_movement_increased = True

    def new_color(self) -> list[int]:
        """Generate random color."""
        return [
            int(i * 255)
            for i in colorsys.hsv_to_rgb(
                random.random(),  # noqa: S311
                1.0,
                1.0,
            )
        ]

    def collides(  # noqa: C901, PLR0911, PLR0912
        self,
        offset: list[int] | None = None,
        rotate: bool = False,
    ) -> bool:
        """Returns if current figure collisions when moved or rotated."""
        if offset:
            # Check if collides when moved by x,y positions.
            figure_position: list[int] = [
                self.figure_position[0] + offset[0],
                self.figure_position[1] + offset[1],
            ]
        else:
            # Check if collides when rotates.
            figure_position = self.figure_position

        for dot in self.current_figure.values[self.figure_orientation]:
            # Check if the figure crosses board limits.
            if not 0 <= figure_position[0] + dot[0] < BOARD_COLS:
                return True
            if not 0 <= figure_position[1] + dot[1] < BOARD_ROWS:
                return True

            # Check if the figure collides with some occupied position when moved.
            if self.board.boolean[figure_position[0] + dot[0]][
                figure_position[1] + dot[1]
            ]:
                return True

        if rotate:
            next_figure_orientation = self.figure_orientation + 1
            if next_figure_orientation > 3:  # noqa: PLR2004
                next_figure_orientation = 0

            # Check if the figure crosses border limits when rotated.
            for dot in self.current_figure.values[next_figure_orientation]:
                if not 0 <= figure_position[0] + dot[0] < BOARD_COLS:
                    return True
                if not 0 <= figure_position[1] + dot[1] < BOARD_ROWS:
                    return True

            # Check if the figure collides while rotating
            for dot in self.current_figure.rotation_collisions[self.figure_orientation]:
                if self.board.boolean[figure_position[0] + dot[0]][
                    figure_position[1] + dot[1]
                ]:
                    return True

            # Check if the figure collides when rotated
            for dot in self.current_figure.values[next_figure_orientation]:
                if self.board.boolean[figure_position[0] + dot[0]][
                    figure_position[1] + dot[1]
                ]:
                    return True
        return False

    async def print_board(
        self,
        do_remove_row: bool = False,
        remove_row: int = 0,
        end_game: bool = False,
    ) -> None:
        """Print curent board.

        Args:
            do_remove_row: give feedback about a row being removed.
            remove_row: row being removed.
            end_game: give feedback when game ends and show points.
        """
        color_board = deepcopy(self.board.colors)

        if do_remove_row:
            # Create a clone of the board with the specified row empty.
            # Alternate it with the unmodified board.
            color_board_line_removed = deepcopy(color_board)
            for col in range(BOARD_COLS):
                color_board_line_removed[col][remove_row] = COLOR_BLACK
            for _ in range(4):
                await self.send_message(
                    message=self.next_message(color_board_line_removed),
                )
                await asyncio.sleep(0.10)
                await self.send_message(message=self.next_message(color_board))
                await asyncio.sleep(0.10)
        elif end_game:
            # Add current figure to a copy of the board.
            for dot in self.current_figure.values[self.figure_orientation]:
                color_board[self.figure_position[0] + dot[0]][
                    self.figure_position[1] + dot[1]
                ] = self.figure_color
            red_board = [
                [
                    COLOR_BLACK if not any(rgb_color) else [128, 0, 0]
                    for rgb_color in column
                ]
                for column in color_board
            ]

            # Print 4 times board with alternating red color.
            for _ in range(4):
                await self.send_message(message=self.next_message(color_board))
                await asyncio.sleep(0.2)
                await self.send_message(message=self.next_message(red_board))
                await asyncio.sleep(0.2)

            # Print user points.
            percent = int(min(self.points, MAX_POINTS) / MAX_POINTS * 100)
            for i in range(0, percent, 3):
                await self.send_message(
                    message=self.next_message(
                        color_board,
                        points_percent=i,
                    ),
                )
                await asyncio.sleep(0.06)
            await self.send_message(
                message=self.next_message(
                    color_board,
                    no_timeout=True,
                    points_percent=percent,
                ),
            )
        else:
            # Add current figure to the copy of the board.
            for dot in self.current_figure.values[self.figure_orientation]:
                color_board[self.figure_position[0] + dot[0]][
                    self.figure_position[1] + dot[1]
                ] = self.figure_color
            await self.send_message(
                message=self.next_message(
                    color_board,
                    move_color=True,
                ),
            )

    def next_message(
        self,
        board: list[list[list[int]]],
        no_timeout: bool = False,
        move_color: bool = False,
        points_percent: int = -1,
    ) -> list[str]:
        """Get message to be sent to server.

        Args:
            board: board colors.
            no_timeout: do not set timeout to the sent frame.
            move_color: do drift leds brightness.
            points_percent: show user points.
        """
        board = deepcopy(board)

        if move_color:
            value = self.brightness_drift_values[self.brightness_drift_position]
            board = [
                [
                    [
                        max(0, int(board[c][r][0] * value)),
                        max(0, int(board[c][r][1] * value)),
                        max(0, int(board[c][r][2] * value)),
                    ]
                    for r in range(BOARD_ROWS)
                ]
                for c in range(BOARD_COLS)
            ]

        if self.show_movement_increased:
            board = [
                [
                    [
                        max(6, board[c][r][0]),
                        board[c][r][1],
                        board[c][r][2],
                    ]
                    for r in range(BOARD_ROWS)
                ]
                for c in range(BOARD_COLS)
            ]
            self.show_movement_increased = False

        if self.rotate_board:
            # Reverse board left<->right
            board = list(reversed(board))
        else:
            # Reverse board top<->bottom
            for row in board:
                row.reverse()

        if points_percent > -1:
            # Clear first row, where points will be shown.
            points_rectangle = "rectangle=0 0 12 1 #000000 #000000 right false 100"
            # Add points in white color.
            points_rectangle += (
                f" rectangle=0 0 12 1 #333333 #FFFFFF right false {points_percent}"
            )

        return [
            "action=add_movie",
            "name=hidden_tetris",
            "create_frames=true",
            f"times={-1 if no_timeout else self.movement_time * 2}",
            "pixels=",
            " ".join(
                [
                    f"#{board[c][r][0]:02X}{board[c][r][1]:02X}{board[c][r][2]:02X}"
                    for c in range(BOARD_COLS)
                    for r in range(BOARD_ROWS)
                ],
            ),
            " #000000" * BOARD_ROWS,  # Add trackball row, ignored by the board.
            points_rectangle if points_percent > -1 else "",
            "end=true",
            "action=play_movie",
            "name=hidden_tetris",
            f"priority={self.priority}",
            "end=true",
        ]

    async def next_turn(self) -> None:  # noqa: C901
        if self.collides(offset=[0, 1]):  # Moving current figure down collides.
            # Add current figure to the board and generate a new figure.
            for dot in self.current_figure.values[self.figure_orientation]:
                self.board.colors[self.figure_position[0] + dot[0]][
                    self.figure_position[1] + dot[1]
                ] = self.figure_color
                self.board.boolean[self.figure_position[0] + dot[0]][
                    self.figure_position[1] + dot[1]
                ] = True

            # Check for full rows, from bottom to top.
            cleared_rows = 0
            for row in reversed(range(BOARD_ROWS)):
                # While all pixels on this row are filled:
                while all(self.board.boolean[col][row] for col in range(BOARD_COLS)):
                    cleared_rows += 1
                    await self.print_board(do_remove_row=True, remove_row=row)
                    # Move rows down.
                    for previous_row in reversed(range(row)):
                        for col in range(BOARD_COLS):
                            self.board.boolean[col][previous_row + 1] = (
                                self.board.boolean[col][previous_row]
                            )
                            self.board.colors[col][previous_row + 1] = (
                                self.board.colors[col][previous_row]
                            )
                    self.board.boolean[col][0] = False
                    self.board.colors[col][0] = COLOR_BLACK
            if cleared_rows == 1:
                self.points += ONE_ROW_POINTS
            if cleared_rows == 2:  # noqa: PLR2004
                self.points += TWO_ROW_POINTS
            if cleared_rows == 3:  # noqa: PLR2004
                self.points += THREE_ROW_POINTS

            self.new_figure()
            if self.collides():
                # If the newly added figure also collides game ends.
                await self.print_board(end_game=True)

                # Pause until user presses any key.
                self.key_event.clear()
                await self.key_event.wait()
                self.key_event.clear()
                self.initialize()
        else:
            # Move current figure one cell down.
            self.figure_position[1] += 1

    async def loop(self) -> None:
        self.turn_ended = False
        turn_start_time = perf_counter()
        turn_time_remaining = self.movement_time
        await self.print_board()

        while True:
            try:
                # Wait until next key is pressed, or turn time expires.
                await asyncio.wait_for(
                    self.key_event.wait(),
                    timeout=min(turn_time_remaining, MOVE_BRIGHTNESS_TIME),
                )
            except TimeoutError:
                # Compute remaining turn time and use as next timeout.
                turn_time_remaining = max(
                    self.movement_time - (perf_counter() - turn_start_time),
                    0.0,
                )
                if turn_time_remaining < 0.01:  # noqa: PLR2004
                    self.turn_ended = True
                else:
                    self.brightness_drift_position += 1
                    if self.brightness_drift_position >= len(
                        self.brightness_drift_values,
                    ):
                        self.brightness_drift_position = 0
            else:
                # A key has been pressed, process it.
                self.key_event.clear()
                self.process_key_event()

                # Compute remaining turn time and use as next timeout.
                turn_time_remaining = max(
                    self.movement_time - (perf_counter() - turn_start_time),
                    0.0,
                )
            finally:
                if self.turn_ended:
                    self.turn_ended = False
                    turn_start_time = perf_counter()
                    turn_time_remaining = self.movement_time
                    await self.next_turn()
            await self.print_board()

    def process_key_event(self) -> None:  # noqa: C901
        """Returns if current movement ends."""
        match self.key_event_code:
            case self.key_left:
                if not self.collides(offset=[-1, 0]):
                    self.figure_position[0] -= 1
            case self.key_down:
                self.turn_ended = True
            case self.key_rotate:
                if not self.collides(rotate=True):
                    self.figure_orientation += 1
                else:
                    # Can not rotate in-place, try moving left/right and then rotate.
                    for try_offset in -1, 1:
                        if not self.collides(offset=[try_offset, 0]):
                            figure_position = [*self.figure_position]
                            self.figure_position[0] += try_offset
                            if not self.collides(rotate=True):
                                self.figure_orientation += 1
                                break
                            # Restore original figure position
                            self.figure_position = figure_position
                if self.figure_orientation > 3:  # noqa: PLR2004
                    self.figure_orientation = 0
            case self.key_right:
                if not self.collides(offset=[1, 0]):
                    self.figure_position[0] += 1

    async def run(self) -> None:
        await asyncio.gather(
            self.loop(),
            self.read_input_events(),
        )

    async def read_input_events(self) -> None:
        async for _sec, _usec, etype, code, value in InputEventGenerator(
            self.configuration.keyboard_device,
        ):
            if etype == EVDEV_ETYPE_KEYBOARD and value in {1, 2}:
                key_code = evdev_events[EVDEV_ETYPE_KEYBOARD][code]
                if key_code in self.keys:
                    self.key_event_code = key_code
                    self.key_event.set()


figures: dict[str, Figure] = {
    "line": Figure(
        "line",
        [
            [(1, 0), (1, 1), (1, 2)],
            [(0, 1), (1, 1), (2, 1)],
            [(1, 0), (1, 1), (1, 2)],
            [(0, 1), (1, 1), (2, 1)],
        ],
        [
            [(2, 0), (0, 2)],  # 0 -> 1
            [(0, 0), (2, 2)],  # 1 -> 2
            [(2, 0), (0, 2)],  # 2 -> 3
            [(0, 0), (2, 2)],  # 3 -> 0
        ],
    ),
    "square": Figure(
        "square",
        [
            [(0, 0), (0, 1), (1, 0), (1, 1)],
            [(0, 0), (0, 1), (1, 0), (1, 1)],
            [(0, 0), (0, 1), (1, 0), (1, 1)],
            [(0, 0), (0, 1), (1, 0), (1, 1)],
        ],
        [[], [], [], []],
    ),
    "triangle": Figure(
        "triangle",
        [
            [(1, 0), (1, 1), (2, 1), (1, 2)],
            [(0, 1), (1, 1), (2, 1), (1, 2)],
            [(1, 0), (0, 1), (1, 1), (1, 2)],
            [(1, 0), (0, 1), (1, 1), (2, 1)],
        ],
        [
            [(2, 0), (0, 2)],  # 0 -> 1
            [(0, 0), (2, 2)],  # 1 -> 2
            [(2, 0), (0, 2)],  # 2 -> 3
            [(0, 0), (2, 2)],  # 3 -> 0
        ],
    ),
    "l": Figure(
        "l",
        [
            [(1, 0), (1, 1), (1, 2), (2, 2)],
            [(0, 1), (1, 1), (2, 1), (0, 2)],
            [(1, 0), (1, 1), (1, 2), (0, 0)],
            [(0, 1), (1, 1), (2, 1), (2, 0)],
        ],
        [
            [(2, 0), (0, 2)],  # 0 -> 1
            [(0, 0), (2, 2)],  # 1 -> 2
            [(2, 0), (0, 2)],  # 2 -> 3
            [(0, 0), (2, 2)],  # 3 -> 0
        ],
    ),
    "l_inversed": Figure(
        "l_inversed",
        [
            [(1, 0), (1, 1), (1, 2), (0, 2)],
            [(0, 1), (1, 1), (2, 1), (0, 0)],
            [(1, 0), (1, 1), (1, 2), (2, 0)],
            [(0, 1), (1, 1), (2, 1), (2, 2)],
        ],
        [
            [(2, 0), (0, 2)],  # 0 -> 1
            [(0, 0), (2, 2)],  # 1 -> 2
            [(2, 0), (0, 2)],  # 2 -> 3
            [(0, 0), (2, 2)],  # 3 -> 0
        ],
    ),
    "z": Figure(
        "z",
        [
            [(1, 0), (2, 0), (0, 1), (1, 1)],
            [(1, 0), (1, 1), (2, 1), (2, 2)],
            [(1, 1), (2, 1), (0, 2), (1, 2)],
            [(0, 0), (0, 1), (1, 1), (1, 2)],
        ],
        [
            [],  # 0 -> 1
            [],  # 1 -> 2
            [],  # 2 -> 3
            [],  # 3 -> 0
        ],
    ),
    "z_inverse": Figure(
        "z_inverse",
        [
            [(0, 0), (1, 0), (1, 1), (2, 1)],
            [(2, 0), (1, 1), (2, 1), (1, 2)],
            [(0, 1), (1, 1), (1, 2), (2, 2)],
            [(1, 0), (0, 1), (1, 1), (0, 2)],
        ],
        [
            [],  # 0 -> 1
            [],  # 1 -> 2
            [],  # 2 -> 3
            [],  # 3 -> 0
        ],
    ),
}
