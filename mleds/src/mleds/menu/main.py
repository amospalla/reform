import asyncio
from pathlib import Path

from mleds.communications import Status, messages_client, parse_status
from simple_menu.configuration import get_configuration
from simple_menu.item.base import ItemTextType
from simple_menu.item.item import Item
from simple_menu.item.menu import Menu


async def main_menu(socket_path: Path) -> None:
    configuration = get_configuration(
        config_file=None,
        requested_interface="fzf",
        requested_token_separators=[],
    )
    token_separator = configuration.token_separators[0]

    await Menu(
        configuration=configuration,
        value=token_separator.join(("title", "mleds main menu")),
        menu_items=[
            *[
                (
                    MenuQueue,
                    token_separator.join((queue_name, str(socket_path))),
                )
                for queue_name in ("background", "foreground", "urgent")
            ],
            (MenuClient, str(socket_path)),
            (MenuScripts, str(socket_path)),
            (ItemIntensity, token_separator.join((str(socket_path), "upper"))),
            (ItemIntensity, token_separator.join((str(socket_path), "lower"))),
        ],
    ).execute()


class MenuQueue(Menu):
    item_type = "MenuQueue"

    async def set_title(self) -> None:
        queue, _ = self.value.split(self.delimiter)
        self.title = f"queue: {queue}"

    async def set_text(self) -> None:
        self.texts.type = ItemTextType.menu
        queue, socket_path_str = self.value.split(self.delimiter)
        socket_path = Path(socket_path_str)
        status = parse_status(
            await messages_client(
                message="action=status end=true",
                socket_path=socket_path,
            ),
        )
        self.texts.category = "queue"
        self.texts.subcategory = queue

        match queue:
            case "background":
                if status.playing_background != "blank":
                    self.texts.status = "<running>"
                    self.texts.text = status.playing_background
                else:
                    self.texts.text = "<empty>"
            case "foreground":
                if status.playing_foreground is not None:
                    self.texts.status = "<running>"
                    self.texts.text = status.playing_foreground
                else:
                    self.texts.text = "<empty>"
            case "urgent":
                if status.playing_urgent:
                    self.texts.status = "<running>"
                    self.texts.text = ",".join(status.playing_urgent)
                else:
                    self.texts.text = "<empty>"

    async def set_items(self) -> None:
        queue, socket_path_str = self.value.split(self.delimiter)
        socket_path = Path(socket_path_str)
        status = parse_status(
            await messages_client(
                message="action=status end=true",
                socket_path=socket_path,
            ),
        )
        self.items = [
            (
                ItemQueueStop,
                self.delimiter.join(
                    (
                        queue,
                        socket_path_str,
                    ),
                ),
            )
        ]
        self.items.extend(
            [
                (
                    ItemMovie,
                    self.delimiter.join(
                        (
                            queue,
                            socket_path_str,
                            movie,
                        ),
                    ),
                )
                for movie in status.available_movies
                if movie != "blank" and not movie.startswith("hidden_")
            ],
        )


class MenuClient(Menu):
    item_type = "MenuClient"

    async def set_title(self) -> None:
        self.title = "Clients"

    async def set_text(self) -> None:
        self.texts.type = ItemTextType.menu
        status = parse_status(
            await messages_client(
                message="action=status end=true",
                socket_path=Path(self.value),
            ),
        )

        self.texts.subcategory = "clients"
        if status.running_clients:
            self.texts.status = "<running>"
            self.texts.text = ",".join(status.running_clients)
        else:
            self.texts.text = "<empty>"

    async def set_items(self) -> None:
        status = parse_status(
            await messages_client(
                message="action=status end=true",
                socket_path=Path(self.value),
            ),
        )
        self.items = [
            (
                ItemClient,
                self.delimiter.join((self.value, client_name)),
            )
            for client_name in status.available_clients
        ]


class ItemMovie(Item):
    item_type = "ItemMovie"
    lock = asyncio.Lock()

    async def set_shared_data(self) -> Status:
        _queue, socket_path_str, _movie_name = self.value.split(self.delimiter)
        return parse_status(
            await messages_client(
                message="action=status end=true",
                socket_path=Path(socket_path_str),
            ),
        )

    async def set_text(self) -> None:
        self.texts.type = ItemTextType.action
        queue, _socket_path_str, movie_name = self.value.split(self.delimiter)
        status = await self.get_shared_data()
        self.texts.category = "movie"
        self.texts.subcategory = "play"
        match queue:
            case "background":
                if movie_name == status.playing_background:
                    self.texts.status = "<running>"
            case "foreground":
                if status.playing_background:
                    if movie_name == status.playing_foreground:
                        self.texts.status = "<running>"
            case "urgent":
                if movie_name in status.playing_urgent:
                    self.texts.status = "<running>"
        self.texts.text = movie_name

    async def execute(self) -> None:
        queue, socket_path_str, movie_name = self.value.split(self.delimiter)
        await messages_client(
            message=f"action=play_movie name={movie_name} priority={queue} end=true",
            socket_path=Path(socket_path_str),
        )


class ItemQueueStop(Item):
    item_type = "ItemQueueStop"

    async def set_text(self) -> None:
        self.texts.type = ItemTextType.action
        self.texts.subcategory = "stop"
        self.texts.text = "stop playing movies"

    async def execute(self) -> None:
        queue, socket_path_str = self.value.split(self.delimiter)
        if queue == "background":
            await messages_client(
                message="action=play_movie name=blank priority=background end=true",
                socket_path=Path(socket_path_str),
            )
        else:
            await messages_client(
                message=f"action=stop_movie queue={queue} end=true",
                socket_path=Path(socket_path_str),
            )


class ItemClient(Item):
    item_type = "ItemClient"
    lock = asyncio.Lock()

    async def set_shared_data(self) -> Status:
        socket_path_str, _movie_name = self.value.split(self.delimiter)
        return parse_status(
            await messages_client(
                message="action=status end=true",
                socket_path=Path(socket_path_str),
            ),
        )

    async def set_text(self) -> None:
        self.texts.type = ItemTextType.action
        _socket_path_str, client_name = self.value.split(self.delimiter)
        status = await self.get_shared_data()
        if client_name in status.running_clients:
            self.texts.status = "<running>"
        self.texts.text = client_name

    async def execute(self) -> None:
        socket_path_str, client_name = self.value.split(self.delimiter)
        status = parse_status(
            await messages_client(
                message="action=status end=true",
                socket_path=Path(socket_path_str),
            ),
        )
        if client_name in status.running_clients:
            await messages_client(
                message=f"action=stop_client name={client_name} end=true",
                socket_path=Path(socket_path_str),
            )
        else:
            await messages_client(
                message=f"action=run_client name={client_name} end=true",
                socket_path=Path(socket_path_str),
            )


class ItemIntensity(Item):
    item_type = "ItemIntensity"

    async def set_text(self) -> None:
        socket_path_str, action = self.value.split(self.delimiter)
        status = parse_status(
            await messages_client(
                message="action=status end=true",
                socket_path=Path(socket_path_str),
            ),
        )
        self.texts.type = ItemTextType.action
        self.texts.subcategory = "intensity"
        self.texts.text = f"{status.intensity:4.2f} <{action}>"

    async def execute(self) -> None:
        socket_path_str, action = self.value.split(self.delimiter)
        symbol = {"upper": "+", "lower": "-"}[action]
        await messages_client(
            message=f"action=set_intensity value={symbol}0.05 end=true",
            socket_path=Path(socket_path_str),
        )


class MenuScripts(Menu):
    item_type = "MenuScripts"

    async def set_title(self) -> None:
        self.title = "Scripts"

    async def set_text(self) -> None:
        self.texts.type = ItemTextType.menu
        self.texts.subcategory = "scripts"
        self.texts.text = "scripts"

    async def set_items(self) -> None:
        status = parse_status(
            await messages_client(
                message="action=status end=true",
                socket_path=Path(self.value),
            ),
        )
        self.items = [
            (
                ItemScript,
                self.delimiter.join((self.value, script_name)),
            )
            for script_name in status.available_scripts
        ]


class ItemScript(Item):
    item_type = "ItemScript"
    lock = asyncio.Lock()

    async def set_shared_data(self) -> Status:
        socket_path_str, _script_name = self.value.split(self.delimiter)
        return parse_status(
            await messages_client(
                message="action=status end=true",
                socket_path=Path(socket_path_str),
            ),
        )

    async def set_text(self) -> None:
        self.texts.type = ItemTextType.action
        _socket_path_str, script_name = self.value.split(self.delimiter)
        self.texts.text = script_name

    async def execute(self) -> None:
        socket_path_str, script_name = self.value.split(self.delimiter)
        await messages_client(
            message=f"action=run_script name={script_name} end=true",
            socket_path=Path(socket_path_str),
        )
