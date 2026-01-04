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
import dataclasses
import logging
import re
from collections.abc import Awaitable
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict

from mleds.clients import all_clients
from mleds.configuration import Configuration
from mleds.constants import (
    COLOR_BLACK,
    KEYBOARD_ROWS,
    PIXELS_PER_FRAME,
    TIMEOUT_DISABLE,
)
from mleds.exceptions import InvalidConfigurationError
from mleds.movie import (
    Movie,
    NewFrames,
    PlayingMovie,
    Rectangle,
    frame_data_t,
    priority_t,
)

if TYPE_CHECKING:
    from mleds.clients.base import Client


class ClientItem(TypedDict):
    klass: "type[Client]"
    task: Awaitable[Any] | None


message_t = list[tuple[str, str]]

writer_event = asyncio.Event()
scheduler_lock = asyncio.Lock()
process_messages_lock = asyncio.Lock()
logger = logging.getLogger(__name__)


def hex2rgb(string: str) -> list[int]:
    """String hexadecimal color to list of rgb integers."""
    # Fix: hidraw device expects BGR instead of RGB
    return [int(string[5:7], 16), int(string[3:5], 16), int(string[1:3], 16)]


def send_frame_to_keyboard(hidraw: Path, frame: frame_data_t) -> None:
    for index, line in enumerate(frame):
        with hidraw.open("wb") as k:
            row_colors: list[int] = []
            for rgb in line:
                row_colors.extend(rgb)
            if index == KEYBOARD_ROWS - 1:
                # Fix: mouse buttons do not alineate with matrix position.
                # On last row, right pointer buttons are read from columns number 10 and
                # 11, but visually these rows are 8 and 9.
                row_colors[27:36] = row_colors[21:27]
            k.write(b"xXRGB" + bytes([index, *row_colors]))


@dataclasses.dataclass
class PlayingSlots:
    background: PlayingMovie | None = None
    foreground: PlayingMovie | None = None
    urgents: list[PlayingMovie] = dataclasses.field(default_factory=list)
    playing: PlayingMovie | None = None


class MessagesBuffer:
    """Intermediary class between socket communication and Server.

    Communication is:
        - line based to allow easy scripting.
        - key=value, where value spans across lines, allow single line messages.
    """

    def __init__(self, server: "Server") -> None:
        self.lines: list[str] = []
        self.partial_pre = ""  # line contents before "end=true"
        # self.partial_post = ""  # line contents after "end=true""
        self.server = server

    async def add(self, line: str) -> tuple[list[str], bool]:
        """Receive a new line to the next message and if ready process it.

        Args:
            line: new line for adding to the next message.

        Returns:
            tuple with a list[str] and a bool.

            server response in the form of a list of strings. To check if this new line
            completed a message which has been sent, check if the response is empty or
            not.

            bool to tell if the sent message means the communication has ended.
        """
        disconnect = False
        response_lines: list[str] = []

        line = line.strip()
        if not line or line.startswith("//"):
            return response_lines, disconnect
        while match := re.match(r"(.*?)\s*end=true\s*(.*)", line):
            ########################################################################
            # This line marks the end of a message, send this message to the server.
            ########################################################################
            self.partial_pre, line = match.groups()
            if self.partial_pre:
                self.lines.append(self.partial_pre)
            try:
                message = message_keyvalues(self.lines)
                async with process_messages_lock:
                    (new_lines, new_disconnect) = await self.server.receive_message(
                        message,
                    )
                response_lines.extend(new_lines)
                if new_disconnect:
                    disconnect = True
            except InvalidConfigurationError as e:
                disconnect = True
                msg = f"Error: invalid configuration: {e.args[0]}."
                logger.warning(msg)
                response_lines.append(msg)
            except Exception as e:
                disconnect = True
                logger.exception("Error while processing client message")
                response_lines.append(f"Unhandled server error: {e!s}")
            else:
                self.lines.clear()
        if line:
            self.lines.append(line)
        return response_lines, disconnect


class Server:
    def __init__(self, configuration: Configuration, oneshot: bool) -> None:
        logger.info("__init__(): Initializing server instance.")

        blank_movie = Movie(name="blank")
        blank_movie.create_frames(
            NewFrames(
                create_frames=True,
                pixels_bool=[True] * PIXELS_PER_FRAME,
                colors=[COLOR_BLACK],
                times=[-1],
            ),
        )
        self.movies: dict[str, Movie] = {"blank": blank_movie}
        self.clients = {
            name: ClientItem(klass=client, task=None)
            for name, client in all_clients.items()
        }
        self.hidraw_device = configuration.hidraw_device
        self.slot = PlayingSlots()
        self.slot.background = PlayingMovie(movie=blank_movie, priority="background")
        # In oneshot mode server exits when the playing movie ends.
        self.oneshot = oneshot
        # Intensity to apply to colors, float >=0.0
        self.intensity = 1.0
        self.loads_path = configuration.loads_path
        self.scripts_paths = configuration.scripts_paths
        self.configuration = configuration

    def get_messages_reader(self) -> MessagesBuffer:
        return MessagesBuffer(self)

    async def async_init(
        self,
        include_loads: bool,
        include_resources: bool,
    ) -> None:
        if include_loads:
            for load_file in sorted(
                file
                for path in self.loads_path
                for file in path.glob("*")
                if file.is_file()
            ):
                logger.info("async_init(): loading command file %s.", load_file)
                messages_reader = self.get_messages_reader()
                with load_file.open("r") as f:
                    for line in f.readlines():
                        _response_lines, _disconnect = await messages_reader.add(line)

        if include_resources:
            for resource_file in (
                file
                for file in resources.files("mleds.scripts").iterdir()
                if file.is_file()
            ):
                logger.info("async_init(): loading embedded file %s.", resource_file)
                messages_reader = self.get_messages_reader()
                with resource_file.open("r") as f:
                    for line in f.readlines():
                        _response_lines, _disconnect = await messages_reader.add(line)

    async def add_movie(self, message: message_t) -> str:  # noqa: C901, PLR0912, PLR0915
        """Add a movie to the list of available movies."""
        # frames list is initialized to make static cheker happy, but this instance is
        # never used.
        new_frames_list: list[NewFrames] = []
        new_frames: NewFrames = NewFrames()
        movie_name = ""
        first_data = True

        for key, value in message:
            match key:
                case "action":
                    pass
                case "name":
                    movie_name = value
                case "copy_movie":
                    if first_data:
                        first_data = False
                    else:
                        new_frames.check()
                        new_frames_list.append(new_frames)
                    new_frames = NewFrames(copy_movie_name=value)
                case "create_frames":
                    if first_data:
                        first_data = False
                    else:
                        new_frames.check()
                        new_frames_list.append(new_frames)
                    new_frames = NewFrames(create_frames=True)
                case "colors":
                    new_frames.colors = [hex2rgb(c) for c in value.split()]
                case "times":
                    new_frames.times = [float(t) for t in value.split()]
                case "intensity":
                    new_frames.intensity = max(float(value), 0.0)
                case "repetitions":
                    new_frames.repetitions = int(value)
                case "reverse":
                    new_frames.reverse = value.lower() == "true"
                case "back_and_forth":
                    new_frames.back_and_forth = value.lower() == "true"
                case "rectangle":
                    x, y, width, height = [int(v) for v in value.split()[0:4]]
                    color1, color2 = [hex2rgb(v) for v in value.split()[4:6]]
                    direction = value.split()[6].lower()
                    fill = value.split()[7].lower() == "true"
                    rec_value = int(value.split()[8])
                    new_frames.rectangles.append(
                        Rectangle(
                            x,
                            y,
                            width,
                            height,
                            color1,
                            color2,
                            direction,  # type:ignore[arg-type]
                            fill,
                            rec_value,
                        ),
                    )
                case "pixels":
                    if value.startswith("#"):
                        # Color pixels "#11ff22"
                        new_frames.pixels_color = [hex2rgb(c) for c in value.split()]
                    else:
                        # Black and white pixels
                        new_frames.pixels_bool = [
                            pixel != "." for pixel in value if pixel != " "
                        ]
                case _:
                    raise InvalidConfigurationError(
                        f"unknown parameter for 'add_movie': '{key}'",
                    )

        new_frames.check()
        if not movie_name:
            raise InvalidConfigurationError("Movie must have a name")
        if not re.match(r"^[a-zA-Z0-9-_]+$", movie_name):
            raise InvalidConfigurationError(
                "Movie can contain only alphanumeric symbols plus _ and -",
            )
        if movie_name.lower() == "none":
            raise InvalidConfigurationError(
                "Movie name can not be the reserved word 'none'",
            )
        new_frames_list.append(new_frames)

        movie = Movie(name=movie_name)
        for new_frames in new_frames_list:
            if new_frames.create_frames:
                movie.create_frames(new_frames)
            else:
                if new_frames.copy_movie_name not in self.movies:
                    raise InvalidConfigurationError(
                        f"movie '{new_frames.copy_movie_name}' does not exist",
                    ) from None

                movie.copy_frames_from(
                    source_movie=self.movies[new_frames.copy_movie_name],
                    submovie=new_frames,
                )
        self.movies[movie_name] = movie
        return "ok"

    async def message_stop_movies(self, message: message_t) -> None:
        """Stop all movies in a priority queue."""
        priority = None
        for key, value in message:
            match key:
                case "action":
                    pass
                case "priority":
                    priority = value
                case _:
                    raise InvalidConfigurationError(
                        f"unknown parameter for 'stop_movies': '{key}'",
                    )
        if priority is None:
            raise InvalidConfigurationError("Priority not specified")
        if priority not in {"background", "foreground", "urgent"}:
            raise InvalidConfigurationError(f"Invalid priority {priority}")

        async with scheduler_lock:
            await self.movie_scheduler(
                notify_writer=True,
                stop_priority=priority,
            )

    async def play_movie(self, message: message_t) -> None:
        priority = "foreground"  # default priority if no priority is specified.
        for key, value in message:
            match key:
                case "action":
                    pass
                case "name":
                    movie = self.movies[value]
                case "priority":
                    if value not in ("background", "foreground", "urgent"):
                        raise InvalidConfigurationError(
                            f"invalid value for priority: '{value}'",
                        )
                    priority = value
                case _:
                    raise InvalidConfigurationError(
                        f"unknown parameter for action 'enqueue_movie': '{key}'",
                    )

        playing_movie = PlayingMovie(
            movie=movie,
            priority=priority,  # type:ignore[arg-type]
        )

        async with scheduler_lock:
            match priority:
                case "background":
                    logger.info(
                        "play_movie(): Set background movie to: %s.", movie.name
                    )
                    self.slot.background = playing_movie
                case "foreground":
                    logger.info(
                        "play_movie(): Set foreground movie to: %s.", movie.name
                    )
                    self.slot.foreground = playing_movie
                case "urgent":
                    logger.info("play_movie(): Enqueue urgent movie: %s.", movie.name)
                    self.slot.urgents.append(playing_movie)
                case _:
                    raise RuntimeError  # Make static checker happy

            await self.movie_scheduler(
                notify_writer=True,
                movie_added_with_priority=priority,
            )

    async def movie_scheduler(  # noqa: C901, PLR0912
        self,
        notify_writer: bool,
        movie_ended: bool = False,
        movie_added_with_priority: priority_t | None = None,
        stop_priority: str | None = None,
    ) -> None:
        """Reacts to movie slots changes, sets them accordingly and notify writer.

        Ensure that:
          - self.slot.background
          - self.slot.foreground
          - self.slot.urgents
          - self.slot.playing

        is consistent after some change has been made to them.
        """
        previous_playing = self.slot.playing

        if movie_added_with_priority == "urgent":
            # Urgent movie added. If current playing movie is not urgent, replace it.
            if not self.slot.playing:
                self.slot.playing = self.slot.urgents.pop(0)
            elif self.slot.playing.priority != "urgent":
                # There was a non-urgent movie playing. Replace it by the urgent one.
                self.slot.playing = self.slot.urgents.pop(0)
                if self.slot.foreground:
                    self.slot.foreground = None
        elif movie_added_with_priority == "foreground":
            # Foreground movie replaces any foreground/background playing movies.
            if self.slot.playing:
                if self.slot.playing.priority in ("background", "foreground"):
                    self.slot.playing = self.slot.foreground
            else:
                self.slot.playing = self.slot.foreground
            self.slot.foreground = None
        elif movie_added_with_priority == "background":
            # Background movie replaces previous background movie.
            if self.slot.playing:
                if self.slot.playing.priority == "background":
                    self.slot.playing = self.slot.background
            else:
                self.slot.playing = self.slot.background
        elif movie_ended:
            if self.slot.urgents:
                # Ended movie was urgent and there are pending urgent movies enqueued.
                self.slot.playing = self.slot.urgents.pop(0)
            elif self.slot.background:
                # Ended movie was foreground/background and there is a background movie.
                self.slot.playing = self.slot.background

        elif stop_priority:
            if self.slot.playing is not None:  # make linter happy
                if self.slot.playing.priority == stop_priority:
                    self.slot.playing = None

            if stop_priority == "background":
                self.slot.background = self.slot.playing = PlayingMovie(
                    movie=self.movies["blank"],
                    priority="background",
                )
            elif stop_priority == "foreground":
                self.slot.foreground = None
            elif stop_priority == "urgent":
                self.slot.urgents.clear()

            if self.slot.playing is None:
                if self.slot.foreground is not None:
                    self.slot.playing = self.slot.foreground
                else:
                    self.slot.playing = self.slot.background

        # It is posible that there has no been any change to current playing movie.
        # For example:
        #   - background or foreground movie changed, but urgent movie is playing.
        #   - background movie changed while foreground movie is playing.
        #   - urgent movie added while another urgent movie is playing.
        if self.slot.playing is not previous_playing:
            if self.slot.playing is None:
                logger.info("movie_scheduler(): No movie to schedule.")
            else:
                logger.info(
                    "movie_scheduler(): Scheduled next movie to: %s.",
                    self.slot.playing.movie.name,
                )
                if notify_writer:
                    logger.info(
                        "movie_scheduler(): Playing movie changed, notify writer.",
                    )
                    writer_event.set()

    async def receive_message(self, message: message_t) -> tuple[list[str], bool]:  # noqa: C901, PLR0912
        """Read message lines and run them."""
        disconnect = False

        # message[0][0] == "action"
        action = message[0][1]

        match action:
            case "run_client":
                response = await self.run_client(message)
            case "stop_client":
                response = await self.stop_client(message)
            case "run_script":
                response = await self.run_script_file(message)
            case "status":
                response = await self.get_status(message)
            case "add_movie":
                response = [await self.add_movie(message)]
            case "play_movie":
                await self.play_movie(message)
                response = ["ok"]
            case "stop_movies":
                await self.message_stop_movies(message)
                response = ["ok"]
            case "set_intensity":
                if message[1][1].startswith("+"):
                    intensity = self.intensity + float(
                        message[1][1].replace("+", ""),
                    )
                elif message[1][1].startswith("-"):
                    intensity = self.intensity - float(
                        message[1][1].replace("-", ""),
                    )
                else:
                    intensity = float(message[1][1])
                self.intensity = max(intensity, 0.0)
                response = [str(self.intensity)]
            case "dump_movies":
                response = self.dump_movies()
            case "disconnect":
                response = ["ok"]
                disconnect = True
            case _:
                raise InvalidConfigurationError(f"invalid action '{message[0][1]}'")
        return response, disconnect

    async def get_status(self, message: message_t) -> list[str]:
        for key, _value in message:
            match key:
                case "action":
                    pass
                case _:
                    raise InvalidConfigurationError(
                        f"unknown parameter for action 'status': '{key}'",
                    )

        response: list[str] = []
        response.extend([f"available_movie: {movie}" for movie in self.movies])
        response.extend([f"available_client: {client}" for client in self.clients])
        if not self.oneshot:
            response.extend(
                [f"available_script: {script}" for script in await self.list_scripts()],
            )
        if self.slot.background:
            playing_background = self.slot.background.movie.name
        else:
            playing_background = "<none>"
        response.append(f"playing_background_movie: {playing_background}")
        if self.slot.playing is not None and self.slot.playing.priority == "foreground":
            playing_foreground = self.slot.playing.movie.name
        else:
            playing_foreground = "<none>"
        response.append(f"playing_foreground_movie: {playing_foreground}")

        playing_urgents: list[str] = []

        if self.slot.playing is not None:
            if self.slot.playing.priority == "urgent":
                playing_urgents.append(self.slot.playing.movie.name)
        if self.slot.urgents:
            playing_urgents.extend(
                [playing.movie.name for playing in self.slot.urgents]
            )
        if not playing_urgents:
            playing_urgents.append("<none>")
        playing_urgents_str = " ".join(playing_urgents)

        response.append(f"playing_urgent_movies: {playing_urgents_str}")
        response.extend(
            [
                f"running_client: {name}"
                for name, value in self.clients.items()
                if value["task"]
            ],
        )
        response.append(
            f"intensity: {self.intensity}",
        )
        response.append(
            f"socket_path: {self.configuration.socket_path}",
        )
        response.append(
            f"keyboard_device: {self.configuration.keyboard_device}",
        )
        response.append(
            f"hidraw_device: {self.configuration.hidraw_device}",
        )
        return response

    async def list_scripts(self) -> list[str]:
        return [
            file.name
            for path in self.scripts_paths
            for file in path.glob("*")
            if file.is_file()
        ]

    async def run_client(self, message: message_t) -> list[str]:
        for key, value in message:
            match key:
                case "action":
                    pass
                case "name":
                    name = value
                case _:
                    raise InvalidConfigurationError(
                        f"unknown parameter for action 'load': '{key}'",
                    )

        if not name:
            raise InvalidConfigurationError(
                "Command 'run_client' needs a client name.",
            )
        if name not in self.clients:
            raise InvalidConfigurationError(
                "Command 'run_client' invalid client name.",
            )
        if self.clients[name]["task"] is not None:
            raise InvalidConfigurationError(
                "Command 'run_client' client is already running.",
            )

        client_class = self.clients[name]["klass"]
        instance = client_class(server=self, configuration=self.configuration)
        self.clients[name]["task"] = asyncio.create_task(
            instance.start(self.clients[name]),
        )
        self.clients[name]["task"]

        return ["ok"]

    async def stop_client(self, message: message_t) -> list[str]:
        for key, value in message:
            match key:
                case "action":
                    pass
                case "name":
                    name = value
                case _:
                    raise InvalidConfigurationError(
                        f"unknown parameter for action 'load': '{key}'",
                    )

        if not name:
            raise InvalidConfigurationError(
                "Command 'run_client' needs a client name.",
            )
        if name not in self.clients:
            raise InvalidConfigurationError(
                "Command 'run_client' invalid client name.",
            )
        if not (task := self.clients[name]["task"]):
            raise InvalidConfigurationError(
                f"Command 'run_client' client '{name}' is not running.",
            )
        task.cancel()  # type:ignore[attr-defined]
        self.clients[name]["task"] = None

        return ["ok"]

    async def run_script_file(self, message: message_t) -> list[str]:
        filename = ""
        for key, value in message:
            match key:
                case "action":
                    pass
                case "name":
                    filename = value
                case _:
                    raise InvalidConfigurationError(
                        f"unknown parameter for action 'load': '{key}'",
                    )

        if not filename:
            raise InvalidConfigurationError(
                "Command 'run_script' has not a 'name' key.",
            )
        try:
            file = next(
                file
                for path in self.scripts_paths
                for file in path.glob(filename)
                if file.is_file()
            )
        except StopIteration:
            raise InvalidConfigurationError(
                f"Can not load command file '{filename}'.",
            ) from None

        logger.debug(f"run_script_file(): running '{file!s}'.")
        response_lines: list[str] = []
        mbuffer = self.get_messages_reader()
        with file.open("rb") as f:
            for line in [line.decode("utf-8").strip() for line in f.readlines()]:
                receive_response_lines, _disconnected = await mbuffer.add(line)
                response_lines.extend(receive_response_lines)

        return response_lines

    def dump_movies(self) -> list[str]:
        lines: list[str] = []
        for movie in self.movies.values():
            lines.append(f"{movie.name=}")
            lines.append("times: " + str([frame.time for frame in movie.frames]))
            lines.append("frames:")
            for frame in movie.frames:
                for pixels_list in frame.pixels:
                    lines.append(  # noqa: PERF401
                        ", ".join(
                            (
                                f"[{pixel[0]:>3} {pixel[1]:>3} {pixel[2]:>3}]"
                                for pixel in pixels_list
                            ),
                        ),
                    )
                lines.append("")
            lines.append("")
        return lines

    async def writer(self) -> None:  # noqa: C901, PLR0912, PLR0915
        """Server writer task, periodically send frames to keyboard."""
        logger.info("writer(): Start.")
        playing_movie: PlayingMovie | None = None
        await_timeout: float | None = 0.0
        frame: frame_data_t

        while True:
            logger.info("writer(): sleep for %s.", await_timeout)
            try:
                # Wait until:
                #   - this frame times out or
                #   - a client message triggered the scheduler, which modified
                #     self.slot.playing, and so notified this writer() method by
                #     setting the event writer_event.
                await asyncio.wait_for(
                    writer_event.wait(),
                    timeout=await_timeout,
                )
                writer_event.clear()
            except TimeoutError:
                logger.info(
                    "writer(): new loop run: previous frame time expired.",
                )
            else:
                logger.info("writer(): new loop run: got notified to play next frame.")

            # playing_movie depends on scheduler decissions. Do not let a client
            # incoming message call the scheduler and modify self.slots until
            # this loop run finished.
            async with scheduler_lock:
                await_timeout = None
                next_timeout = TIMEOUT_DISABLE

                # Set playing_movie
                if self.slot.playing:
                    if playing_movie is not self.slot.playing:
                        # Scheduler changed slot.playing, it is not the same it was on
                        # our previous run. Store what is the new playing movie
                        playing_movie = self.slot.playing
                        logger.info(
                            "writer(): start playing new movie: %s.",
                            playing_movie.movie.name,
                        )
                        # playing_movie.position = 0
                    elif not playing_movie.ended():
                        # Keep playing the movie we were playing on our previous run.
                        logger.info(
                            "writer(): continue playing movie: %s.",
                            playing_movie.movie.name,
                        )
                        # Increase the frame position.
                        playing_movie.position += 1
                    elif (
                        playing_movie.ended() and playing_movie.priority == "background"
                    ):
                        # Repeat background movie from the beginning.
                        logger.info(
                            "writer(): restart background movie movie: %s.",
                            playing_movie.movie.name,
                        )
                        # Increase the frame position.
                        playing_movie.position = 0
                    else:
                        # Previously playing movie (foreground or urgent) has ended.
                        logger.info("writer(): ended playing last movie.")
                        playing_movie = None
                        self.slot.playing = None
                        # Scheduler will set self.slot.playing to the appropiate movie,
                        # if there is any.
                        await self.movie_scheduler(
                            notify_writer=False,
                            movie_ended=True,
                        )
                        if self.slot.playing:
                            playing_movie = self.slot.playing
                            logger.info(
                                "writer(): start playing new movie: %s.",
                                playing_movie.movie.name,
                            )
                        else:
                            logger.info("writer(): no movie scheduled to play.")
                            if self.oneshot:
                                # In oneshot mode, exit.
                                return

                # Send next playing movie frame to keyboard.
                if playing_movie:
                    logger.debug(
                        "writer(): playing frame %s",
                        playing_movie.position + 1,
                    )
                    current_frame = playing_movie.movie.frames[playing_movie.position]
                    logger.debug(
                        "writer(): playing next frame: index=%s.",
                        playing_movie.position,
                    )
                    logger.debug(
                        "writer(): playing next frame: %s.",
                        current_frame.pixels,
                    )

                    if self.intensity == 1.0:
                        frame = current_frame.pixels
                    else:
                        frame = [
                            [
                                [
                                    min(int(component * self.intensity), 255)
                                    for component in pixel
                                ]
                                for pixel in row
                            ]
                            for row in current_frame.pixels
                        ]
                    send_frame_to_keyboard(
                        frame=frame,
                        hidraw=self.hidraw_device,
                    )
                    next_timeout = playing_movie.movie.frames[
                        playing_movie.position
                    ].time

                    if next_timeout == TIMEOUT_DISABLE:
                        await_timeout = None  # This frame stays forever
                    elif next_timeout == 0:
                        # Don't wait between frame waits (but still use a low timeout).
                        await_timeout = 0.005
                    elif next_timeout > 0:
                        await_timeout = next_timeout


def message_keyvalues(lines: list[str]) -> message_t:
    """Return list of key/value tuples from raw input data."""
    # Join all the lines and split on "key=value".
    single_line_text = "\n".join(lines).replace("\n", " ")
    parts = [
        part
        for part in re.split(r"([a-z_]+)=", single_line_text, flags=re.IGNORECASE)
        if part.strip()
    ]
    try:
        # Return list of tuples(key, value)
        return [(parts[i], parts[i + 1].strip()) for i in range(0, len(parts), 2)]
    except IndexError:
        raise InvalidConfigurationError(
            "user supplied configuration can contain 'key=<string>' data only",
        ) from None
