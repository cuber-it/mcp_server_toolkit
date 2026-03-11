"""CLI — Entry point for the MCP Server Proxy."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from mcp_server_framework import load_config, create_server, run_server, start_health_server
from mcp_server_framework.plugins.loader import add_plugin_dir
from .proxy import PluginManager

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mcp-proxy",
        description="MCP Server Proxy — dynamic plugin loading at runtime.",
    )
    parser.add_argument(
        "--autoload", "-a", nargs="+", default=[],
        help="Plugins to load at startup",
    )
    parser.add_argument("--config", "-c", type=Path, default=None, help="YAML config file")
    parser.add_argument("--http", type=int, metavar="PORT", help="HTTP transport on given port")
    parser.add_argument("--health-port", type=int, metavar="PORT", help="Health endpoint port")
    parser.add_argument(
        "--plugin-dir", "-d", type=Path, action="append", default=[],
        help="Additional plugin search directory (can be repeated)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)

    if args.http:
        config["transport"] = "http"
        config["port"] = args.http
    if args.health_port:
        config["health_port"] = args.health_port
    if config.get("server_name") == "MCP Server":
        config["server_name"] = "MCP Proxy"

    logging.basicConfig(
        level=getattr(logging, config.get("log_level", "INFO")),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    # Register plugin search directories
    for plugin_dir in args.plugin_dir:
        add_plugin_dir(plugin_dir.resolve())

    # Create server and plugin manager
    mcp = create_server(config)
    proxy = PluginManager(mcp, config)

    # Load management tools
    from .plugins import management
    management.register(mcp, {"_proxy": proxy})

    # Autoload plugins from CLI or config
    autoload = args.autoload or config.get("autoload", [])
    for name in autoload:
        result = proxy.load(name)
        if not result.ok:
            logger.error("Autoload '%s' failed: %s", name, result.error)

    loaded_count = len(proxy.plugins)
    logger.info("Proxy ready: %d plugin(s), %d tools", loaded_count, len(proxy._all_tools))

    # Start health server if not stdio
    if config.get("transport") != "stdio":
        start_health_server(
            port=config["health_port"],
            title=f"{config['server_name']} Health",
        )

    run_server(mcp, config)


if __name__ == "__main__":
    main()
