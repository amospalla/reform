import asyncio

from mleds.communications import Status, messages_client, parse_status
from mleds.shared import shared
from simple_menu.configuration import get_configuration
from simple_menu.item.base import ItemTextType
from simple_menu.item.item import Item
from simple_menu.item.menu import Menu


async def communicate(message: str) -> list[str]:
    if shared["socket_path"] is not None:
        return await messages_client(
            message=message,
            socket_path=shared["socket_path"],
        )
    else:
        messages_reader = shared["server_instance"].get_messages_reader(use_lock=True)
        for line in message.splitlines():
            response, _disconnected = await messages_reader.add(line)
        return response


async def main_menu(include_quit: bool) -> None:
    configuration = get_configuration(
        config_file=None,
        requested_interface="fzf",
        requested_token_separators=[],
    )
    token_separator = configuration.token_separators[0]
    menu_items = [
        *[
            (MenuQueue, queue_name)
            for queue_name in ("background", "foreground", "urgent")
        ],
        (MenuClient, ""),
        (MenuScripts, ""),
        (ItemIntensity, "upper"),
        (ItemIntensity, "lower"),
    ]
    if include_quit:
        menu_items.append((ItemQuit, ""))
    await Menu(
        configuration=configuration,
        value=token_separator.join(("title", "mleds main menu")),
        menu_items=menu_items,
    ).execute()


class MenuQueue(Menu):
    item_type = "MenuQueue"

    async def set_title(self) -> None:
        queue = self.value
        self.title = f"queue: {queue}"

    async def set_text(self) -> None:
        self.texts.type = ItemTextType.menu
        queue = self.value
        status = parse_status(
            await communicate(message="action=status end=true"),
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
        queue = self.value
        status = parse_status(
            await communicate(message="action=status end=true"),
        )
        self.items = [(ItemQueueStop, queue)]
        self.items.extend(
            [
                (
                    ItemMovie,
                    self.delimiter.join((queue, movie)),
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
            await communicate(message="action=status end=true"),
        )

        self.texts.subcategory = "clients"
        if status.running_clients:
            self.texts.status = "<running>"
            self.texts.text = ",".join(status.running_clients)
        else:
            self.texts.text = "<empty>"

    async def set_items(self) -> None:
        status = parse_status(
            await communicate(message="action=status end=true"),
        )
        self.items = [
            (ItemClient, client_name) for client_name in status.available_clients
        ]


class ItemMovie(Item):
    item_type = "ItemMovie"
    lock = asyncio.Lock()

    async def set_shared_data(self) -> Status:
        return parse_status(
            await communicate(message="action=status end=true"),
        )

    async def set_text(self) -> None:
        self.texts.type = ItemTextType.action
        queue, movie_name = self.value.split(self.delimiter)
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
        queue, movie_name = self.value.split(self.delimiter)
        await communicate(
            message=f"action=play_movie name={movie_name} priority={queue} end=true",
        )


class ItemQueueStop(Item):
    item_type = "ItemQueueStop"

    async def set_text(self) -> None:
        self.texts.type = ItemTextType.action
        self.texts.subcategory = "stop"
        self.texts.text = "stop playing movies"

    async def execute(self) -> None:
        queue = self.value
        if queue == "background":
            message = "action=play_movie name=blank priority=background end=true"
        else:
            message = f"action=stop_movie queue={queue} end=true"
        await communicate(message=message)


class ItemClient(Item):
    item_type = "ItemClient"
    lock = asyncio.Lock()

    async def set_shared_data(self) -> Status:
        return parse_status(
            await communicate(message="action=status end=true"),
        )

    async def set_text(self) -> None:
        self.texts.type = ItemTextType.action
        client_name = self.value
        status = await self.get_shared_data()
        if client_name in status.running_clients:
            self.texts.status = "<running>"
        self.texts.text = client_name

    async def execute(self) -> None:
        client_name = self.value
        status = parse_status(
            await communicate(message="action=status end=true"),
        )
        if client_name in status.running_clients:
            message = f"action=stop_client name={client_name} end=true"
        else:
            message = f"action=run_client name={client_name} end=true"
        await communicate(message=message)


class ItemIntensity(Item):
    item_type = "ItemIntensity"

    async def set_text(self) -> None:
        action = self.value
        status = parse_status(
            await communicate(message="action=status end=true"),
        )
        self.texts.type = ItemTextType.action
        self.texts.subcategory = "intensity"
        self.texts.text = f"{status.intensity:4.2f} <{action}>"

    async def execute(self) -> None:
        action = self.value
        symbol = {"upper": "+", "lower": "-"}[action]
        await communicate(message=f"action=set_intensity value={symbol}0.05 end=true")


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
            await communicate(message="action=status end=true"),
        )
        self.items = [
            (ItemScript, script_name) for script_name in status.available_scripts
        ]


class ItemScript(Item):
    item_type = "ItemScript"
    lock = asyncio.Lock()

    async def set_shared_data(self) -> Status:
        return parse_status(
            await communicate(message="action=status end=true"),
        )

    async def set_text(self) -> None:
        self.texts.type = ItemTextType.action
        self.texts.text = self.value

    async def execute(self) -> None:
        script_name = self.value
        await communicate(message=f"action=run_script name={script_name} end=true")


class ItemQuit(Item):
    item_type = "ItemQuit"

    async def set_text(self) -> None:
        self.texts.type = ItemTextType.action
        self.texts.text = "<poweroff> Quit"

    async def execute(self) -> None:
        raise SystemExit
