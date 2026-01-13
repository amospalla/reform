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

from simple_menu.interface import FzfInterface, Interface, RofiInterface

from .base import BaseItem, DecodeStringError, ItemTextType

logger = logging.getLogger(__name__)


class Menu(BaseItem):
    """Menu class which shows its items and executes the selected.

    Attributes:
        items: List of tuples that define the items: tuple(item class, item value).
    """

    item_type = "Menu"
    title: str

    def value2menu_options(self, value: str) -> tuple[str, bool, float, str]:
        """Given a string value return menu options."""
        title = "Menu"
        loop_timeout = 0.0
        keep_opened = True
        tokens = value.split(self.configuration.token_separators[0])
        while tokens:
            match tokens[0].strip().lower():
                case "title":
                    title = tokens[1]
                    tokens = tokens[2:]
                case "keep-opened":
                    keep_opened = bool(int(tokens[1]))
                    tokens = tokens[2:]
                case "loop-timeout":
                    loop_timeout = float(tokens[1])
                    tokens = tokens[2:]
                case _:
                    break

        return (
            title,
            keep_opened,
            loop_timeout,
            self.configuration.token_separators[0].join(tokens),
        )

    def __init__(  # type:ignore[no-untyped-def]
        self,
        menu_items: list[tuple[type[BaseItem], str]] | None = None,
        *args,
        **kwargs,
    ) -> None:
        """Menu initialization."""
        super().__init__(*args, **kwargs)
        self.title, self.keep_opened, self.loop_timeout, self.value = (
            self.value2menu_options(self.value)
        )
        self.items: list[tuple[type[BaseItem], str]] = menu_items or []

    async def execute(self) -> None:
        selection = ""
        if self.loop_timeout:  # Run in loop until menu stops or user stops it.
            while True:
                action, selection = await self.show(
                    selection,
                    loop_timeout=self.loop_timeout,  # used by interface.run_menu()
                )
                if action in {"back", ""}:
                    break

        # Run normally
        while True:
            action, selection = await self.show(
                selection,
                loop_timeout=0.0,
            )

            if not self.keep_opened or action in {"back", ""}:
                break

    async def set_items(self) -> None:
        """Function to inspect/modify self.items, called just before menu is shown."""

    async def set_title(self) -> None:
        """This function is to be overridden to inspect or modify self.title."""

    async def show(self, last_item_id: str, loop_timeout: float) -> tuple[str, str]:  # noqa: C901
        """Show menu and execute the selected item."""
        fn_name = f"{self.item_type}.show()"
        logger.debug("%s: Start.", fn_name)

        # Empty global shared object, next run starts from zero.
        self.shared.clear()
        await self.set_items()
        await self.set_title()

        items_instances = [
            klass(
                configuration=self.configuration,
                value=value,
            )
            for klass, value in self.items
        ]

        try:
            await asyncio.gather(*[item.set_text_wrapper() for item in items_instances])
        except DecodeStringError as e:
            logger.error(f"Could not read item text: {e}.")  # noqa: TRY400
            return "", ""

        match self.configuration.interface:
            case "rofi":
                interface_class: type[Interface] = RofiInterface
            case "fzf":
                interface_class = FzfInterface

        interface = interface_class(
            title=self.title,
            last_item_id=last_item_id,
            items=[item for item in items_instances if item.visible],
        )
        action, selected_item = await interface.run(
            timeout=loop_timeout,
        )

        if action == "selected" and loop_timeout:
            action = "back"

        if selected_item:
            logger.info(
                '%s: next_action="%s" selected_item="%s".',
                fn_name,
                action,
                selected_item.identifier,
            )
        else:
            logger.info(
                "%s: next_action='%s', no selected item.",
                fn_name,
                action,
            )
        # if selected_item is None:
        #     # Rofi did close before selecting any item
        #     return next_action, ""
        if action == "restart":
            logger.info(
                "%s: user requested a menu restart.",
                fn_name,
            )
        elif action == "back":
            logger.info(
                "%s: user requested a menu exit.",
                fn_name,
            )
        elif action == "selected":
            logger.info(
                "%s: execute selected item '%s'.",
                fn_name,
                selected_item.identifier,  # type:ignore[union-attr]
            )
            if selected_item.texts.type != ItemTextType.notification:  # type:ignore[union-attr]
                await selected_item.execute()  # type:ignore[union-attr]

        if selected_item:
            return action, selected_item.identifier
        else:
            return action, ""
