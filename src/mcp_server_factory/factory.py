"""Factory — Core orchestrator for plugin loading and management.

Uses PluginRegistry from framework for tracking and collision detection.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp_server_framework.plugins import PluginRegistry, load_module

logger = logging.getLogger(__name__)


class Factory:
    """Plugin-based MCP server factory.

    Thin orchestration layer around PluginRegistry.
    Loads plugins at startup — no runtime management.
    """

    def __init__(self, mcp: FastMCP, config: dict[str, Any]):
        self.mcp = mcp
        self.config = config
        self.registry = PluginRegistry(mcp, config)

    # Backwards-compatible properties
    @property
    def plugins(self):
        return self.registry.plugins

    def load_internals(self) -> None:
        """Load internal factory plugins (management, logging)."""
        from .plugins import management, logging as factory_logging
        internal_config = {"_factory": self}
        self.registry.load_plugin("factory_management", module=management,
                                  plugin_config=internal_config, internal=True)
        self.registry.load_plugin("factory_logging", module=factory_logging,
                                  plugin_config=internal_config, internal=True)

    def load_externals(self, plugin_names: list[str]) -> list[str]:
        """Load external plugins by name. Returns list of successfully loaded names."""
        loaded = []
        for name in plugin_names:
            result = self.registry.load_plugin(name)
            if result.ok:
                loaded.append(name)
            else:
                logger.error("%s", result.error)
        return loaded

    def get_plugin_summary(self) -> dict[str, Any]:
        """Return summary of all loaded plugins."""
        return self.registry.get_summary()
