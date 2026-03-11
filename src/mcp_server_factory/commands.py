"""CLI — Entry point for the MCP Server Factory."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from mcp_server_framework import load_config, create_server, run_server, start_health_server
from mcp_server_framework.plugins.loader import add_plugin_dir
from mcp_server_framework.plugins.tracker import set_log_callback
from .factory import Factory

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="mcp-factory", description="MCP Server Factory — loads tool modules as plugins.")
    parser.add_argument("--plugins", "-p", nargs="+", default=[], help="Plugin names to load")
    parser.add_argument("--config", "-c", type=Path, default=None, help="YAML config file")
    parser.add_argument("--http", type=int, metavar="PORT", help="HTTP transport on given port")
    parser.add_argument("--health-port", type=int, metavar="PORT", help="Health endpoint port")
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
        config["server_name"] = "MCP Factory"

    logging.basicConfig(
        level=getattr(logging, config.get("log_level", "INFO")),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    plugin_names = args.plugins or config.get("plugins_load", [])
    plugins_config = config.get("plugins", {})
    if not plugin_names and isinstance(plugins_config, dict):
        plugin_names = [n for n, c in plugins_config.items() if isinstance(c, dict) and c.get("enabled", True)]
    if not plugin_names:
        print("Error: No plugins specified (use --plugins or config)")
        sys.exit(1)

    # Set up plugin infrastructure
    add_plugin_dir(Path(__file__).parent.parent.parent / "plugins")
    from .plugins.logging import log_settings
    set_log_callback(log_settings.log_call)

    mcp = create_server(config)
    factory = Factory(mcp, config)
    config["_factory"] = factory
    factory.load_internals()
    loaded = factory.load_externals(plugin_names)
    if not loaded:
        logger.error("No plugins loaded successfully — aborting")
        sys.exit(1)
    logger.info("%d plugin(s) loaded: %s", len(loaded), ", ".join(loaded))

    if config.get("transport") != "stdio":
        start_health_server(port=config["health_port"], title=f"{config['server_name']} Health")

    run_server(mcp, config)


if __name__ == "__main__":
    main()
