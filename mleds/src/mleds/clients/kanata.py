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
import re

from mleds.clients.base import Client

MOVIE_NAME = "hidden_kanata"
logger = logging.getLogger(__name__)


class Kanata(Client):
    def __init__(self, *args, **kwargs) -> None:  # type:ignore[no-untyped-def]
        super().__init__(*args, **kwargs)

    async def run(self) -> None:
        reader, _writer = await asyncio.open_connection(
            self.configuration.kanata_host,
            self.configuration.kanata_port,
        )
        logger.info(
            f"Connected to {self.configuration.kanata_host}:"
            f"{self.configuration.kanata_port}",
        )

        try:
            while True:
                line = await reader.readline()

                if not line:
                    print("Connection closed by remote host")
                    break
                text = line.decode().strip()
                logger.debug("Received from kanata: '%s'.", text)
                if match := re.match(r'{"LayerChange":{"new":"(.*)"}}', text):
                    layer = match.groups(0)[0]
                    await self.send_layer(layer)

        except asyncio.CancelledError:
            # Allow the task to be cancelled cleanly
            print("Read task cancelled")
            raise

    async def send_layer(self, name: str) -> None:
        if name in self.configuration.kanata_layers:
            message = [
                "action=add_movie",
                f"name={MOVIE_NAME}",
                "create_frames=true",
                "times=-1",
                "pixels=",
                *self.configuration.kanata_layers[name],
                "end=true",
                #
                "action=play_movie",
                f"name={MOVIE_NAME}",
                "priority=background",
                "end=true",
            ]
            await self.send_message(message=message)
        else:
            logger.error("Layer %s not defined", name)
