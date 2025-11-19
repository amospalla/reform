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

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from mleds.communications import (
    messages_client,
    messages_server,
)
from mleds.configuration import Configuration, get_configuration
from mleds.constants import PROGRAM_NAME, PROGRAM_VERSION
from mleds.exceptions import InvalidConfigurationError
from mleds.server import Server
from mleds.shared import shared

logger = logging.getLogger(__name__)


def set_logging_level(verbose: int) -> None:
    if verbose == 1:
        logging.basicConfig(level=logging.INFO)
    elif verbose > 1:
        logging.basicConfig(level=logging.DEBUG)


def parse_args() -> argparse.Namespace:
    """Return main program parsed arguments."""
    description = (
        "Daemon for MNT Pocket Reform keyboard leds manipulation. "
        f"Version {PROGRAM_VERSION}."
    )
    server_command_help = "Run main server which listens on a Unix Domain Socket."
    client_command_help = (
        "Send raw commands to the server. Use a single dash '-' to read from stdin."
    )
    oneshot_command_help = (
        "Run raw commands directly without a running server. "
        "Use single dash '-' to read from stdin."
    )
    status_command_help = "Show current server status."
    run_client_command_help = "Start an embedded client."
    stop_client_command_help = "Stop an embedded client."
    run_script_command_help = "Run a named script on the server."
    set_intensity_command_help = (
        "Sets the server brightness intensity, affects everything playing. "
        "Format: [+-]<float>."
    )
    show_path_command_help = "List paths for used files by the server."
    play_movie_command_help = "Run the specified movie on the specified queue."

    parser = argparse.ArgumentParser(prog=PROGRAM_NAME, description=description)
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("-s", "--socket-path", type=Path)
    parser.add_argument("-c", "--config-file", type=Path)
    parser.add_argument("-k", "--keyboard-device", required=False, type=Path)
    parser.add_argument("-d", "--hidraw-device", required=False, type=Path)
    subparser = parser.add_subparsers(dest="mode", required=True)

    _parser_server = subparser.add_parser("server", help=server_command_help)
    parser_client = subparser.add_parser("client", help=client_command_help)
    parser_client.add_argument("message")
    parser_oneshot = subparser.add_parser("oneshot", help=oneshot_command_help)
    parser_oneshot.add_argument("message")
    _parser_status = subparser.add_parser(
        "status",
        help=status_command_help,
    )

    parser_play_movie = subparser.add_parser(
        "play_movie",
        help=play_movie_command_help,
    )
    parser_play_movie.add_argument("movie_name")
    parser_play_movie.add_argument("priority")
    parser_run_client = subparser.add_parser(
        "run_client",
        help=run_client_command_help,
    )
    parser_run_client.add_argument("name")
    parser_stop_client = subparser.add_parser(
        "stop_client",
        help=stop_client_command_help,
    )
    parser_stop_client.add_argument("name")
    parser_run_script = subparser.add_parser("run_script", help=run_script_command_help)
    parser_run_script.add_argument("script_name")
    parser_set_intensity = subparser.add_parser(
        "set_intensity",
        help=set_intensity_command_help,
    )
    parser_set_intensity.add_argument("intensity_value")
    parser_show_path = subparser.add_parser(
        "path",
        help=show_path_command_help,
    )
    parser_show_path.add_argument("name", choices=("hidraw", "keyboard", "socket"))
    return parser.parse_args()


def check_path_exists(path: Path) -> None:
    if not path.exists():
        print(f"Error: path does not exist {path!s}. Is server runing?")
        sys.exit(1)


def check_path_writable(path: Path) -> None:
    resolved_path = path.resolve()

    if not os.access(resolved_path, os.W_OK):
        print(f"Error: path is not writable {resolved_path!s}.")
        sys.exit(1)


def main() -> None:  # noqa: C901, PLR0912
    """Main program."""
    args = parse_args()
    set_logging_level(args.verbose)
    logger.info("User supplied arguments: %s.", args)

    configuration = get_configuration(
        config_file=args.config_file,
        keyboard_device=args.keyboard_device,
        hidraw_device=args.hidraw_device,
        socket_path=args.socket_path,
    )
    if args.mode == "server":
        check_path_exists(configuration.hidraw_device)
        check_path_writable(configuration.hidraw_device)
        asyncio.run(server_event_loop(configuration))
    elif args.mode == "oneshot":
        if args.message == "-":
            asyncio.run(
                oneshot_event_loop(
                    configuration=configuration,
                    message=sys.stdin.read(),
                ),
            )
        else:
            asyncio.run(
                oneshot_event_loop(
                    configuration=configuration,
                    message=args.message,
                ),
            )
    elif args.mode == "client":
        check_path_exists(configuration.socket_path)
        check_path_writable(configuration.socket_path)
        if args.message == "-":
            asyncio.run(
                messages_client(
                    message=sys.stdin.read(),
                    socket_path=configuration.socket_path,
                ),
            )
        else:
            asyncio.run(
                messages_client(
                    message=args.message,
                    socket_path=configuration.socket_path,
                ),
            )
    elif args.mode == "status":
        asyncio.run(
            messages_client(
                message="action=status end=true",
                socket_path=configuration.socket_path,
            ),
        )
    elif args.mode == "run_client":
        asyncio.run(
            messages_client(
                message=f"action=run_client name={args.name} end=true",
                socket_path=configuration.socket_path,
            ),
        )
    elif args.mode == "stop_client":
        asyncio.run(
            messages_client(
                message=f"action=stop_client name={args.name} end=true",
                socket_path=configuration.socket_path,
            ),
        )
    elif args.mode == "run_script":
        check_path_exists(configuration.socket_path)
        asyncio.run(
            messages_client(
                message=f"action=run_script name={args.script_name} end=true",
                socket_path=configuration.socket_path,
            ),
        )
    elif args.mode == "set_intensity":
        check_path_exists(configuration.socket_path)
        asyncio.run(
            messages_client(
                message=f"action=set_intensity value={args.intensity_value} end=true",
                socket_path=configuration.socket_path,
            ),
        )
    elif args.mode == "play_movie":
        check_path_exists(configuration.socket_path)
        asyncio.run(
            messages_client(
                message=(
                    f"action=play_movie name={args.movie_name} "
                    f"priority={args.priority} end=true"
                ),
                socket_path=configuration.socket_path,
            ),
        )
    elif args.mode == "path":
        if args.name == "hidraw":
            print(configuration.hidraw_device)
        if args.name == "keyboard":
            print(configuration.keyboard_device)
        if args.name == "socket":
            print(configuration.socket_path)


async def oneshot(message: str) -> None:
    """Ad-hoc client to send messages to a oneshot server."""
    logger.info("Start oneshot execution.")
    lines = message.splitlines()
    response_lines: list[str] = []
    try:
        messages_buffer = shared["server_instance"].get_messages_reader()
        for line in lines:
            receive_response_lines, _disconnected = await messages_buffer.add(line)
            response_lines.extend(receive_response_lines)
    except InvalidConfigurationError as e:
        logger.error(repr(e))  # noqa: TRY400
        response_lines.append(str(e))
        for line in response_lines:
            print(line)
        sys.exit(1)
    except Exception as e:
        logger.exception("Error while processing client message")
        response_lines.append(str(e))
        for line in response_lines:
            print(line)
        sys.exit(1)

    for line in response_lines:
        print(line)


async def server_event_loop(configuration: Configuration) -> None:
    """Start server event loop."""
    if configuration.socket_path.exists():
        configuration.socket_path.unlink()

    shared["server_instance"] = Server(configuration=configuration, oneshot=False)
    task_messages_server = await asyncio.start_unix_server(
        messages_server,
        configuration.socket_path,
    )
    if configuration.socket_user > -1 or configuration.socket_group > -1:
        os.chown(
            path=configuration.socket_path,
            uid=configuration.socket_user,
            gid=configuration.socket_group,
        )

    configuration.socket_path.chmod(configuration.socket_mode)
    await asyncio.gather(
        # task_server_writer,
        shared["server_instance"].writer(),
        shared["server_instance"].async_init(
            include_loads=True,
            include_resources=True,
        ),
        task_messages_server.serve_forever(),
    )


async def oneshot_event_loop(configuration: Configuration, message: str) -> None:
    """Run a server with user supplied configuration and exit."""
    shared["server_instance"] = Server(configuration=configuration, oneshot=True)
    await asyncio.gather(
        asyncio.sleep(1),
        shared["server_instance"].writer(),
        shared["server_instance"].async_init(
            include_loads=False,
            include_resources=True,
        ),
        oneshot(message),
    )


if __name__ == "__main__":
    main()
