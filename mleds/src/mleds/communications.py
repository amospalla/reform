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
