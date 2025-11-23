import asyncio
import logging
import os
import struct
from collections import deque
from collections.abc import AsyncGenerator
from pathlib import Path

logger = logging.getLogger(__name__)


INPUT_EVENT_FORMAT = "llHHI"  # timeval(sec,usec), type, code, value
EVENT_SIZE = struct.calcsize(INPUT_EVENT_FORMAT)

evdev_events = {
    1: {
        1: "KEY_ESC",
        2: "KEY_1",
        3: "KEY_2",
        4: "KEY_3",
        5: "KEY_4",
        6: "KEY_5",
        7: "KEY_6",
        8: "KEY_7",
        9: "KEY_8",
        10: "KEY_9",
        11: "KEY_0",
        12: "KEY_MINUS",
        13: "KEY_EQUAL",
        14: "KEY_BACKSPACE",
        15: "KEY_TAB",
        16: "KEY_Q",
        17: "KEY_W",
        18: "KEY_E",
        19: "KEY_R",
        20: "KEY_T",
        21: "KEY_Y",
        22: "KEY_U",
        23: "KEY_I",
        24: "KEY_O",
        25: "KEY_P",
        26: "KEY_LEFTBRACE",
        27: "KEY_RIGHTBRACE",
        28: "KEY_ENTER",
        29: "KEY_LEFTCTRL",
        30: "KEY_A",
        31: "KEY_S",
        32: "KEY_D",
        33: "KEY_F",
        34: "KEY_G",
        35: "KEY_H",
        36: "KEY_J",
        37: "KEY_K",
        38: "KEY_L",
        39: "KEY_SEMICOLON",
        40: "KEY_APOSTROPHE",
        41: "KEY_GRAVE",
        42: "KEY_LEFTSHIFT",
        43: "KEY_BACKSLASH",
        44: "KEY_Z",
        45: "KEY_X",
        46: "KEY_C",
        47: "KEY_V",
        48: "KEY_B",
        49: "KEY_N",
        50: "KEY_M",
        51: "KEY_COMMA",
        52: "KEY_DOT",
        53: "KEY_SLASH",
        54: "KEY_RIGHTSHIFT",
        55: "KEY_KPASTERISK",
        56: "KEY_LEFTALT",
        57: "KEY_SPACE",
        58: "KEY_CAPSLOCK",
        59: "KEY_F1",
        60: "KEY_F2",
        61: "KEY_F3",
        62: "KEY_F4",
        63: "KEY_F5",
        64: "KEY_F6",
        65: "KEY_F7",
        66: "KEY_F8",
        67: "KEY_F9",
        68: "KEY_F10",
        70: "KEY_SCROLLLOCK",
        71: "KEY_KP7",
        72: "KEY_KP8",
        73: "KEY_KP9",
        74: "KEY_KPMINUS",
        75: "KEY_KP4",
        76: "KEY_KP5",
        77: "KEY_KP6",
        78: "KEY_KPPLUS",
        79: "KEY_KP1",
        80: "KEY_KP2",
        81: "KEY_KP3",
        82: "KEY_KP1",
        83: "KEY_KPDOT",
        87: "KEY_F11",
        88: "KEY_F12",
        97: "KEY_RIGHTCTRL",
        99: "KEY_SYSRQ",
        100: "KEY_RIGHTALT",
        102: "KEY_HOME",
        103: "KEY_UP",
        104: "KEY_PAGEUP",
        105: "KEY_LEFT",
        106: "KEY_RIGHT",
        107: "KEY_END",
        108: "KEY_DOWN",
        109: "KEY_PAGEDOWN",
        110: "KEY_INSERT",
        113: "KEY_MUTE",
        114: "KEY_VOLUMEDOWN",
        115: "KEY_VOLUMEUP",
        111: "KEY_DELETE",
        119: "KEY_PAUSE",
        125: "KEY_LEFTMETA",
        126: "KEY_RIGHTMETA",
        127: "KEY_COMPOSE",
        186: "KEY_F16",
        187: "KEY_F17",
        272: "BTN_LEFT",
        273: "BTN_RIGHT",
        274: "BTN_MIDDLE",
        275: "BTN_SIDE",
        276: "BTN_EXTRA",
    },
}

event_t = tuple[int, int, int, int, int]


class InputEventGenerator:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        self._buffer: deque[event_t] = deque()
        self._waiter: asyncio.Future | None = None  # type:ignore[type-arg]
        self._closed = False

    def _on_readable(self) -> None:
        try:
            data = os.read(self.fd, EVENT_SIZE * 64)  # batch read
        except BlockingIOError:
            return

        if not data:
            self._closed = True
            if self._waiter and not self._waiter.done():
                self._waiter.set_result(None)
            return

        # unpack all events in one go
        for i in range(0, len(data), EVENT_SIZE):
            chunk = data[i : i + EVENT_SIZE]
            if len(chunk) < EVENT_SIZE:
                continue
            evt = struct.unpack(INPUT_EVENT_FORMAT, chunk)
            self._buffer.append(evt)

        if self._waiter and not self._waiter.done():
            self._waiter.set_result(True)

    async def __aiter__(self) -> AsyncGenerator[event_t]:
        loop = asyncio.get_running_loop()
        loop.add_reader(self.fd, self._on_readable)

        try:
            while True:
                # if we have buffered events, yield immediately
                if self._buffer:
                    yield self._buffer.popleft()
                    continue

                if self._closed:
                    break

                self._waiter = loop.create_future()
                await self._waiter
                self._waiter = None

        finally:
            loop.remove_reader(self.fd)
            os.close(self.fd)
