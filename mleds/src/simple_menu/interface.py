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
import os
import subprocess
from typing import TYPE_CHECKING, Literal

from simple_menu.constants import text_substitutions
from simple_menu.exceptions import SystemQuit
from simple_menu.item.base import ItemTexts, ItemTextType

if TYPE_CHECKING:
    from simple_menu.item.base import BaseItem

next_action_t = Literal["selected", "restart", "back", "quit"]

logger = logging.getLogger(__name__)


class Interface:
    """End user interface.

    Attributes:
        title: menu title, shown to the user.
        last_item_id: item text on the previous menu execution.
        items: menu items.
    """

    def __init__(
        self,
        title: str,
        last_item_id: str,
        items: list["BaseItem"],
    ) -> None:
        self.title = title
        self.last_item_id = last_item_id
        self.items = items

    async def run(
        self,
        timeout: float,
    ) -> "tuple[next_action_t, BaseItem | None]":
        selected = next(
            (
                index
                for (index, item) in enumerate(self.items)
                if item.identifier == self.last_item_id
            ),
            0,
        )

        self.format_items_text()
        return await self.run_menu(selected, timeout)

    async def run_menu(
        self,
        selected: int,
        timeout: float,
    ) -> "tuple[next_action_t, BaseItem | None]":
        raise NotImplementedError

    def format_items_text(self) -> None:
        """Generate menu texts for items.

        Loops over self.items to set item.texts.menu string variable.
        """
        if non_raw_items := [i for i in self.items if i.texts.type != ItemTextType.raw]:
            type_len = max(
                len(self.formatted_texts(i.texts).type) for i in non_raw_items
            )
            category_len = max(
                len(self.formatted_texts(i.texts).category) for i in non_raw_items
            )
            subcategory_len = max(
                len(self.formatted_texts(i.texts).subcategory) for i in non_raw_items
            )
            status_len = max(
                len(self.formatted_texts(i.texts).status) for i in non_raw_items
            )
            text_len = max(
                len(self.formatted_texts(i.texts).text) for i in non_raw_items
            )

            for item in non_raw_items:
                formatted_texts = self.formatted_texts(item.texts)
                logger.debug(
                    "Building menu text for item '%s' '%s' '%s'.",
                    item.item_type,
                    item.texts,
                    formatted_texts,
                )
                text = f" {formatted_texts.type:<{type_len}}"
                if category_len:
                    text += f" {formatted_texts.category:>{category_len}}"
                if subcategory_len:
                    if formatted_texts.subcategory:
                        if category_len:
                            if formatted_texts.category:
                                text += "/"
                            else:
                                text += " "
                        text += f"{formatted_texts.subcategory:<{subcategory_len}}"
                    else:
                        text += " " * (subcategory_len + 1)
                if status_len:
                    text += f"  {formatted_texts.status:>{status_len}}"
                if text_len:
                    text += f"  {formatted_texts.text}"
                item.texts.menu = text
        for item in (i for i in self.items if i.texts.type == ItemTextType.raw):
            logger.debug(
                "Building menu text for item '%s' '%s'.",
                item.item_type,
                item.texts,
            )
            item.texts.menu = item.texts.text

    def formatted_texts(self, item: "ItemTexts") -> ItemTexts:
        """Return a formatted list of ItemText specific to this interface."""
        category = self.text_apply_tokens(item.category.strip())
        subcategory = self.text_apply_tokens(item.subcategory.strip())
        status = self.text_apply_tokens(item.status.strip())
        text = self.text_apply_tokens(item.text)
        type_ = self.text_apply_tokens(item.type)
        return ItemTexts(
            type=type_,
            category=category,
            subcategory=subcategory,
            status=status,
            text=text,
        )

    def text_apply_tokens(self, text: str) -> str:
        """Substitute special text tokens."""
        raise NotImplementedError

    def get_selected_item(self, selected_text: str) -> "BaseItem | None":
        try:
            _index, item = next(
                (index, item)
                for (index, item) in enumerate(self.items)
                if item.texts.menu == selected_text
            )
        except StopIteration:
            return None
        else:
            return item


class RofiInterface(Interface):
    def text_apply_tokens(self, text: str) -> str:
        """Substitute text tokens."""
        if os.environ.get("RAW", ""):
            return text
        for key, value in text_substitutions.items():
            text = text.replace(key, value)
        return text

    async def run_menu(  # noqa: C901, PLR0912
        self,
        selected: int,
        timeout: float,
    ) -> "tuple[next_action_t, BaseItem | None]":
        args = [
            "rofi",
            "-dmenu",
            "-tokenize",
            "-i",  # case insensitive
            "-p",  # prompt title
            self.title,
            "-selected-row",
            str(selected),
            "-kb-custom-1",
            "Control-r",
            "-kb-custom-2",
            "Control-q",
        ]
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
        )

        timeout_raised = False
        try:
            if timeout:
                stdout, _stderr = await asyncio.wait_for(
                    proc.communicate(
                        "\n".join([i.texts.menu for i in self.items]).encode(),
                    ),
                    timeout=timeout,
                )
            else:
                stdout, _stderr = await proc.communicate(
                    "\n".join([i.texts.menu for i in self.items]).encode(),
                )
        except asyncio.TimeoutError:
            timeout_raised = True
            proc.terminate()
            try:  # noqa: SIM105
                await proc.wait()
            except ProcessLookupError:
                pass  # Process may already be gone

        logger.info("rofi.returncode='%s'", proc.returncode)

        if timeout_raised:
            return "restart", None
        else:
            selected_text = stdout.decode().rstrip() or None
            if selected_text:
                selected_item = self.get_selected_item(selected_text)
            else:
                selected_item = None

            if proc.returncode == 10:  # Ctrl-r  # noqa: PLR2004
                next_action = "restart"
            elif proc.returncode == 11:  # Ctrl-q  # noqa: PLR2004
                raise SystemQuit
            elif proc.returncode == 1:  # Esc
                next_action = "back"
            elif selected_text:
                next_action = "selected"

            # Fixes:
            if selected_text and not selected_item:
                # User wrote some text in Rofi and pressed enter, but no line matched.
                next_action = "restart"

            return next_action, selected_item  # type:ignore[return-value]


class FzfInterface(Interface):
    def is_console(self) -> bool:
        """Return if program is running on a console."""
        tty_proc = subprocess.run(
            "tty",  # noqa: S607
            capture_output=True,
            check=True,
        )
        return tty_proc.stdout.decode("utf-8").startswith("/dev/tty")

    def text_apply_tokens(self, text: str) -> str:
        """Substitute text tokens."""
        if os.environ.get("RAW", "") or self.is_console():
            return text

        for key, value in text_substitutions.items():
            text = text.replace(key, value)

        return text

    async def run_menu(  # noqa: C901, PLR0912
        self,
        selected: int,
        timeout: float,
    ) -> "tuple[next_action_t, BaseItem | None]":
        args = [
            "fzf",
            "--no-sort",
            "--no-multi",
            "--ignore-case",
            "--bind",
            f"result:pos({selected + 1})",
            "--header",
            f"{self.title} >",
            "--expect=f5,esc,ctrl-r,enter,ctrl-q",
            # "--no-height",
        ]
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
        )

        timeout_raised = False
        try:
            if timeout:
                stdout, _stderr = await asyncio.wait_for(
                    proc.communicate(
                        "\n".join([i.texts.menu for i in self.items]).encode(),
                    ),
                    timeout=timeout,
                )
            else:
                stdout, _stderr = await proc.communicate(
                    "\n".join([i.texts.menu for i in self.items]).encode(),
                )
        except asyncio.TimeoutError:
            timeout_raised = True
            proc.terminate()
            try:  # noqa: SIM105
                await proc.wait()
            except ProcessLookupError:
                pass  # Process may already be gone

        logger.info("fzf.returncode='%s'", proc.returncode)

        if timeout_raised:
            return "restart", None
        else:
            lines = stdout.decode().splitlines()
            if lines:
                key = lines[0].rstrip()
                if len(lines) == 2:  # noqa: PLR2004
                    selected_text = lines[1].rstrip()
                    selected_item = self.get_selected_item(selected_text)
                else:
                    # User pressed enter before fzf received input.
                    selected_text, selected_item = None, None
            else:
                key = None
                selected_text, selected_item = None, None

            if key in {"ctrl-r", "f5"}:
                next_action = "restart"
            elif key == "ctrl-q":
                raise SystemQuit
            elif key == "esc":
                next_action = "back"
            elif selected_text:
                next_action = "selected"
            elif selected_text is None:  # fzf exited before received input.
                next_action = "restart"
            else:
                next_action = "back"

            return next_action, selected_item  # type:ignore[return-value]
