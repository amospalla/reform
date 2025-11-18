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

import logging
import re
from pathlib import Path

from mleds.constants import COLOR_BLACK

HIDRAW_RE_PATTERN = r"^HID_NAME=MNT Pocket Reform Input.*"
KEYBOARD_DEVICE_PATTERN = "usb-MNT_Pocket_Reform_Input_*-event-kbd"

logger = logging.getLogger(__name__)


def get_hidraw_device() -> Path:
    """Return hidraw device for this MNT Pocket Reform machine."""
    for hidraw_device_path in Path("/sys/class/hidraw/").glob("*"):
        logger.info(
            "Check if hidraw device is a MNT Pocket Reform one %s.",
            hidraw_device_path,
        )
        with (hidraw_device_path / "device/uevent").open("r") as f:
            if re.search(HIDRAW_RE_PATTERN, f.read(), re.MULTILINE):
                return Path("/dev/" + hidraw_device_path.name)
    raise RuntimeError("No hidraw device found")


def blank_hidraw(hidraw: Path) -> None:
    """Send command to set keyboard leds to black."""
    with hidraw.open("wb") as k:
        k.write(b"xLRGB" + bytes(COLOR_BLACK))


def get_keyboard_device() -> Path:
    """Return keyboard input device for this MNT Pocket Reform machine."""
    for keyboard_device_path in Path("/dev/input/by-id").glob(
        KEYBOARD_DEVICE_PATTERN,
    ):
        return keyboard_device_path
    raise RuntimeError("No keyboard device found")
