"""Argument parsing for mcp-proxy CLI."""

from __future__ import annotations

import argparse
from pathlib import Path

DEFAULT_MGMT_PORT = 12299


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for mcp-proxy."""
    parser = argparse.ArgumentParser(
        prog="mcp-proxy",
        description="MCP Server Proxy — dynamic plugin loading at runtime.",
    )
    sub = parser.add_subparsers(dest="command")

    # serve (default)
    serve = sub.add_parser("serve", help="Start the proxy server")
    _add_serve_args(serve)

    # load / unload / reload
    for cmd in ("load", "unload", "reload"):
        p = sub.add_parser(cmd, help=f"{cmd.capitalize()} a plugin on running proxy")
        p.add_argument("plugin", help="Plugin name")
        _add_remote_args(p)

    # status
    st = sub.add_parser("status", help="Show proxy status")
    _add_remote_args(st)

    # No subcommand = serve
    _add_serve_args(parser)

    return parser.parse_args()


def _add_serve_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--autoload", "-a", nargs="+", default=[], help="Plugins to load at startup")
    parser.add_argument("--config", "-c", type=Path, default=None, help="YAML config file")
    parser.add_argument("--http", type=int, metavar="PORT", help="HTTP transport on given port")
    parser.add_argument("--health-port", type=int, metavar="PORT", help="Health endpoint port")
    parser.add_argument("--mgmt-port", type=int, metavar="PORT", default=DEFAULT_MGMT_PORT, help="Management API port")
    parser.add_argument("--mgmt-token", default=None, help="Bearer token for management API")
    parser.add_argument(
        "--plugin-dir", "-d", type=Path, action="append", default=[],
        help="Additional plugin search directory (repeatable)",
    )


def _add_remote_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mgmt-port", type=int, default=DEFAULT_MGMT_PORT, help="Management API port")
    parser.add_argument("--token", default=None, help="Management API Bearer token")
