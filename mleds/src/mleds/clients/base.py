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
"""Base class for clients."""

import asyncio
import logging
from typing import TYPE_CHECKING

from mleds.constants import Priority

if TYPE_CHECKING:
    from mleds.configuration import Configuration
    from mleds.server import ClientItem, Server

logger = logging.getLogger(__name__)


class Client:
    priority: Priority

    def __init__(self, server: "Server", configuration: "Configuration") -> None:
        self.server = server
        self.configuration = configuration

    async def start(self, client_item: "ClientItem") -> None:
        """Starts the client execution."""
        # Item of server.clients where this client is started from. Set task for later
        # cancellation.
        task = asyncio.create_task(self.run())
        client_item["task"] = task
        try:
            await task
        except Exception:
            logger.exception("Error while running client")

    async def run(self) -> None:
        raise NotImplementedError

    async def send_message(self, message: list[str]) -> None:
        """Sends a message to the server."""
        reader = self.server.get_messages_reader()
        for line in message:
            await reader.add(line)
