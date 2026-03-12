"""Factory — Core orchestrator for plugin loading and management."""

from __future__ import annotations

import logging
from datetime import datetime
from types import ModuleType
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp_server_framework.plugins import LoadedPlugin, load_module, find_register, ToolTracker

logger = logging.getLogger(__name__)


class Factory:
    """Plugin-based MCP server factory."""

    def __init__(self, mcp: FastMCP, config: dict[str, Any]):
        self.mcp = mcp
        self.config = config
        self.plugins: dict[str, LoadedPlugin] = {}
        self._all_tools: set[str] = set()
        self._all_resources: set[str] = set()
        self._all_prompts: set[str] = set()

    def load_internals(self) -> None:
        """Load internal factory plugins (management, logging)."""
        from .plugins import management, logging as factory_logging
        internal_config = {"_factory": self}
        self._load_module(management, "factory_management", internal_config, internal=True)
        self._load_module(factory_logging, "factory_logging", internal_config, internal=True)

    def load_externals(self, plugin_names: list[str]) -> list[str]:
        """Load external plugins by name. Returns list of successfully loaded names."""
        loaded = []
        plugins_config = self.config.get("plugins", {})
        for name in plugin_names:
            plugin_config = plugins_config.get(name, {})
            if isinstance(plugin_config, dict) and not plugin_config.get("enabled", True):
                logger.info("Plugin '%s' disabled in config, skipping", name)
                continue
            module = load_module(name, self.config)
            if module is None:
                logger.error("Plugin '%s' not found", name)
                continue
            if self._load_module(module, name, plugin_config, internal=False):
                loaded.append(name)
        return loaded

    def _load_module(self, module: ModuleType, name: str, plugin_config: dict, internal: bool) -> bool:
        """Load a single module: find register(), track tools, check collisions."""
        register_fn = find_register(module)
        if register_fn is None:
            logger.error("Plugin '%s' has no register(mcp, config) function", name)
            return False
        tracker = ToolTracker(self.mcp)
        try:
            register_fn(tracker, plugin_config)
        except Exception as e:
            logger.error("Plugin '%s' register() failed: %s", name, e)
            return False
        new_tools = tracker.registered_tools
        new_resources = tracker.registered_resources
        new_prompts = tracker.registered_prompts
        collisions = self._all_tools & set(new_tools)
        if collisions:
            for tool_name in collisions:
                owner = self._find_tool_owner(tool_name)
                logger.error("Tool collision: '%s' already in plugin '%s', cannot load '%s'", tool_name, owner, name)
            return False
        res_collisions = self._all_resources & set(new_resources)
        if res_collisions:
            logger.error("Resource collision: %s, cannot load '%s'", res_collisions, name)
            return False
        prompt_collisions = self._all_prompts & set(new_prompts)
        if prompt_collisions:
            logger.error("Prompt collision: %s, cannot load '%s'", prompt_collisions, name)
            return False
        self._all_tools.update(new_tools)
        self._all_resources.update(new_resources)
        self._all_prompts.update(new_prompts)
        self.plugins[name] = LoadedPlugin(
            name=name, module=module, tools=new_tools,
            resources=new_resources, prompts=new_prompts,
            loaded_at=datetime.now(), config=plugin_config, internal=internal,
        )
        label = "internal" if internal else "external"
        logger.info("Plugin '%s' loaded (%s): %d tools", name, label, len(new_tools))
        return True

    def _find_tool_owner(self, tool_name: str) -> str:
        for plugin in self.plugins.values():
            if tool_name in plugin.tools:
                return plugin.name
        return "unknown"

    def get_plugin_summary(self) -> dict[str, Any]:
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
