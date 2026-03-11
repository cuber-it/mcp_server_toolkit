"""mcp_server_factory — Builds MCP servers from tool modules.

Everything is a plugin. External tools and internal management
commands use the same interface: register(mcp, config).
"""

__version__ = "0.9.0"

from .factory import Factory

__all__ = ["Factory"]
