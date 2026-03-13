"""Introspection helpers — formatted status/list output from a PluginRegistry.

Pure functions, no MCP dependency. Used by Factory and Proxy
to build their management tools.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .registry import PluginRegistry


def plugin_status(registry: PluginRegistry, config: dict[str, Any] | None = None) -> str:
    """Formatted status overview: server info, plugin count, tool count."""
    summary = registry.get_summary()
    config = config or registry.config
    lines = [
        f"Server:    {config.get('server_name', 'MCP Server')}",
        f"Transport: {config.get('transport', 'stdio')}",
    ]
    if config.get("transport") != "stdio":
        lines.append(f"Port:      {config.get('port', 'n/a')}")
        if config.get("health_port"):
            lines.append(f"Health:    {config.get('health_port')}")
    lines.append(f"Plugins:   {summary['total_plugins']} loaded")
    lines.append(f"Tools:     {summary['total_tools']} registered")
    if summary["total_resources"]:
        lines.append(f"Resources: {summary['total_resources']} registered")
    if summary["total_prompts"]:
        lines.append(f"Prompts:   {summary['total_prompts']} registered")
    return "\n".join(lines)


def plugin_list(registry: PluginRegistry) -> str:
    """Formatted list of loaded plugins and their tools."""
    summary = registry.get_summary()
    if not summary["plugins"]:
        return "(no plugins loaded)"
    lines = []
    for name, info in summary["plugins"].items():
        label = " (internal)" if info.get("internal") else ""
        tools_str = ", ".join(info["tools"][:5])
        if info["tool_count"] > 5:
            tools_str += f", ... (+{info['tool_count'] - 5})"
        lines.append(f"  {name:<20} {info['tool_count']:>3} tools{label}")
        lines.append(f"    [{tools_str}]")
    lines.append(f"  {'─' * 40}")
    lines.append(f"  Total: {summary['total_tools']} tools, {summary['total_plugins']} plugins")
    return "\n".join(lines)


def tool_list(registry: PluginRegistry) -> str:
    """Sorted list of all registered tools."""
    summary = registry.get_summary()
    all_tools = []
    for p in summary["plugins"].values():
        all_tools.extend(p["tools"])
    return "\n".join(sorted(all_tools)) or "(no tools loaded)"
