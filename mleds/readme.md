# mleds

Keyboard led utilities for MNT Pocket Reform computer.

## Concepts

The server has three movie queues:

- background: it has one or no movie. Enqueuing in _background_ replaces the previous one.
- foreground: it has one or no movie.Enqueuing in _foreground_ replaces the previous one.
- urgent: it may have an unlimited number of movies.

All movies put into _urgent_ queue are played serially one after another, in the order
these have been enqueued. Once a movie in this queue has ended it is removed.
When there are no more _urgent_ movies, then the _background_ movie is played, in loop.

A movie in _background_ (if any) plays in loop, forever. If _urgent_ or _foreground_
movies are enqueued, once they end, the _background_ movie will resume where it was left.

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
- run_script: run a named sript.

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
- `mleds keypresses`: client for the server that shows keyboard keypresses. By default
  it plays on _foreground_ queue.
- `mleds list_movies|play_movie|list_scripts|run_script|set_intensity` shortcuts to
  sending these commands with the `mleds client "action=<my_action> ... end=true"`.
- `mleds path hidraw|keyboard|socket`: show internal used paths used with the current
  configuration.

## Install

Client does not need to run under the same user as the server. Only thing to take into
consideration is that the server needs write permissions to the hidraw device, and that
the _keypresses_ client need to be run under an user with read permissions to the
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

To use the _keypresses_ client, install evtest `sudo apt install evtest`.

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

**Why this format? Why can'it I throw code at it?**

I want it to be simple text file easily readable and writable, no coding at all. But
any suggestion is welcomed.

The most advanced primitive you will find is the `rectangle` one, available on the
_add_movie_ command.

## TODO

- Client to notify about battery status.
- Keypresses client should be controlled with a command like _play_movie_, later when a
  play_movie is run with the same "foreground" or "background" priority, keypresses
  module should be stopped (scheduler). This solves two problems:
  - having to run _mleds keypresses_ as a separate long running command.
  - the need for the user running _mleds keypresses_ to have read access to the keyboard device (if the server is already running under root).
- Add the concept of "loop starting point" to a movie, and when movie is played in
  background priority (which always loops) restart the movie on this specified frame
  instead of the first one. This allows movies to have an grup of frames that start the
  movie, which won't play lately on the loop.
- More configurable options for keypresses colors and times.
- add to configuration the following keys:
  - "startup_movie_background"
  - "startup_movie_foreground"
  - "startup_movies_urgent"
