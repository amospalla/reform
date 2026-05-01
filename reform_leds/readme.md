# reform-leds

The script is known to work with:

- MNT Pocket Reform/keyboard leds: using XRGB HID command.

Should work (not tested) on:

- MNT Reform Keyboard 4.0/OLED display: using WBIO HID command.

Output of the command main help:

```text
$ reform-leds -h
usage: reform-leds [-h] [-V] [-l {critical,error,warning,info,debug}] {fill,draw,bitmap,text} ...

Set keyboard-leds/oled on a MNT Pocket Reform computer.  Version 0.0.1.

options:
  -h, --help            show this help message and exit
  -V, --version         show program's version number and exit
  -l, --log-level {critical,error,warning,info,debug}

Available commands:
  {fill,draw,bitmap,text}
    fill                fill with a color
    draw                put an image from a text file
    bitmap              put an image from a binary bitmap file
    text                put text from a file
    hidraw              list known devices

Examples:
   reform-leds fill keyboard --color purple
   reform-leds draw keyboard text-image.txt
   magick -size 128x32 pattern:crosshatch -depth 1 gray:- | reform-leds bitmap oled 1bit -
   magick -size  12x6  pattern:crosshatch -depth 8  rgb:- | reform-leds bitmap keyboard rgb -
   echo -e "bat1 " | reform-leds text oled -

Specific command help:
   reform-leds bitmap --help
   reform-leds draw --help
   reform-leds fill --help
   reform-leds text --help

Some commands and file format accept colors.
Colors can be specified in any of these formats: "green", "#00FF00" or "0,255,0".

List of known name colors: red, green, blue, black, white, orange, pink, violet, yellow, purple.
```

Examples:

```bash
$ echo -e "battery:\n 󰁾" | reform-leds text oled --font-size 10x14 -
```

![img1](https://file.amospalla.es/misc/reform_leds_text.jpg)

```bash
$ reform-leds text oled /etc/resolv.conf
```

![img2](https://file.amospalla.es/misc/reform_leds_text-file.jpg)

```bash
$ echo "
  ....O..O....
  ...O.OO.O...
  ...O....O...
  ....O..O....
  .....OO.....
  ............" | reform-leds draw keyboard --color "#ff00ff" -
```

![img3](https://file.amospalla.es/misc/reform_leds_keyboard.jpg)
