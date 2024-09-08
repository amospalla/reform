# Personal MNT Pocket Reform scripts

All the scripts use the file reform-libs.sh, which must be placed in the same path where the scripts reside.

## Scripts

### psuspend

This program disables everything as posible on the computer trying to minimize the power consumption. It does not
stop it but your screen and keyboard will not respond to until you resume it again.

Copy files into:

- /etc/psuspend.conf.
- /usr/local/bin/reform-libs.sh
- /usr/local/bin/psuspend
- /etc/systemd/system/psuspend.service

Install evtest: `apt-get install evtest`.

Enable the systemd service: `systemctl enable psuspend`.

### battery-notify

- Gives user feedback about battery status by using the keyboard leds.

### set_leds

- Set leds colours.
