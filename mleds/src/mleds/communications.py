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
from dataclasses import dataclass
from pathlib import Path

from mleds.shared import shared

logger = logging.getLogger(__name__)


async def messages_server(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    """Process incoming messages from client.

    This method is spawned once for each new client connection.
    """
    messages_reader = shared["server_instance"].get_messages_reader()
    disconnect = False

    try:
        while not disconnect:
            line = await reader.readline()
            if line in {b"", b"END\n"}:
                break
            logger.debug("Received line: %s.", line)

            response_lines, disconnect = await messages_reader.add(line.decode("utf-8"))

            if not response_lines:
                continue

            # Response lines is not empty, a new message was processed and a response
            # has been obtained. Send it back to the user.
            try:
                for response_line in [*response_lines, "END"]:
                    response_line_bytes = (response_line + "\n").encode("utf-8")
                    writer.write(response_line_bytes)
                    await writer.drain()  # let asyncio flush buffer
            except (ConnectionResetError, BrokenPipeError):
                logger.info("Client disconnected during write.")
                disconnect = True
                break

        logger.info("Client disconnected.")
    except (ConnectionResetError, BrokenPipeError):
        logger.info("Client disconnected before close completed.")
    except Exception:
        logger.exception("Error while processing message.")
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except (ConnectionResetError, BrokenPipeError):
            logger.info("Client disconnected before close completed.")


async def messages_client(message: str, socket_path: Path) -> list[str]:
    """Send messages to the server through socket and print its response."""
    logger.info("Start client message.")

    lines: list[str] = []
    reader, writer = await asyncio.open_unix_connection(socket_path)

    for query_line in [*message.splitlines(), "END"]:
        query_line_bytes = (query_line + "\n").encode("utf-8")
        writer.write(query_line_bytes)
        await writer.drain()  # let asyncio flush buffer

    while True:
        response_line_bytes = await reader.readline()
        if response_line_bytes in {b"", b"END\n"}:
            break
        response_line = response_line_bytes.decode("utf-8")
        lines.append(response_line.strip())

    writer.close()
    await writer.wait_closed()
    return lines


@dataclass
class Status:
    available_movies: list[str]
    available_clients: list[str]
    available_scripts: list[str]
    playing_background: str
    playing_foreground: None | str
    playing_urgent: list[str]
    running_clients: list[str]
    intensity: float
    socket_path: Path
    keyboard_device: Path
    hidraw_device: Path


def parse_status(lines: list[str]) -> Status:
    playing_background: str = next(
        line.replace("playing_background_movie: ", "")
        for line in lines
        if line.startswith("playing_background_movie: ")
    )

    playing_foreground: str | None = next(
        line.replace("playing_foreground_movie: ", "")
        for line in lines
        if line.startswith("playing_foreground_movie: ")
    )
    if playing_foreground == "<none>":
        playing_foreground = None

    playing_urgent = [
        movie
        for movie in next(
            line.replace("playing_urgent_movies: ", "")
            for line in lines
            if line.startswith("playing_urgent_movies: ")
        ).split(" ")
        if movie != "<none>"
    ]

    available_movies = [
        line.replace("available_movie: ", "")
        for line in lines
        if line.startswith("available_movie: ")
    ]

    available_scripts = [
        line.replace("available_script: ", "")
        for line in lines
        if line.startswith("available_script: ")
    ]

    available_clients = [
        line.replace("available_client: ", "")
        for line in lines
        if line.startswith("available_client: ")
    ]

    running_clients = [
        line.replace("running_client: ", "")
        for line in lines
        if line.startswith("running_client: ")
    ]

    intensity = float(
        next(
            line.replace("intensity: ", "")
            for line in lines
            if line.startswith("intensity: ")
        )
    )

    socket_path = Path(
        next(
            line.replace("socket_path: ", "")
            for line in lines
            if line.startswith("socket_path: ")
        )
    )

    hidraw_device = Path(
        next(
            line.replace("hidraw_device: ", "")
            for line in lines
            if line.startswith("hidraw_device: ")
        )
    )

    keyboard_device = Path(
        next(
            line.replace("keyboard_device: ", "")
            for line in lines
            if line.startswith("keyboard_device: ")
        )
    )
    return Status(
        available_movies=available_movies,
        available_clients=available_clients,
        available_scripts=available_scripts,
        playing_background=playing_background,
        playing_foreground=playing_foreground,
        playing_urgent=playing_urgent,
        running_clients=running_clients,
        intensity=intensity,
        socket_path=socket_path,
        hidraw_device=hidraw_device,
        keyboard_device=keyboard_device,
    )
