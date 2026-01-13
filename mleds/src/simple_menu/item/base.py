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
import enum
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from simple_menu.configuration import Configuration


logger = logging.getLogger(__name__)


class ItemTextType(enum.StrEnum):
    menu = "<menu>"
    action = "<action>"
    notification = "<notification>"
    raw = ""


@dataclass
class ItemTexts:
    type: str = ItemTextType.raw
    category: str = ""
    subcategory: str = ""
    status: str = ""
    text: str = ""
    menu: str = ""  # Used by Interface


class DecodeStringError(Exception):
    pass


class BaseItem:
    """Base class for Items.

    Attributes:
        item_type: item name, used for logging.
        lock: attribute to instantiate a shared object for all the class instances.
        shared: dictionary to store child classes shared data.
        configuration: user configuration.
    """

    item_type: str
    lock: asyncio.Lock
    shared: ClassVar[dict[str, Any]] = {}

    def __init__(
        self,
        configuration: "Configuration",
        value: str = "",
    ) -> None:
        self.configuration = configuration
        self.texts, self.value = self.str2item_texts(
            value,
            # lazy=True,
            token_separator=self.delimiter,
        )
        self.raw_value = value

    async def get_shared_data(self) -> Any:  # noqa:ANN401
        """Return the shared class object.

        This is an end method user. Takes care of checking if shared data is
        initialized and/or initialize it within a class lock. Finally it
        returns the shared object.
        """
        async with self.lock:
            logger.debug("Shared data for %s: entered Lock.", self.item_type)
            if self.item_type not in self.shared:
                logger.debug("Shared data for %s: not initialized.", self.item_type)
                # Each class must have its own lock=asyncio.Lock() instance
                self.shared[self.item_type] = await self.set_shared_data()
                logger.debug("Shared data for %s: set.", self.item_type)
            else:
                logger.debug("Shared data for %s: already initialized.", self.item_type)
        return self.shared[self.item_type]

    async def set_text_wrapper(self) -> None:
        """Calls the user function to set the item text. Wrapped to get elapsed time."""
        start_time = time.perf_counter()

        await self.set_text()

        elapsed = time.perf_counter() - start_time
        logger.info(
            '%s.set_text(): %ssec value="%s" "%s/%s/%s/%s/%s"',
            self.item_type,
            f"{elapsed:.3f}",
            self.value,
            self.texts.type,
            self.texts.category,
            self.texts.subcategory,
            self.texts.status,
            self.texts.text,
        )

    async def set_text(self) -> None:
        """Build self.texts which will be used as menu entry text by inteface.

        An empty string means the item is disabled.
        """

    @staticmethod
    def str2item_texts(
        text: str,
        token_separator: str,
    ) -> tuple[ItemTexts, str]:
        """Given a string, return an ItemTexts and the remaining value."""
        logger.debug("str2item_texts(%s).", text)

        tokens = text.split(token_separator)

        if len(tokens) > 4 and tokens[0].strip() in {i.name for i in ItemTextType}:  # noqa: PLR2004
            item_type = ItemTextType[tokens[0].strip()]
            text = tokens[4]
            if item_type != ItemTextType.raw:
                text = text.strip()
            return ItemTexts(
                type=item_type,
                category=tokens[1].strip(),
                subcategory=tokens[2].strip(),
                status=tokens[3].strip(),
                text=text,
            ), token_separator.join(tokens[5:])

        return ItemTexts(), text

    async def set_shared_data(self) -> Any:  # noqa: ANN401
        """Sets type(self).shared."""
        raise NotImplementedError

    async def execute(self) -> None:
        """Run this item action."""
        raise NotImplementedError

    @property
    def visible(self) -> bool:
        return bool(self.texts.text)

    @property
    def identifier(self) -> str:
        return f"{self.item_type}:{self.raw_value}"

    @property
    def delimiter(self) -> str:
        return self.configuration.token_separators[0]
