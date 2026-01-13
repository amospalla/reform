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

import asyncio
import logging

from simple_menu.constants import QUIT_EXIT_CODE
from simple_menu.exceptions import SystemQuit

from .base import BaseItem

logger = logging.getLogger(__name__)


class Item(BaseItem):
    item_type = "Item"

    async def execute(self) -> None:
        """Run external program action."""
        logger.debug("%s.execute(): Start", self.item_type)
        logger.debug("%s.execute(): self.value='%s'", self.item_type, self.value)

        if self.value:
            command = self.value.split(self.delimiter)
            logger.debug("%s.execute(): command='%s'", self.item_type, command)
            proc = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()

            if proc.returncode == QUIT_EXIT_CODE:
                raise SystemQuit

            logger.debug("%s.execute(): End", self.item_type)
