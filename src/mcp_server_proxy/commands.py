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
        p.add_argument("--token", default=None, help="Management API Bearer token (or set MCP_MGMT_TOKEN)")

    # --- status ---
    st = sub.add_parser("status", help="Show proxy status")
    st.add_argument("--mgmt-port", type=int, default=DEFAULT_MGMT_PORT, help="Management API port")
    st.add_argument("--token", default=None, help="Management API Bearer token (or set MCP_MGMT_TOKEN)")

    # Allow serve args on top-level (no subcommand = serve)
    _add_serve_args(parser)

    return parser.parse_args()


def _add_serve_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--autoload", "-a", nargs="+", default=[], help="Plugins to load at startup")
    parser.add_argument("--config", "-c", type=Path, default=None, help="YAML config file")
    parser.add_argument("--http", type=int, metavar="PORT", help="HTTP transport on given port")
    parser.add_argument("--health-port", type=int, metavar="PORT", help="Health endpoint port")
    parser.add_argument("--mgmt-port", type=int, metavar="PORT", default=DEFAULT_MGMT_PORT, help="Management API port")
    parser.add_argument("--mgmt-token", default=None, help="Bearer token for management API (or set MCP_MGMT_TOKEN)")
    parser.add_argument(
        "--plugin-dir", "-d", type=Path, action="append", default=[],
        help="Additional plugin search directory (can be repeated)",
    )


def _mgmt_url(port: int, path: str) -> str:
    return f"http://127.0.0.1:{port}{path}"


def _cmd_remote(command: str, args: argparse.Namespace) -> None:
    """Send a command to the running proxy via management API."""
    import os
    port = args.mgmt_port
    token = getattr(args, "token", None) or os.environ.get("MCP_MGMT_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        if command == "status":
            resp = httpx.get(_mgmt_url(port, "/proxy/status"), headers=headers, timeout=5)
            if resp.status_code == 401:
                print("Error: unauthorized — provide --token or set MCP_MGMT_TOKEN", file=sys.stderr)
                sys.exit(1)
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
                headers=headers,
                timeout=10,
            )
            if resp.status_code == 401:
                print("Error: unauthorized — provide --token or set MCP_MGMT_TOKEN", file=sys.stderr)
                sys.exit(1)
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


def _is_proxy_running(port: int) -> bool:
    """Check if a proxy management API is already responding."""
    try:
        resp = httpx.get(_mgmt_url(port, "/proxy/status"), timeout=1)
        return resp.status_code == 200
    except Exception:
        return False


def _cmd_serve(args: argparse.Namespace) -> None:
    """Start the proxy server."""
    mgmt_port = getattr(args, "mgmt_port", DEFAULT_MGMT_PORT)
    if _is_proxy_running(mgmt_port):
        print(f"Proxy already running on management port {mgmt_port}.", file=sys.stderr)
        print("Use 'mcp-proxy status' to check, or choose a different --mgmt-port.", file=sys.stderr)
        sys.exit(1)

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

    # Management token: CLI --mgmt-token > config > env (env handled in management.py)
    cli_token = getattr(args, "mgmt_token", None)
    if cli_token:
        config["management_token"] = cli_token

    from mcp_server_framework import setup_logging
    setup_logging(
        level=config.get("log_level", "INFO"),
        json_format=config.get("log_format") == "json",
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
    mgmt_token = config.get("management_token")
    start_management_server(proxy, port=config["management_port"], token=mgmt_token)

    # Start health server if not stdio (with plugin status)
    if config.get("transport") != "stdio":
        def _readiness_check():
            if not proxy.plugins and autoload:
                raise RuntimeError(f"No plugins loaded (expected: {autoload})")

        def _registry_setup(app):
            @app.get("/health/plugins")
            async def health_plugins():
                return proxy.list_plugins()

        start_health_server(
            port=config["health_port"],
            title=f"{config['server_name']} Health",
            readiness_check=_readiness_check,
            registry_setup=_registry_setup,
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
