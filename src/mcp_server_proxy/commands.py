"""CLI entry point for mcp-proxy."""

from __future__ import annotations

from .cli import parse_args
from .client import send_command
from .serve import cmd_serve


def main() -> None:
    args = parse_args()
    command = args.command

    if command in ("load", "unload", "reload", "status"):
        send_command(command, args)
    else:
        cmd_serve(args)


if __name__ == "__main__":
    main()
