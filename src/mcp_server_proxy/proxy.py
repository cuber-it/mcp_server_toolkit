"""Proxy — Dynamic plugin manager with runtime load/unload.

Uses PluginRegistry from framework for tracking and collision detection.
Adds dynamic load/unload/reload and management command extensions.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Callable

from mcp.server.fastmcp import FastMCP

from mcp_server_framework.plugins import (
    PluginRegistry, LoadResult, UnloadResult, load_plugin_config,
)

logger = logging.getLogger(__name__)


class PluginManager:
    """Dynamic plugin management — load, unload and reload at runtime.

    Thin orchestration layer around PluginRegistry with:
    - Dynamic load/unload/reload
    - Startup vs runtime tracking
    - Management command extensions via register_command()
    """

    def __init__(self, mcp: FastMCP, config: dict[str, Any]):
        self.mcp = mcp
        self.config = config
        self.registry = PluginRegistry(mcp, config)
        self._commands: dict[str, Callable] = {}
        self._startup_complete: bool = False
        self._startup_tools: set[str] = set()

    # Backwards-compatible properties
    @property
    def plugins(self):
        return self.registry.plugins

    @property
    def _all_tools(self):
        return self.registry._all_tools

    def mark_startup_done(self) -> None:
        """Mark the autoload phase as complete. Tools loaded after this are dynamic."""
        self._startup_tools = set(self.registry.all_tools)
        self._startup_complete = True
        logger.info("Startup complete: %d tools marked as static", len(self._startup_tools))

    @property
    def dynamic_tools(self) -> list[str]:
        """Tools loaded after startup (available via proxy__run)."""
        return sorted(self.registry.all_tools - self._startup_tools)

    @property
    def dynamic_dispatch_enabled(self) -> bool:
        return self.config.get("dynamic_dispatch", False)

    def register_command(self, name: str, handler: Callable) -> None:
        """Register a management command extension."""
        self._commands[name] = handler
        logger.info("Management command registered: %s", name)

    def run_command(self, name: str, **kwargs) -> str:
        """Execute a registered management command."""
        handler = self._commands.get(name)
        if handler is None:
            return f"Unknown command: {name}"
        try:
            return handler(self, **kwargs)
        except Exception as e:
            return f"Command '{name}' failed: {e}"

    @property
    def commands(self) -> list[str]:
        return list(self._commands.keys())

    def load(self, name: str) -> LoadResult:
        """Load a plugin by name. Returns LoadResult with tools or error."""
        # Plugin config: plugin_dir/{name}/config.yaml, fallback to proxy config
        plugin_config = load_plugin_config(name)
        if not plugin_config:
            plugins_config = self.config.get("plugins", {})
            plugin_config = plugins_config.get(name, {})

        prefix = self._resolve_prefix(name, plugin_config if isinstance(plugin_config, dict) else {})

        result = self.registry.load_plugin(
            name,
            plugin_config=plugin_config if isinstance(plugin_config, dict) else {},
            prefix=prefix,
        )
        if result.ok and result.plugin:
            result.plugin.startup = not self._startup_complete
        return result

    def unload(self, name: str) -> UnloadResult:
        """Unload a plugin. Removes its tools from FastMCP."""
        return self.registry.unload_plugin(name)

    def reload(self, name: str) -> LoadResult:
        """Unload, reimport module, and load again."""
        if name not in self.plugins:
            return LoadResult(ok=False, error=f"Plugin '{name}' not loaded, use load()")

        old_module = self.plugins[name].module
        self.unload(name)

        try:
            importlib.reload(old_module)
        except Exception as e:
            logger.warning("Could not reload module for '%s': %s", name, e)

        return self.load(name)

    def list_plugins(self) -> dict[str, Any]:
        """Return summary of all loaded plugins."""
        return self.registry.get_summary()

    def _resolve_prefix(self, plugin_name: str, plugin_config: dict) -> str | None:
        """Determine the tool name prefix for a plugin."""
        if "prefix" in plugin_config:
            val = plugin_config["prefix"]
            if val is False or val == "":
                return None
            return str(val)
        auto_prefix = self.config.get("auto_prefix", False)
        if auto_prefix:
            return plugin_name
        return None
