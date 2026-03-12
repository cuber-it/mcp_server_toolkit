"""Proxy — Dynamic plugin manager with runtime load/unload."""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from datetime import datetime
from types import ModuleType
from typing import Any, Callable

from mcp.server.fastmcp import FastMCP

from mcp_server_framework.plugins import LoadedPlugin, load_module, load_plugin_config, find_register, ToolTracker

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
    """Dynamic plugin management — load, unload and reload at runtime.

    Supports management command extensions via ``register_command()``.
    Extensions can add MCP tools and FastAPI endpoints for custom management.
    """

    def __init__(self, mcp: FastMCP, config: dict[str, Any]):
        self.mcp = mcp
        self.config = config
        self.plugins: dict[str, LoadedPlugin] = {}
        self._all_tools: set[str] = set()
        self._all_resources: set[str] = set()
        self._all_prompts: set[str] = set()
        self._commands: dict[str, Callable] = {}

    def register_command(self, name: str, handler: Callable) -> None:
        """Register a management command extension.

        Args:
            name: Command name (e.g. "backup", "metrics").
            handler: Callable(proxy, **kwargs) -> str. Will be exposed
                via MCP tool ``proxy__<name>`` and management API.
        """
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
        """List registered management commands."""
        return list(self._commands.keys())

    def load(self, name: str) -> LoadResult:
        """Load a plugin by name. Returns LoadResult with tools or error."""
        if name in self.plugins:
            return LoadResult(ok=False, error=f"Plugin '{name}' already loaded")

        # Plugin config: plugin_dir/{name}/config.yaml, fallback to proxy config
        plugin_config = load_plugin_config(name)
        if not plugin_config:
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

        prefix = self._resolve_prefix(name, plugin_config if isinstance(plugin_config, dict) else {})
        tracker = ToolTracker(self.mcp, prefix=prefix)
        try:
            register_fn(tracker, plugin_config if isinstance(plugin_config, dict) else {})
        except Exception as e:
            return LoadResult(ok=False, error=f"Plugin '{name}' register() failed: {e}")

        new_tools = tracker.registered_tools
        new_resources = tracker.registered_resources
        new_prompts = tracker.registered_prompts
        collisions = self._all_tools & set(new_tools)
        if collisions:
            # Remove already-registered tools from FastMCP to stay clean
            for tool_name in new_tools:
                self._remove_tool_from_mcp(tool_name)
            return LoadResult(
                ok=False,
                error=f"Tool collision: {', '.join(collisions)} already registered",
            )
        res_collisions = self._all_resources & set(new_resources)
        if res_collisions:
            for tool_name in new_tools:
                self._remove_tool_from_mcp(tool_name)
            return LoadResult(
                ok=False,
                error=f"Resource collision: {', '.join(res_collisions)} already registered",
            )
        prompt_collisions = self._all_prompts & set(new_prompts)
        if prompt_collisions:
            for tool_name in new_tools:
                self._remove_tool_from_mcp(tool_name)
            return LoadResult(
                ok=False,
                error=f"Prompt collision: {', '.join(prompt_collisions)} already registered",
            )

        self._all_tools.update(new_tools)
        self._all_resources.update(new_resources)
        self._all_prompts.update(new_prompts)
        pcfg = plugin_config if isinstance(plugin_config, dict) else {}
        self.plugins[name] = LoadedPlugin(
            name=name, module=module, tools=new_tools,
            resources=new_resources, prompts=new_prompts,
            loaded_at=datetime.now(), config=pcfg,
        )
        logger.info("Plugin '%s' loaded: %d tools, %d resources, %d prompts",
                     name, len(new_tools), len(new_resources), len(new_prompts))
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

        # Resources/prompts: remove from tracking.
        # FastMCP has no remove_resource()/remove_prompt() API (SDK 1.26),
        # so we can only clean our tracking sets. Log a warning if present.
        for uri in plugin.resources:
            self._all_resources.discard(uri)
        for prompt_name in plugin.prompts:
            self._all_prompts.discard(prompt_name)
        if plugin.resources or plugin.prompts:
            logger.warning(
                "Plugin '%s' had %d resources, %d prompts — "
                "removed from tracking but FastMCP has no removal API",
                name, len(plugin.resources), len(plugin.prompts),
            )

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
            "total_resources": len(self._all_resources),
            "total_prompts": len(self._all_prompts),
            "total_plugins": len(self.plugins),
            "plugins": {
                name: {
                    "tools": p.tools,
                    "tool_count": len(p.tools),
                    "resources": p.resources,
                    "resource_count": len(p.resources),
                    "prompts": p.prompts,
                    "prompt_count": len(p.prompts),
                    "loaded_at": p.loaded_at.isoformat(),
                }
                for name, p in self.plugins.items()
            },
        }

    def _resolve_prefix(self, plugin_name: str, plugin_config: dict) -> str | None:
        """Determine the tool name prefix for a plugin.

        Priority:
            1. Per-plugin ``prefix`` in config (False = no prefix, str = custom)
            2. Global ``auto_prefix`` in proxy config (default: True → use plugin name)
        """
        # Per-plugin override
        if "prefix" in plugin_config:
            val = plugin_config["prefix"]
            if val is False or val == "":
                return None
            return str(val)

        # Global setting
        auto_prefix = self.config.get("auto_prefix", False)
        if auto_prefix:
            return plugin_name
        return None

    def _remove_tool_from_mcp(self, tool_name: str) -> bool:
        """Remove a tool from FastMCP. Returns True if removed."""
        try:
            self.mcp.remove_tool(tool_name)
            return True
        except Exception:
            return False
