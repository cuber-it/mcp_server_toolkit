"""mcp_server_framework — Shared framework for MCP servers.

Provides transport, health monitoring and configuration.
Imported as a library — by standalone MCP servers and by the MCP Server Factory.

Public API:
    load_config(path)              → Config from YAML + ENV
    create_server(config)          → FastMCP instance
    run_server(mcp, config)        → Start server (stdio or HTTP)
    start_health_server(port, ...) → Start health thread
    create_health_app(...)         → Create health app directly
"""

__version__ = "0.3.0"

from .config import load_config
from .server import create_server, run_server
from .health import start_health_server, create_health_app

__all__ = [
    "load_config",
    "create_server",
    "run_server",
    "start_health_server",
    "create_health_app",
]
