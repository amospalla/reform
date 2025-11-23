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

import dataclasses
import grp
import logging
import os
import pwd
import tomllib
from pathlib import Path

from mleds.constants import PROGRAM_NAME
from mleds.mnt import get_hidraw_device, get_keyboard_device
from mleds.movie import priority_t

logger = logging.getLogger(__name__)


def default_keypresses_keyboard_layout() -> list[str]:
    return [
        "ESC GRAVE",
        "1 F1",
        "2 F2",
        "3 F3",
        "4 F4",
        "5 F5",
        "6 F6",
        "7 F7",
        "8 F8",
        "9 F9",
        "0 F10",
        "BACKSPACE DELETE",
        #
        "TAB",
        "Q F11",
        "W F12",
        "E F13",
        "R",
        "T",
        "Y",
        "U",
        "I",
        "O LEFTBRACE",
        "P RIGHTBRACE",
        "SEMICOLON",
        #
        "LEFTCTRL",
        "A",
        "S",
        "D",
        "F",
        "G",
        "H",
        "J",
        "K",
        "L",
        "APOSTROPHE",
        "ENTER",
        #
        "LEFTSHIFT",
        "Z",
        "X",
        "C",
        "V",
        "B",
        "N",
        "M",
        "COMMA",
        "DOT",
        "UP PAGEUP",
        "RIGHTALT RIGHTSHIFT",
        #
        "unset",
        "LEFTMETA RIGHTMETA",
        "LEFTALT RIGHTALT",
        "BACKSLASH",
        "EQUAL",
        "SPACE",
        "SPACE",
        "MINUS",
        "SLASH",
        "LEFT HOME",
        "DOWN PAGEDOWN",
        "RIGHT END",
        #
        "unset",
        "unset",
        "unset",
        "unset",
        "unset",
        "unset",
        "unset",
        "unset",
        "unset",
        "unset",
        "unset",
        "unset",
    ]


default_battery_configuration = {
    "battery_border_color": "#3d1986",
    "battery_increase_color_start": "#206000",
    "battery_increase_color_end": "#00a000",
    "battery_decrease_color_start": "#303000",
    "battery_decrease_color_end": "#806000",
    "battery_charging_color": "#008000",
    "battery_discharging_color": "#380000",
    "battery_notification_events": [
        # Up
        "33 34",
        "50 51",
        "70 71",
        "84 85",
        # Down
        "66 65",
        "33 32",
        "16 15",
        "6 5",
    ],
}


@dataclasses.dataclass
class Configuration:
    keyboard_device: Path
    hidraw_device: Path
    socket_path: Path
    keypresses_keyboard_layout: list[str]
    keypresses_priority: priority_t
    loads_path: list[Path]
    scripts_paths: list[Path]
    socket_user: int
    socket_group: int
    socket_mode: int
    battery_border_color: str
    battery_increase_color_start: str
    battery_increase_color_end: str
    battery_decrease_color_start: str
    battery_decrease_color_end: str
    battery_charging_color: str
    battery_discharging_color: str
    battery_notification_events: list[tuple[int, int]]


def configuration_dir_paths() -> list[Path]:
    dir_paths: list[Path] = []
    if "XDG_CONFIG_HOME" in os.environ:
        dir_path = Path(os.environ["XDG_CONFIG_HOME"])
    else:
        dir_path = Path.home() / ".config"

    dir_paths.append(dir_path / PROGRAM_NAME)
    dir_paths.append(Path("/etc/") / PROGRAM_NAME)
    return dir_paths


def default_configuration_file() -> Path | None:
    for dir_path in configuration_dir_paths():
        file_path = dir_path / f"{PROGRAM_NAME}.toml"
        if file_path.exists():
            return file_path
    return None


def source_files_paths(subfolder: str) -> list[Path]:
    dir_paths: list[Path] = []
    if "XDG_CONFIG_HOME" in os.environ:
        dir_path = Path(os.environ["XDG_CONFIG_HOME"]) / PROGRAM_NAME / subfolder
    else:
        dir_path = Path.home() / ".config" / PROGRAM_NAME / subfolder

    if dir_path.exists():
        dir_paths.append(dir_path)
    dir_paths.append(Path("/etc/") / PROGRAM_NAME / subfolder)

    return [dir_path for dir_path in dir_paths if dir_path.exists()]


def default_socket_path() -> Path:
    # Return environment MLEDS_SOCKET if exists
    if f"{PROGRAM_NAME}_SOCKET".upper() in os.environ:
        return Path(f"{PROGRAM_NAME}_SOCKET".upper())

    # If root return system wide socket
    if os.getuid() == 0:
        return Path(f"/var/run/{PROGRAM_NAME}.sock")

    # If XDG_RUNTIME_DIR exists return this
    if runtime_dir := os.environ.get("XDG_RUNTIME_DIR"):
        return Path(runtime_dir) / f"{PROGRAM_NAME}.sock"

    # Fallback to /tmp
    return Path(f"/tmp/{PROGRAM_NAME}.sock")  # noqa: S108


def get_configuration(  # noqa: C901, PLR0912
    config_file: Path | None = None,
    keyboard_device: Path | None = None,
    hidraw_device: Path | None = None,
    socket_path: Path | None = None,
) -> Configuration:
    config_file = config_file or default_configuration_file()
    logger.info("Loading configuration from file '%s'.", config_file)
    if config_file:
        with config_file.open("rb") as f:
            data = tomllib.load(f)
            # Make Path from str
            for path in (
                "keyboard_device",
                "hidraw_device",
                "socket_device",
            ):
                if path in data:
                    data[path] = Path(data[path])
            if "socket_path" in data:
                data["socket_path"] = Path(data["socket_path"])
    else:
        data = {}

    for k, v in default_battery_configuration.items():
        if k not in data:
            data[k] = v

    data["battery_notification_events"] = [
        (int(event.split()[0]), int(event.split()[1]))
        for event in data["battery_notification_events"]
    ]

    logger.debug("Configuration data loaded from file: '%s'.", data)

    if keyboard_device:
        data["keyboard_device"] = keyboard_device
    elif "keyboard_device" not in data:
        data["keyboard_device"] = get_keyboard_device()

    if hidraw_device:
        data["hidraw_device"] = hidraw_device
    elif "hidraw_device" not in data:
        data["hidraw_device"] = get_hidraw_device()

    if socket_path:
        data["socket_path"] = socket_path
    elif "socket_path" not in data:
        data["socket_path"] = default_socket_path()

    data.setdefault(
        "keypresses_keyboard_layout",
        default_keypresses_keyboard_layout(),
    )
    data.setdefault("keypresses_priority", "foreground")

    if "socket_user" in data:
        if isinstance(data["socket_user"], int):
            uid = data["socket_user"]
        else:
            uid = pwd.getpwnam(data["socket_user"]).pw_uid
    else:
        uid = -1

    if "socket_group" in data:
        if isinstance(data["socket_group"], int):
            gid = data["socket_group"]
        else:
            gid = grp.getgrnam(data["socket_group"]).gr_gid
    else:
        gid = -1

    if "socket_mode" in data:
        socket_mode = int(data["socket_mode"], 8)
    else:
        socket_mode = 0o660

    configuration = Configuration(
        keyboard_device=data["keyboard_device"],
        hidraw_device=data["hidraw_device"],
        socket_path=data["socket_path"],
        loads_path=source_files_paths("load.d"),
        scripts_paths=source_files_paths("scripts.d"),
        keypresses_keyboard_layout=[
            value for value in data["keypresses_keyboard_layout"] if value
        ],
        keypresses_priority=data["keypresses_priority"],
        socket_user=uid,
        socket_group=gid,
        socket_mode=socket_mode,
        battery_border_color=data["battery_border_color"],
        battery_increase_color_start=data["battery_increase_color_start"],
        battery_increase_color_end=data["battery_increase_color_end"],
        battery_decrease_color_start=data["battery_decrease_color_start"],
        battery_decrease_color_end=data["battery_decrease_color_end"],
        battery_charging_color=data["battery_charging_color"],
        battery_discharging_color=data["battery_discharging_color"],
        battery_notification_events=data["battery_notification_events"],
    )

    logger.info("[Configuration] %s.", configuration)

    return configuration
