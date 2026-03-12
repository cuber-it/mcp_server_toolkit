"""Local serve logic — start the proxy server."""

from __future__ import annotations

import argparse
import logging
import signal
import sys

from mcp_server_framework import create_server, load_config, run_server, setup_logging, start_health_server
from mcp_server_framework.plugins.loader import add_plugin_dir
from mcp_server_framework.plugins.tracker import set_log_callback

from .cli import DEFAULT_MGMT_PORT
from .client import is_proxy_running
from .proxy import PluginManager

logger = logging.getLogger(__name__)


def cmd_serve(args: argparse.Namespace) -> None:
    """Start the proxy server."""
    mgmt_port = getattr(args, "mgmt_port", DEFAULT_MGMT_PORT)
    if is_proxy_running(mgmt_port):
        print(f"Proxy already running on management port {mgmt_port}.", file=sys.stderr)
        print("Use 'mcp-proxy status' to check, or choose a different --mgmt-port.", file=sys.stderr)
        sys.exit(1)

    config = _build_config(args)

    setup_logging(
        level=config.get("log_level", "INFO"),
        json_format=config.get("log_format") == "json",
    )

    for plugin_dir in getattr(args, "plugin_dir", []):
        add_plugin_dir(plugin_dir.resolve())

    # Persistent tool call logging
    from .tool_log import ToolLog
    tool_log = ToolLog()
    set_log_callback(tool_log.log_call)
    logger.info("Tool call log: %s", tool_log.path)

    mcp = create_server(config)
    proxy = PluginManager(mcp, config)

    # Management MCP tools
    from .plugins import management
    management.register(mcp, {"_proxy": proxy})

    # Autoload
    autoload = getattr(args, "autoload", []) or config.get("autoload", [])
    for name in autoload:
        result = proxy.load(name)
        if not result.ok:
            logger.error("Autoload '%s' failed: %s", name, result.error)

    proxy.mark_startup_done()
    logger.info("Proxy ready: %d plugin(s), %d tools", len(proxy.plugins), len(proxy._all_tools))

    # Management API (always on localhost)
    from .management import start_management_server
    start_management_server(proxy, port=config["management_port"], token=config.get("management_token"))

    # Health server (HTTP only)
    if config.get("transport") != "stdio":
        _start_health(config, proxy, autoload)

    # Graceful shutdown
    def _shutdown(sig, _frame):
        logger.info("Received %s, shutting down...", signal.Signals(sig).name)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    run_server(mcp, config)


def _build_config(args: argparse.Namespace) -> dict:
    """Merge CLI args into loaded config."""
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

    cli_token = getattr(args, "mgmt_token", None)
    if cli_token:
        config["management_token"] = cli_token

    return config


def _start_health(config: dict, proxy: PluginManager, autoload: list) -> None:
    """Start health server with plugin readiness check."""
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
