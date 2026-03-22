"""mcp_server_framework — Shared framework for MCP servers.

Provides transport, health monitoring, configuration and plugin infrastructure.
Imported as a library — by standalone MCP servers, the Factory and the Proxy.

Public API:
    load_config(path)              → Config from YAML + ENV
    create_server(config)          → FastMCP instance
    run_server(mcp, config)        → Start server (stdio or HTTP)
    start_health_server(port, ...) → Start health thread
    create_health_app(...)         → Create health app directly

Plugin API (via mcp_server_framework.plugins):
    LoadedPlugin                   → Plugin record dataclass
    load_module(name, config)      → Resolve and import plugin
    find_register(module)          → Find register() function
    ToolTracker(mcp)               → Proxy that tracks tool registrations

Gate API (via mcp_server_framework.gate):
    Gate                           → Session-based TOTP gate
    GateLocked                     → Exception raised for locked tools
    SecretBackend                  → Pluggable secret backend (env/file/vaultwarden)
"""

__version__ = "1.5.0"

from .config import load_config
from .server import create_server, run_server
from .health import start_health_server, create_health_app
from .logging import setup_logging
from .oauth import IntrospectionTokenVerifier

__all__ = [
    "load_config",
    "create_server",
    "run_server",
    "start_health_server",
    "create_health_app",
    "setup_logging",
    "IntrospectionTokenVerifier",
]
