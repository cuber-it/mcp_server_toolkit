"""mcp_server_proxy — Dynamic MCP server with runtime plugin loading.

Loads and unloads tool modules at runtime without restart.
Uses the same register(mcp, config) interface as the Factory.
"""

__version__ = "0.1.0"

from .proxy import PluginManager

__all__ = ["PluginManager"]
