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

import copy
import dataclasses
from typing import Literal

from mleds.constants import (
    COLOR_BLACK,
    COLOR_WHITE,
    DEFAULT_FRAME_DURATION,
    KEYBOARD_COLUMNS,
    KEYBOARD_ROWS,
    PIXELS_PER_FRAME,
)
from mleds.exceptions import InvalidConfigurationError

pixel_t = list[int]
row_t = list[pixel_t]
frame_data_t = list[row_t]
priority_t = Literal["background", "foreground", "urgent"]


@dataclasses.dataclass
class Frame:
    time: float
    pixels: frame_data_t


@dataclasses.dataclass
class Rectangle:
    x: int
    y: int
    width: int
    height: int
    start_color: pixel_t
    end_color: pixel_t
    direction: Literal["up", "down", "left", "right"]
    fill: bool
    value: int


@dataclasses.dataclass
class NewFrames:
    movie_name: str = ""
    copy_movie_name: str = ""
    create_frames: bool = False
    colors: list[list[int]] = dataclasses.field(default_factory=list)
    times: list[float] = dataclasses.field(default_factory=list)
    pixels_bool: list[bool] = dataclasses.field(default_factory=list)
    pixels_color: list[list[int]] = dataclasses.field(default_factory=list)
    reverse: bool = False
    back_and_forth: bool = False
    intensity: float = 1.0
    repetitions: int = 1
    rectangles: list[Rectangle] = dataclasses.field(default_factory=list)

    def check(self) -> None:
        if not self.copy_movie_name and not self.create_frames:
            raise InvalidConfigurationError("Submovie must create or copy movie.")
        if self.create_frames and not (self.pixels_bool or self.pixels_color):
            raise InvalidConfigurationError("Submovie has no pixels defined.")
        if len(self.pixels_bool) % PIXELS_PER_FRAME != 0:
            raise InvalidConfigurationError(
                f"Invalid number of pixels: {len(self.pixels_bool)} is not multiple "
                f"of {PIXELS_PER_FRAME}.",
            )
        if len(self.pixels_color) % PIXELS_PER_FRAME != 0:
            raise InvalidConfigurationError(
                f"Invalid number of pixels: {len(self.pixels_color)} is not multiple "
                f"of {PIXELS_PER_FRAME}.",
            )


class Movie:
    def __init__(self, name: str) -> None:
        self.name = name
        self.frames: list[Frame] = []

    def add_frame_line_bw(
        self,
        submovie: NewFrames,
        row_position: int,
        color: pixel_t,
        intensity: float,
    ) -> row_t:
        """Return a list of pixels using bool pixels and a color."""
        if intensity:
            color = [int(component * intensity) for component in color]
        return [
            color if pixel_bool else COLOR_BLACK
            for pixel_bool in submovie.pixels_bool[
                row_position : row_position + KEYBOARD_COLUMNS
            ]
        ]

    def add_frame_line_color(
        self,
        submovie: NewFrames,
        row_position: int,
        color: pixel_t,  # noqa: ARG002
        intensity: float,
    ) -> row_t:
        """Return a list of pixels using colored pixels."""
        if intensity:
            return [
                [int(color_component * intensity) for color_component in pixel]
                for pixel in submovie.pixels_color[
                    row_position : row_position + KEYBOARD_COLUMNS
                ]
            ]
        else:
            return submovie.pixels_color[row_position : row_position + KEYBOARD_COLUMNS]

    def create_frames(self, submovie: NewFrames) -> None:
        times = submovie.times or [DEFAULT_FRAME_DURATION]
        frames: list[Frame] = []
        pixels: list[bool] | list[list[int]]

        if submovie.pixels_color and submovie.colors:
            # User supplied color pixels and an override color.
            # Transform color pixels to boolean pixels and generate the frame as if
            # was a black and white.
            submovie.pixels_bool = [any(pixel) for pixel in submovie.pixels_color]
            submovie.pixels_color = []

        if submovie.pixels_bool:
            # Black and white movie. Use user supplied colors or plain white for pixels.
            colors = submovie.colors or [COLOR_WHITE]
            pixels = submovie.pixels_bool
            add_frame_line_method = self.add_frame_line_bw

        elif submovie.pixels_color:
            # Color movie. Use user supplied color pixels.
            colors = [COLOR_WHITE]  # Won't be used
            pixels = submovie.pixels_color
            add_frame_line_method = self.add_frame_line_color
        else:
            raise InvalidConfigurationError("Submovie has no pixels defined.")

        for frame_index in range(0, len(pixels), PIXELS_PER_FRAME):
            if frame_index < len(colors):
                color = colors[frame_index]
            if frame_index < len(times):
                frame_duration = times[frame_index]
            frame = Frame(
                time=frame_duration,
                pixels=[
                    add_frame_line_method(
                        submovie,
                        row_position,
                        color,
                        submovie.intensity,
                    )
                    for row_position in range(
                        frame_index,
                        frame_index + PIXELS_PER_FRAME,
                        KEYBOARD_COLUMNS,
                    )
                ],
            )

            # Fix: mouse buttons do not alineate with matrix position.
            # On last row, right pointer buttons are read from columns number 10 and 11,
            # but visually these rows are 8 and 9.

            frame.pixels[KEYBOARD_ROWS - 1][9:12] = frame.pixels[KEYBOARD_ROWS - 1][7:9]
            if submovie.rectangles:
                self.add_rectangles(submovie.rectangles, frame)
            frames.append(frame)
        self.frames.extend(
            self.transformed_frames(
                frames,
                submovie.reverse,
                submovie.repetitions,
                submovie.back_and_forth,
            ),
        )

    def transformed_row(
        self,
        row: list[pixel_t],
        intensity: float,
        color: pixel_t,
    ) -> list[pixel_t]:
        if not color or intensity == 0.0:
            return row
        row = copy.deepcopy(row)
        if color:
            row = [color if any(pixel) else COLOR_BLACK for pixel in row]
        if intensity != 1.0:
            return [
                [int(component * intensity) for component in pixel] for pixel in row
            ]
        else:
            return row

    def copy_frames_from(self, source_movie: "Movie", submovie: NewFrames) -> None:
        times = submovie.times or [f.time for f in source_movie.frames]
        frames: list[Frame] = []
        color: pixel_t
        for frame_index, frame in enumerate(source_movie.frames):
            # Do not overwrite original movie contents.
            frame = copy.deepcopy(frame)  # noqa: PLW2901
            if submovie.colors:
                if frame_index < len(submovie.colors):
                    color = submovie.colors[frame_index]
            else:
                color = []
            if frame_index < len(times):
                frame_duration = times[frame_index]

            new_frame = Frame(
                time=frame_duration,
                pixels=[
                    self.transformed_row(row, submovie.intensity, color)
                    for row in frame.pixels
                ],
            )
            if submovie.rectangles:
                self.add_rectangles(submovie.rectangles, new_frame)
            frames.append(new_frame)
        self.frames.extend(
            self.transformed_frames(
                frames,
                submovie.reverse,
                submovie.repetitions,
                submovie.back_and_forth,
            ),
        )

    def transformed_frames(
        self,
        frames: list[Frame],
        reverse: bool,
        repetitions: int,
        back_and_forth: bool,
    ) -> list[Frame]:
        if reverse:
            frames.reverse()
        if back_and_forth and len(frames) > 1:
            frames.extend(reversed(frames[1:-1]))  # Exclude first and last frame
        if repetitions > 1:
            frames = frames * repetitions
        return frames

    def add_rectangle(self, r: Rectangle, matrix: frame_data_t) -> None:  # noqa: C901, PLR0912
        def clamp(v: float, lo: int = 0, hi: int = 255) -> int:
            return max(lo, min(hi, int(v)))

        def interpolate(c1: pixel_t, c2: pixel_t, t: float) -> list[int]:
            return [clamp(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)]

        ############################################################
        # Percentage cutoff (0-100)
        ############################################################
        percent = max(0, min(100, r.value)) / 100.0

        ############################################################
        # Compute effective draw size based on direction
        ############################################################
        if r.direction in ("down", "up"):
            real_height = round(r.height * percent)
            real_width = r.width
        else:
            real_width = round(r.width * percent)
            real_height = r.height

        ############################################################
        # Compute drawing bounds depending on direction
        ############################################################
        if r.direction == "down":  # start at top
            row_start = r.y
            row_end = r.y + real_height
        elif r.direction == "up":  # start at bottom
            row_start = r.y + r.height - real_height
            row_end = r.y + r.height
        else:
            row_start = r.y
            row_end = r.y + real_height

        if r.direction == "right":  # start at left
            col_start = r.x
            col_end = r.x + real_width
        elif r.direction == "left":  # start at right
            col_start = r.x + r.width - real_width
            col_end = r.x + r.width
        else:
            col_start = r.x
            col_end = r.x + real_width

        row_end = min(row_end, KEYBOARD_ROWS)
        col_end = min(col_end, KEYBOARD_COLUMNS)

        ############################################################
        # Draw loop
        ############################################################
        for row in range(row_start, row_end):
            for col in range(col_start, col_end):
                if r.direction == "down":
                    t = (row - r.y) / max(r.height - 1, 1)
                elif r.direction == "up":
                    t = 1 - (row - r.y) / max(r.height - 1, 1)
                elif r.direction == "right":
                    t = (col - r.x) / max(r.width - 1, 1)
                elif r.direction == "left":
                    t = 1 - (col - r.x) / max(r.width - 1, 1)
                else:
                    t = 0

                color = interpolate(r.start_color, r.end_color, t)

                if r.fill:
                    matrix[row][col] = color
                else:
                    is_border = (
                        row == row_start
                        or row == row_end - 1
                        or col == col_start
                        or col == col_end - 1
                    )
                    if is_border:
                        matrix[row][col] = color

    def add_rectangles(self, rectangles: list[Rectangle], frame: Frame) -> None:
        for rectangle in rectangles:
            self.add_rectangle(rectangle, frame.pixels)


@dataclasses.dataclass
class PlayingMovie:
    movie: Movie
    priority: priority_t
    position: int = 0

    def ended(self) -> bool:
        return len(self.movie.frames) == self.position + 1
