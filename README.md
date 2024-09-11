# Personal MNT Pocket Reform scripts

All the scripts use the file rmt-lib.sh, which must be placed in the same path where the scripts reside.

## Scripts

### psuspend

This program disables everything as posible on the computer trying to minimize the power consumption. It does not
stop it but your screen and keyboard will not respond to until you resume it again.

Install:

```sh
# Get files:
wget https://raw.githubusercontent.com/amospalla/reform/main/psuspend.conf -O /etc/psuspend.conf
wget https://raw.githubusercontent.com/amospalla/reform/main/rmt-lib.sh -O /usr/local/bin/rmt-lib.sh
wget https://raw.githubusercontent.com/amospalla/reform/main/psuspend -O /usr/local/bin/psuspend
wget https://raw.githubusercontent.com/amospalla/reform/main/systemd/psuspend.service -O /etc/systemd/system/psuspend.service
chmod 0644 /etc/psuspend.conf
chmod 0755 /usr/local/bin/rmt-lib.sh
chmod 0755 /usr/local/bin/psuspend
chmod 0644 /etc/systemd/system/psuspend.service

apt-get install evtest # Install dependencies
systemctl enable psuspend # Enable systemd unit
```

### battery-notify

Gives user feedback about battery status by using the keyboard leds.

Currently it notifies when:

- the computer is charging and the battery capacity transitions into 95%, 66% and 33% with green, blue and red colours.
- the computer is discharging and the battery capacity transitions into 33%, 16% and 4%, using red colour with a
  single slow transition, two faster transitions, or 4 even faster ones.

Install:

```sh
# Get files:
wget https://raw.githubusercontent.com/amospalla/reform/main/battery-notify -O /usr/local/bin/battery-notify
wget https://raw.githubusercontent.com/amospalla/reform/main/rmt-lib.sh -O /usr/local/bin/rmt-lib.sh
wget https://raw.githubusercontent.com/amospalla/reform/main/systemd/battery-notify.service -O /etc/systemd/system/battery-notify.service
chmod 0755 /usr/local/bin/battery-notify
chmod 0755 /usr/local/bin/rmt-lib.sh
chmod 0644 /etc/systemd/system/battery-notify.service

systemctl enable battery-notify # Enable systemd unit
```

### rmt (reform mini tools)

Install:

```sh
# Get files:
wget https://raw.githubusercontent.com/amospalla/reform/main/rmt -O /usr/local/bin/rmt
wget https://raw.githubusercontent.com/amospalla/reform/main/rmt-lib.sh -O /usr/local/bin/rmt-lib.sh
chmod 0755 /usr/local/bin/rmt
chmod 0755 /usr/local/bin/rmt-lib.sh
```

Command help:

```text
Usage:
    rmt leds set <red> <green> <blue>: set leds colours, range 0-255.

    rmt leds transition <r> <g> <b> <r> <g> <b> <steps> <wait-seconds>:
                show a colours transition, from rgb1 to rgb2 in given steps and wait time between two step.

    rmt wait keyboard: wait until /dev/input/by-id/* device is ready.

    rmt wait hidraw: wait until /dev/hidraw* device is ready.

    rmt -h|--help: show this help.

Examples:
    rmt leds set 255 0 0
    rmt leds transition  255 0 0  0 255 0  50 0.02
    rmt wait keyboard
    rmt wait hidraw
```
