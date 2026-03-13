"""PluginRegistry — Tracks loaded plugins with collision detection.

Shared data model extracted from Factory and Proxy. Both use this
to track plugins, tools, resources and prompts.
"""

from __future__ import annotations

import logging
from datetime import datetime
from types import ModuleType
from typing import Any

from mcp.server.fastmcp import FastMCP

from .models import LoadedPlugin
from .loader import load_module, find_register
from .tracker import ToolTracker

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Tracks loaded plugins and detects collisions.

    Usage::

        registry = PluginRegistry(mcp, config)
        result = registry.load_plugin("my_plugin")
        if result.ok:
            print(f"Loaded: {result.plugin.tools}")
    """

    def __init__(self, mcp: FastMCP, config: dict[str, Any]):
        self.mcp = mcp
        self.config = config
        self.plugins: dict[str, LoadedPlugin] = {}
        self._all_tools: set[str] = set()
        self._all_resources: set[str] = set()
        self._all_prompts: set[str] = set()

    def load_plugin(
        self,
        name: str,
        module: ModuleType | None = None,
        plugin_config: dict | None = None,
        internal: bool = False,
        prefix: str | None = None,
    ) -> LoadResult:
        """Load a plugin: find register(), track tools, check collisions.

        Args:
            name: Plugin name.
            module: Pre-imported module. If None, uses load_module().
            plugin_config: Config passed to register(). Falls back to config["plugins"][name].
            internal: Mark as internal plugin.
            prefix: Tool name prefix (e.g. "factory" → "factory_status").

        Returns:
            LoadResult with ok=True and plugin, or ok=False and error.
        """
        if name in self.plugins:
            return LoadResult(ok=False, error=f"Plugin '{name}' already loaded")

        if module is None:
            module = load_module(name, self.config)
            if module is None:
                return LoadResult(ok=False, error=f"Plugin '{name}' not found")

        register_fn = find_register(module)
        if register_fn is None:
            return LoadResult(ok=False, error=f"Plugin '{name}' has no register() function")

        if plugin_config is None:
            plugins_cfg = self.config.get("plugins", {})
            plugin_config = plugins_cfg.get(name, {})

        if isinstance(plugin_config, dict) and not plugin_config.get("enabled", True):
            return LoadResult(ok=False, error=f"Plugin '{name}' disabled in config")

        tracker = ToolTracker(self.mcp, prefix=prefix)
        try:
            register_fn(tracker, plugin_config)
        except Exception as e:
            return LoadResult(ok=False, error=f"Plugin '{name}' register() failed: {e}")

        new_tools = tracker.registered_tools
        new_resources = tracker.registered_resources
        new_prompts = tracker.registered_prompts

        # Collision detection
        collision = self._check_collisions(name, new_tools, new_resources, new_prompts)
        if collision:
            # Clean up already-registered tools
            for tool_name in new_tools:
                self._remove_tool(tool_name)
            return LoadResult(ok=False, error=collision)

        # Commit
        self._all_tools.update(new_tools)
        self._all_resources.update(new_resources)
        self._all_prompts.update(new_prompts)

        plugin = LoadedPlugin(
            name=name, module=module, tools=new_tools,
            resources=new_resources, prompts=new_prompts,
            loaded_at=datetime.now(), config=plugin_config,
            internal=internal,
        )
        self.plugins[name] = plugin
        logger.info("Plugin '%s' loaded: %d tools", name, len(new_tools))
        return LoadResult(ok=True, plugin=plugin)

    def unload_plugin(self, name: str) -> UnloadResult:
        """Unload a plugin. Removes its tools from FastMCP."""
        if name not in self.plugins:
            return UnloadResult(ok=False, error=f"Plugin '{name}' not loaded")

        plugin = self.plugins.pop(name)
        removed = []
        for tool_name in plugin.tools:
            if self._remove_tool(tool_name):
                removed.append(tool_name)
            self._all_tools.discard(tool_name)

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
        logger.info("Plugin '%s' unloaded: removed %d tools", name, len(removed))
        return UnloadResult(ok=True, removed=removed)

    def get_summary(self) -> dict[str, Any]:
        """Return summary of all loaded plugins."""
        return {
            "total_tools": len(self._all_tools),
            "total_resources": len(self._all_resources),
            "total_prompts": len(self._all_prompts),
            "total_plugins": len(self.plugins),
            "plugins": {
                name: {
                    "tools": p.tools, "tool_count": len(p.tools),
                    "resources": p.resources, "resource_count": len(p.resources),
                    "prompts": p.prompts, "prompt_count": len(p.prompts),
                    "internal": p.internal, "loaded_at": p.loaded_at.isoformat(),
                }
                for name, p in self.plugins.items()
            },
        }

    def find_tool_owner(self, tool_name: str) -> str | None:
        """Find which plugin owns a tool."""
        for plugin in self.plugins.values():
            if tool_name in plugin.tools:
                return plugin.name
        return None

    @property
    def all_tools(self) -> set[str]:
        return set(self._all_tools)

    @property
    def all_resources(self) -> set[str]:
        return set(self._all_resources)

    @property
    def all_prompts(self) -> set[str]:
        return set(self._all_prompts)

    def _check_collisions(
        self, name: str,
        tools: list[str], resources: list[str], prompts: list[str],
    ) -> str | None:
        """Check for tool/resource/prompt collisions. Returns error message or None."""
        tool_collisions = self._all_tools & set(tools)
        if tool_collisions:
            owners = {t: self.find_tool_owner(t) for t in tool_collisions}
            details = ", ".join(f"'{t}' (in '{o}')" for t, o in owners.items())
            return f"Tool collision loading '{name}': {details}"

        res_collisions = self._all_resources & set(resources)
        if res_collisions:
            return f"Resource collision loading '{name}': {', '.join(res_collisions)}"

        prompt_collisions = self._all_prompts & set(prompts)
        if prompt_collisions:
            return f"Prompt collision loading '{name}': {', '.join(prompt_collisions)}"

        return None

    def _remove_tool(self, tool_name: str) -> bool:
        """Remove a tool from FastMCP. Returns True if removed."""
        try:
            self.mcp.remove_tool(tool_name)
            return True
        except Exception:
            return False


class LoadResult:
    """Result of a plugin load operation."""
    __slots__ = ("ok", "plugin", "error")

    def __init__(self, ok: bool, plugin: LoadedPlugin | None = None, error: str | None = None):
        self.ok = ok
        self.plugin = plugin
        self.error = error

    @property
    def tools(self) -> list[str]:
        return self.plugin.tools if self.plugin else []


class UnloadResult:
    """Result of a plugin unload operation."""
    __slots__ = ("ok", "removed", "error")

    def __init__(self, ok: bool, removed: list[str] | None = None, error: str | None = None):
        self.ok = ok
        self.removed = removed
        self.error = error
