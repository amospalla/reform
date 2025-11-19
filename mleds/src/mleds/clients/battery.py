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

import asyncio
import logging
from pathlib import Path

from mleds.clients.base import Client

logger = logging.getLogger(__name__)

triggers = {
    # (4, 5),
    # (95, 96),
    (66, 65),
    (33, 32),
    (16, 35),
    (6, 5),
    (33, 34),
    (50, 51),
    (70, 71),
    (84, 85),
}


class Battery(Client):
    def __init__(self, *args, **kwargs) -> None:  # type:ignore[no-untyped-def]
        self.percentage = 0  # self.get_data()
        self.charging = True
        super().__init__(*args, **kwargs)

    async def run(self) -> None:
        while True:
            await asyncio.sleep(0.1)
            new_percentage, self.charging = self.get_data()
            if (self.percentage, new_percentage) in triggers:
                await self.send_message(message=self.next_message())
            self.percentage = new_percentage

            await asyncio.sleep(1)

    def get_data(self) -> tuple[int, bool]:
        with Path("/sys/class/power_supply/BAT0/capacity").open("r") as f:
            percentage = int(f.read().strip())
        with Path("/sys/class/power_supply/BAT0/status").open("r") as f:
            charging = f.read().strip() == "Charging"
        return percentage, charging

    def next_message(self) -> list[str]:
        if self.charging:
            charging_color = self.configuration.battery_charging_color
        else:
            charging_color = self.configuration.battery_discharging_color
        times = 0.4
        return [
            f"action=add_movie name=battery0 copy_movie=blank times={times}",
            f"rectangle= 0 0 10 5 {self.configuration.battery_border_color}",
            f"{self.configuration.battery_border_color} right false 100",
            f"rectangle=10 1  2 3 {self.configuration.battery_border_color}",
            f"{self.configuration.battery_border_color} right false 100",
            "rectangle=  8 1  2 3 #000000 #000000 right false 100",
            f"rectangle= 1 1  9 3 {self.configuration.battery_charge_color_start}",
            f"{self.configuration.battery_charge_color_end}",
            f"right true {self.percentage}",
            f"rectangle= 0 5  1 1 {charging_color} {charging_color} right true 100",
            "end=true",
            # Same frame as before, with {percentage-11}
            f"action=add_movie name=battery1 copy_movie=blank times={times}",
            f"rectangle= 0 0 10 5 {self.configuration.battery_border_color}",
            f"{self.configuration.battery_border_color} right false 100",
            f"rectangle=10 1  2 3 {self.configuration.battery_border_color}",
            f"{self.configuration.battery_border_color} right false 100",
            "rectangle=  8 1  2 3 #000000 #000000 right false 100",
            f"rectangle= 1 1  9 3 {self.configuration.battery_charge_color_start}",
            f"{self.configuration.battery_charge_color_end} right true",
            f"{self.percentage - 11}",
            f"rectangle= 0 5  1 1 {charging_color} {charging_color} right true 100",
            "end=true",
            "action=play_movie name=battery0 priority=urgent",
            "end=true",
            "action=play_movie name=battery1 priority=urgent",
            "end=true",
            "action=play_movie name=battery0 priority=urgent",
            "end=true",
            "action=play_movie name=battery1 priority=urgent",
            "end=true",
            "action=play_movie name=battery0 priority=urgent",
            "end=true",
            "action=play_movie name=battery1 priority=urgent",
            "end=true",
            "action=play_movie name=battery0 priority=urgent",
            "end=true",
            "action=play_movie name=battery1 priority=urgent",
            "end=true",
            "action=play_movie name=battery0 priority=urgent",
            "end=true",
            "action=play_movie name=battery1 priority=urgent",
            "end=true",
        ]
