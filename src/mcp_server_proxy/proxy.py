"""Proxy — Dynamic plugin manager with runtime load/unload."""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from datetime import datetime
from types import ModuleType
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server_framework.plugins import LoadedPlugin, load_module, find_register, ToolTracker

logger = logging.getLogger(__name__)


@dataclass
class LoadResult:
    ok: bool
    tools: list[str] | None = None
    error: str | None = None


@dataclass
class UnloadResult:
    ok: bool
    removed: list[str] | None = None
    error: str | None = None


class PluginManager:
    """Dynamic plugin management — load, unload and reload at runtime."""

    def __init__(self, mcp: FastMCP, config: dict[str, Any]):
        self.mcp = mcp
        self.config = config
        self.plugins: dict[str, LoadedPlugin] = {}
        self._all_tools: set[str] = set()

    def load(self, name: str) -> LoadResult:
        """Load a plugin by name. Returns LoadResult with tools or error."""
        if name in self.plugins:
            return LoadResult(ok=False, error=f"Plugin '{name}' already loaded")

        plugins_config = self.config.get("plugins", {})
        plugin_config = plugins_config.get(name, {})
        if isinstance(plugin_config, dict) and not plugin_config.get("enabled", True):
            return LoadResult(ok=False, error=f"Plugin '{name}' disabled in config")

        module = load_module(name, self.config)
        if module is None:
            return LoadResult(ok=False, error=f"Plugin '{name}' not found")

        register_fn = find_register(module)
        if register_fn is None:
            return LoadResult(ok=False, error=f"Plugin '{name}' has no register() function")

        tracker = ToolTracker(self.mcp)
        try:
            register_fn(tracker, plugin_config if isinstance(plugin_config, dict) else {})
        except Exception as e:
            return LoadResult(ok=False, error=f"Plugin '{name}' register() failed: {e}")

        new_tools = tracker.registered_tools
        collisions = self._all_tools & set(new_tools)
        if collisions:
            # Remove already-registered tools from FastMCP to stay clean
            for tool_name in new_tools:
                self._remove_tool_from_mcp(tool_name)
            return LoadResult(
                ok=False,
                error=f"Tool collision: {', '.join(collisions)} already registered",
            )

        self._all_tools.update(new_tools)
        self.plugins[name] = LoadedPlugin(
            name=name, module=module, tools=new_tools,
            loaded_at=datetime.now(), config=plugin_config if isinstance(plugin_config, dict) else {},
        )
        logger.info("Plugin '%s' loaded: %d tools %s", name, len(new_tools), new_tools)
        return LoadResult(ok=True, tools=new_tools)

    def unload(self, name: str) -> UnloadResult:
        """Unload a plugin. Removes its tools from FastMCP."""
        if name not in self.plugins:
            return UnloadResult(ok=False, error=f"Plugin '{name}' not loaded")

        plugin = self.plugins.pop(name)
        removed = []
        for tool_name in plugin.tools:
            if self._remove_tool_from_mcp(tool_name):
                removed.append(tool_name)
            self._all_tools.discard(tool_name)

        logger.info("Plugin '%s' unloaded: removed %d tools %s", name, len(removed), removed)
        return UnloadResult(ok=True, removed=removed)

    def reload(self, name: str) -> LoadResult:
        """Unload, reimport module, and load again."""
        if name not in self.plugins:
            return LoadResult(ok=False, error=f"Plugin '{name}' not loaded, use load()")

        old_module = self.plugins[name].module
        self.unload(name)

        # Force reimport for fresh code
        try:
            importlib.reload(old_module)
        except Exception as e:
            logger.warning("Could not reload module for '%s': %s", name, e)

        return self.load(name)

    def list_plugins(self) -> dict[str, Any]:
        """Return summary of all loaded plugins."""
        return {
            "total_tools": len(self._all_tools),
            "total_plugins": len(self.plugins),
            "plugins": {
                name: {
                    "tools": p.tools,
                    "tool_count": len(p.tools),
                    "loaded_at": p.loaded_at.isoformat(),
                }
                for name, p in self.plugins.items()
            },
        }

    def _remove_tool_from_mcp(self, tool_name: str) -> bool:
        """Remove a tool from FastMCP internals. Returns True if removed."""
        try:
            # FastMCP stores tools in _tool_manager._tools dict
            tool_manager = getattr(self.mcp, "_tool_manager", None)
            if tool_manager is None:
                return False
            tools_dict = getattr(tool_manager, "_tools", None)
            if tools_dict is None:
                return False
            if tool_name in tools_dict:
                del tools_dict[tool_name]
                return True
            return False
        except Exception as e:
            logger.warning("Failed to remove tool '%s' from FastMCP: %s", tool_name, e)
            return False
