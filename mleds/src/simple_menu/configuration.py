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

import dataclasses
import logging
import os
import sys
from os import environ
from pathlib import Path
from shutil import which
from typing import Literal

import tomllib

from simple_menu.constants import PROGRAM_NAME, TOKEN_SEPARATORS, interface_t

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Configuration:
    helper_systemd_toggle_allowed: list[str]
    helper_zerotier_allowed: list[str]
    menu_sound_ignore_nodes: set[str]
    menu_syncthing_api_token: str
    menu_syncthing_api_url: str
    interface: interface_t
    token_separators: list[str]


def configuration_folders() -> list[Path]:
    dir_paths: list[Path] = []
    if "XDG_CONFIG_HOME" in os.environ:
        dir_path = Path(os.environ["XDG_CONFIG_HOME"])
    else:
        dir_path = Path.home() / ".config"

    dir_paths.append(dir_path / PROGRAM_NAME)
    dir_paths.append(Path("/etc/") / PROGRAM_NAME)
    return dir_paths


def default_configuration_file() -> Path | None:
    for dir_path in configuration_folders():
        file_path = dir_path / f"{PROGRAM_NAME}.toml"
        if file_path.exists():
            return file_path
    return None


def get_configuration(  # noqa: C901, PLR0912
    config_file: Path | None,
    requested_interface: interface_t | Literal["auto"],
    requested_token_separators: list[str],
) -> Configuration:
    config_file = config_file or default_configuration_file()
    logger.info("Loading configuration from file '%s'.", config_file)
    if config_file:
        with config_file.open("rb") as f:
            data = tomllib.load(f)
    else:
        data = {}

    logger.debug("Configuration data on disk was file: '%s'.", data)

    if requested_interface in ("fzf", "rofi"):
        interface = requested_interface
    elif "INTERFACE" in environ:
        interface = environ["INTERFACE"]
    elif "interface" in data:
        interface = data["interface"]
    else:
        interface = "auto"

    # Interface explicitly set to either rofi or fzf, either on command line,
    # environment variable or configuration file.
    if interface in ("rofi", "fzf"):
        if not which(interface):
            print(f"[Error] {interface} command is not available.")
            sys.exit(1)

    if interface == "auto":
        if ("WAYLAND_DISPLAY" in environ or "DISPLAY" in environ) and which("rofi"):
            interface = "rofi"
        else:
            interface = "fzf"

    if interface == "fzf":
        if not which("fzf"):
            print(f"[Error] {interface} command is not available.")
            sys.exit(1)

    if requested_token_separators:  # command line --token-separators
        token_separators = requested_token_separators
    elif "token_separators" in data:
        token_separators = data["token_separators"]
    else:
        token_separators = TOKEN_SEPARATORS

    configuration = Configuration(
        helper_systemd_toggle_allowed=data.get("helper_systemd_toggle_allowed", []),
        helper_zerotier_allowed=data.get("helper_zerotier_allowed", []),
        menu_sound_ignore_nodes=set(data.get("menu_sound_ignore_nodes", [])),
        menu_syncthing_api_token=data.get("menu_syncthing_api_token", ""),
        menu_syncthing_api_url=data.get("menu_syncthing_api_url", ""),
        interface=interface,  # type:ignore[arg-type]
        token_separators=token_separators,
    )

    logger.info("Using configuration: %s.", configuration)

    return configuration
