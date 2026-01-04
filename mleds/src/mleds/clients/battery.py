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
from mleds.constants import Priority

MOVIE_NAME = "hidden_battery"
logger = logging.getLogger(__name__)


class Battery(Client):
    priority = Priority.urgent

    def __init__(self, *args, **kwargs) -> None:  # type:ignore[no-untyped-def]
        self.percentage = 0  # self.get_data()
        self.charging = True
        super().__init__(*args, **kwargs)

    async def run(self) -> None:
        self.percentage, self.charging = self.get_data()
        if self.charging:
            await self.send_message(message=self.next_message(1))
        else:
            await self.send_message(message=self.next_message(-1))

        while True:
            await asyncio.sleep(10)
            new_percentage, self.charging = self.get_data()
            if (
                self.percentage,
                new_percentage,
            ) in self.configuration.battery_notification_events:
                await self.send_message(
                    message=self.next_message(new_percentage - self.percentage),
                )
            self.percentage = new_percentage

    def get_data(self) -> tuple[int, bool]:
        with Path("/sys/class/power_supply/BAT0/capacity").open("r") as f:
            percentage = int(f.read().strip())
        with Path("/sys/class/power_supply/BAT0/status").open("r") as f:
            charging = f.read().strip() == "Charging"
        return percentage, charging

    def next_message(self, increment: int) -> list[str]:
        # if self.charging:
        #     charging_color = self.configuration.battery_charging_color
        # else:
        #     charging_color = self.configuration.battery_discharging_color
        times = 0.4
        if increment > 0:
            start_color = self.configuration.battery_increase_color_start
            end_color = self.configuration.battery_increase_color_end
        else:
            start_color = self.configuration.battery_decrease_color_start
            end_color = self.configuration.battery_decrease_color_end
        frame0 = [
            f"action=add_movie name={MOVIE_NAME}0 copy_movie=blank times={times}",
            f"rectangle= 0 0 10 5 {self.configuration.battery_border_color}",
            f"{self.configuration.battery_border_color} right false 100",
            f"rectangle=10 1  2 3 {self.configuration.battery_border_color}",
            f"{self.configuration.battery_border_color} right false 100",
            "rectangle=  8 1  2 3 #000000 #000000 right false 100",
            f"rectangle= 1 1  9 3 {start_color} {end_color}",
            f"right true {self.percentage}",
            # f"rectangle= 3 5  2 1 {charging_color} {charging_color} right true 100",
            # f"rectangle= 7 5  2 1 {charging_color} {charging_color} right true 100",
            "end=true",
        ]
        frame1 = [
            # Same frame as before, with {percentage-11}
            f"action=add_movie name={MOVIE_NAME}1 copy_movie=blank times={times}",
            f"rectangle= 0 0 10 5 {self.configuration.battery_border_color}",
            f"{self.configuration.battery_border_color} right false 100",
            f"rectangle=10 1  2 3 {self.configuration.battery_border_color}",
            f"{self.configuration.battery_border_color} right false 100",
            "rectangle=  8 1  2 3 #000000 #000000 right false 100",
            f"rectangle= 1 1  9 3 {start_color} {end_color} right true",
            f"{self.percentage - 11}",
            # f"rectangle= 3 5  2 1 {charging_color} {charging_color} right true 100",
            # f"rectangle= 7 5  2 1 {charging_color} {charging_color} right true 100",
            "end=true",
        ]
        create_movie = [
            f"action=add_movie name={MOVIE_NAME}",
            f"copy_movie={MOVIE_NAME}0 times=0.4",
            f"copy_movie={MOVIE_NAME}1 times=0.4",
            "end=true",
            f"action=add_movie name={MOVIE_NAME}",
            f"copy_movie={MOVIE_NAME} repetitions=5 end=true",
            f"action=play_movie name={MOVIE_NAME} priority={self.priority} end=true,",
        ]
        return [*frame0, *frame1, *create_movie]
