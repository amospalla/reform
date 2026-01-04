# mleds

Keyboard led utilities for MNT Pocket Reform computer.

This utility is meant to be as a tool for easily generate, enqueue, play and manipulate
small movies/frames on the keyboard leds, either as background loops, or informative
data.

![gif1](https://file.amospalla.es/misc/mleds_sample1.gif)
![gif2](https://file.amospalla.es/misc/mleds_sample2.gif)
![gif3](https://file.amospalla.es/misc/mleds_sample3.gif)

## Run the program in oneshot mode

The program is tailored to run in daemon mode and be controlled with the client, still
there is a oneshot mode that allows to easily run it. Examples of running oneshot mode:

Oneshot mode with a menu interface (requires fzf to be available). Use cursors, enter
and escape keys to navigate the menu and activate items:

```sh
wget -O mleds https://github.com/amospalla/reform/raw/refs/heads/main/mleds/mleds
chmod 0755 mleds
sudo ./mleds oneshot-menu
```

Oneshot mode with keypresses and battery clients and matrix rain movie on background
(try using the keyboard with this one):

```sh
wget -O mleds https://github.com/amospalla/reform/raw/refs/heads/main/mleds/mleds
chmod 0755 mleds
sudo ./mleds oneshot "action=play_movie name=startup1 priority=urgent end=true action=play_movie name=matrix priority=background end=true action=run_client name=keypresses end=true action=run_client name=battery end=true"
```

Same oneshot as above, but with lowered brightness:

```sh
sudo ./mleds oneshot "action=set_intensity intensity=0.3 end=true action=play_movie name=startup1 priority=urgent end=true action=play_movie name=matrix priority=background end=true action=run_client name=keypresses end=true action=run_client name=battery end=true"
```

Play some demos:

```sh
sudo ./mleds oneshot "action=play_movie name=background1 priority=background end=true"
sudo ./mleds oneshot "action=play_movie name=background2 priority=background end=true"
sudo ./mleds oneshot "action=play_movie name=background3 priority=background end=true"
```

List available movies on oneshot mode:

```sh
./mleds oneshot "action=status end=true"
```

## Concepts

### Server

The server has three movie queues:

- background: it has one movie.
- foreground: it has one or no movie.
- urgent: it may have an unlimited number of movies.

The movie on the _background_ queue plays in loop, except if there are movies on the
_foreground_ or _urgent_ queues, in this situation the movie on _background_ queue
pauses until _foreground_ and _urgent_ queues end playing.

The movie on the _foreground_ queue plays once and then it is removed from the queue.
Playing a movie on the _urgent_ queue also clears the _foreground_ queue.

Movies in _urgent_ queue are played serially one after another, in the order these have
been enqueued and finally are removed.

A unix socket file is created where commands can be sent. This allows modifying the
server behaviour like add, start or stop playing movies, start or stop embedded clients

This program has two embedded clients, keypresses and battery. These behave like an
scripted external client would do, creating frames on the go and playing them, except
that bypasses the need to open the socket file.

### Movie

Each key is understood as a pixel, that can be shown with a color.

A movie is a series of frames, where each frame is defined by its duration (the time it
will be kept on the keyboard leds) and the colour that each key on the keyboard will
have set.

## Commands

- add_movie: create a new named movie. A movie can be created from scratch defining its
  frames in a text file, either as boolean values (set or not set) plus a frame color,
  or by specifying each key color. A movie can be the combination of another existing
  movies and/or newly created list of frames. Things like frame duration times, colors,
  intensity or repetitions can be set.
- play_movie: puts a given movie on one of the three queues.
- set_intensity: global server modifier that affects brightness.
- list_movies: show all the loaded movies on the server.
- list_scripts: show all available scripts on the server.
- run_script: run a named script.
- run_client: run a named client.
- stop_movies: remove movies from a queue.
- status: show server running status.

Commands are read by:

- `mleds server` at startup time: will read every file under /etc/mleds/load.d and
  ~/.config/mleds/load.d.
- `mleds client`: will send every command to the server.
- `mleds oneshot`: will read and execute all the commands specified, and exit upon completion.

Scripts are files that contain a series of commands, but instead of being read on server
initialization, these are available for being executed manually. Server reads scripts
files from /etc/mleds/scripts.d and ~/.config/mleds/scripts.d folders.

There are examples and documentation for the commands on the _sample_ folder, as a
couple of example script clients.

## Program arguments

- `mleds server`: starts the server, opens the socket file and loads files under _load.d_ folders.
- `mleds client`: sends commands to the server. Examples:
  - `mleds client "action=play_movie name=my_movie end=true"`.
  - `cat files_with_commands* | mleds client -` (note the ending dash).
- `mleds oneshot`: runs the specified commands and exit, without the need to spawn a
  server previously. Has the same interface as the _client_ command, it accepts a literal
  string or reading from stdin. Does not read _load.d_ neither _scripts.d_ folders.
- `mleds oneshot-menu`: runs in oneshot mode with a user interface.
- `mleds menu`: opens a menu which operates in client mode.
- `mleds status`: show server running status.
- `mleds play_movie`: play a movie.
- `mleds stop_movie`: remove all the movies on a queue.
- `mleds run_client|stop_client`: start or stop a client. Available clients:
  - _keypresses_
  - _battery_
  - _kanata_
- `mleds run_script`: run a script available on the server.
- `mleds set_intensity`: set the leds brightness.

## Install

Client does not need to run under the same user as the server. Only thing to take into
consideration is that the server needs write permissions to the hidraw device, and that
the _keypresses_ client needs to be run under an user with read permissions to the
keyboard device. Also, when server and client are not running within the same user, it
may be needed to adjust socket_path, socket_user, socket_group and or socket_perms in
configuration file for client and server.

```bash
# As root.
cp mleds /usr/local/bin/mleds && chmod 0755 /usr/local/bin/mleds
mkdir /etc/mleds
cp -a etc/* /etc/
# suggested configuration, set socket_user to your main user, so it can manage the server.
mkdir -p /usr/local/lib/systemd/system
cp mleds.service /usr/local/lib/systemd/system
systemctl enable mleds.service
systemctl start mleds.service

# As user.
cp mleds "${HOME}/bin" && chmod u+x "${HOME}/bin/mleds"
mkdir "${HOME}/.config/mleds"
cp -a etc/* "${HOME}/.config/mleds"
```

## Available embedded clients

There are 3 embedded clients on the program:

- battery: shows the battery status at given intervals.
- kanata: sets the colour leds for each kanata layer.
- keypresses: gives feedback for the keys being pressed.

## Menu

Both `menu` and `oneshot-menu` commands show a menu to the user.

There are two available interfaces, rofi or fzf. `menu` command will try to run rofi if
posible, else it will try with fzf. With rofi it is recommended to have a monospaced
font, else it is suggested to force fzf mode by running `INTERFACE=fzf mleds menu`.

`oneshot-menu` will always run using fzf.

## FAQ

**How do I load the samples on the _sample_ folder?**

All files on load.d, script.d and sample folders are exactly the same, list of commands.

What is the difference? No difference, just that the files on load.d are loaded by the
server at startup, the files on script.d are only loaded when the user calls
_run_script_.

Being all of them the same, you can load any of these files with

`cat <file> | mleds client -`

or a bunch of them with

`cat <file1> <file2> | mleds client -`

they are just a bunch of commands, one after the other inside the files.

The server has embedded a list of movies. A hardcoded one is the _blank_ movie
which consists of a blank frame with infinite timeout. It can be used for stopping the
current background movie, or for creating new movies. Moreover a list of text files are
embedded and loaded by the server, and are mostly useful if you are not copying the
sample files to your configuration folder, for example, when using the program in
oneshot mode.

**Why this format? Why can'it I throw code at it?**

I want it to be simple text file easily readable and writable, no coding at all. But
any suggestion is welcomed.

The most advanced primitive you will find is the `rectangle` one, available on the
_add_movie_ command.

**How does the keypresses client know what keys are being pressed?**

The keypresses client reads the device under /dev/input directly.

For its purposes it only mantains, at any given time, a list of keys that are currently
pressed, but it does not have memory for the previous states.
