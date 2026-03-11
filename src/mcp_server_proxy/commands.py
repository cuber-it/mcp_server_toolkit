"""CLI — Entry point for the MCP Server Proxy.

Supports two modes:
    mcp-proxy [serve] ...   Start the proxy server (default)
    mcp-proxy load <plugin> Send command to running proxy via management API
    mcp-proxy unload <plugin>
    mcp-proxy reload <plugin>
    mcp-proxy status        Show loaded plugins
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
from pathlib import Path

import httpx

from mcp_server_framework import load_config, create_server, run_server, start_health_server
from mcp_server_framework.plugins.loader import add_plugin_dir
from .proxy import PluginManager

logger = logging.getLogger(__name__)

DEFAULT_MGMT_PORT = 12299


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mcp-proxy",
        description="MCP Server Proxy — dynamic plugin loading at runtime.",
    )
    sub = parser.add_subparsers(dest="command")

    # --- serve (default) ---
    serve = sub.add_parser("serve", help="Start the proxy server")
    _add_serve_args(serve)

    # --- load / unload / reload ---
    for cmd in ("load", "unload", "reload"):
        p = sub.add_parser(cmd, help=f"{cmd.capitalize()} a plugin on running proxy")
        p.add_argument("plugin", help="Plugin name")
        p.add_argument("--mgmt-port", type=int, default=DEFAULT_MGMT_PORT, help="Management API port")

    # --- status ---
    st = sub.add_parser("status", help="Show proxy status")
    st.add_argument("--mgmt-port", type=int, default=DEFAULT_MGMT_PORT, help="Management API port")

    # Allow serve args on top-level (no subcommand = serve)
    _add_serve_args(parser)

    return parser.parse_args()


def _add_serve_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--autoload", "-a", nargs="+", default=[], help="Plugins to load at startup")
    parser.add_argument("--config", "-c", type=Path, default=None, help="YAML config file")
    parser.add_argument("--http", type=int, metavar="PORT", help="HTTP transport on given port")
    parser.add_argument("--health-port", type=int, metavar="PORT", help="Health endpoint port")
    parser.add_argument("--mgmt-port", type=int, metavar="PORT", default=DEFAULT_MGMT_PORT, help="Management API port")
    parser.add_argument(
        "--plugin-dir", "-d", type=Path, action="append", default=[],
        help="Additional plugin search directory (can be repeated)",
    )


def _mgmt_url(port: int, path: str) -> str:
    return f"http://127.0.0.1:{port}{path}"


def _cmd_remote(command: str, args: argparse.Namespace) -> None:
    """Send a command to the running proxy via management API."""
    port = args.mgmt_port
    try:
        if command == "status":
            resp = httpx.get(_mgmt_url(port, "/proxy/status"), timeout=5)
            data = resp.json()
            print(f"Plugins: {data['total_plugins']}, Tools: {data['total_tools']}")
            for name, info in data.get("plugins", {}).items():
                tools = ", ".join(info["tools"][:5])
                if info["tool_count"] > 5:
                    tools += f" (+{info['tool_count'] - 5} more)"
                print(f"  {name}: {tools}")
        else:
            resp = httpx.post(
                _mgmt_url(port, f"/proxy/{command}"),
                json={"plugin": args.plugin},
                timeout=10,
            )
            data = resp.json()
            if data.get("ok"):
                tools = data.get("tools") or data.get("removed") or []
                print(f"{command.capitalize()} '{args.plugin}': {', '.join(tools)}")
            else:
                print(f"Error: {data.get('error', 'unknown')}", file=sys.stderr)
                sys.exit(1)
    except httpx.ConnectError:
        print(f"Cannot connect to management API on port {port}. Is the proxy running?", file=sys.stderr)
        sys.exit(1)


def _cmd_serve(args: argparse.Namespace) -> None:
    """Start the proxy server."""
    config = load_config(getattr(args, "config", None))

    if getattr(args, "http", None):
        config["transport"] = "http"
        config["port"] = args.http
    if getattr(args, "health_port", None):
        config["health_port"] = args.health_port
    if config.get("server_name") == "MCP Server":
        config["server_name"] = "MCP Proxy"

    mgmt_port = getattr(args, "mgmt_port", DEFAULT_MGMT_PORT)
    config.setdefault("management_port", mgmt_port)

    logging.basicConfig(
        level=getattr(logging, config.get("log_level", "INFO")),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    # Register plugin search directories
    for plugin_dir in getattr(args, "plugin_dir", []):
        add_plugin_dir(plugin_dir.resolve())

    # Create server and plugin manager
    mcp = create_server(config)
    proxy = PluginManager(mcp, config)

    # Load management MCP tools
    from .plugins import management
    management.register(mcp, {"_proxy": proxy})

    # Autoload plugins from CLI or config
    autoload = getattr(args, "autoload", []) or config.get("autoload", [])
    for name in autoload:
        result = proxy.load(name)
        if not result.ok:
            logger.error("Autoload '%s' failed: %s", name, result.error)

    loaded_count = len(proxy.plugins)
    logger.info("Proxy ready: %d plugin(s), %d tools", loaded_count, len(proxy._all_tools))

    # Start management API (always, on 127.0.0.1 only)
    from .management import start_management_server
    start_management_server(proxy, port=config["management_port"])

    # Start health server if not stdio
    if config.get("transport") != "stdio":
        start_health_server(
            port=config["health_port"],
            title=f"{config['server_name']} Health",
        )

    # Graceful shutdown
    def _shutdown(sig, frame):
        logger.info("Received %s, shutting down...", signal.Signals(sig).name)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    run_server(mcp, config)


def main() -> None:
    args = parse_args()
    command = args.command

    if command in ("load", "unload", "reload", "status"):
        _cmd_remote(command, args)
    else:
        _cmd_serve(args)


if __name__ == "__main__":
    main()
