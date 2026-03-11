"""Proxy management tools — load, unload, reload and inspect plugins via MCP."""

from __future__ import annotations


def register(mcp, config: dict) -> None:
    """Register proxy management tools."""
    proxy = config.get("_proxy")
    if proxy is None:
        return

    @mcp.tool()
    def proxy__load(plugin: str) -> str:
        """Load a plugin by name. Makes its tools available immediately."""
        result = proxy.load(plugin)
        if result.ok:
            return f"Loaded '{plugin}': {', '.join(result.tools or [])}"
        return f"Error: {result.error}"

    @mcp.tool()
    def proxy__unload(plugin: str) -> str:
        """Unload a plugin. Removes its tools immediately."""
        result = proxy.unload(plugin)
        if result.ok:
            return f"Unloaded '{plugin}': removed {', '.join(result.removed or [])}"
        return f"Error: {result.error}"

    @mcp.tool()
    def proxy__reload(plugin: str) -> str:
        """Reload a plugin. Picks up code changes without full restart."""
        result = proxy.reload(plugin)
        if result.ok:
            return f"Reloaded '{plugin}': {', '.join(result.tools or [])}"
        return f"Error: {result.error}"

    @mcp.tool()
    def proxy__status() -> str:
        """Show all loaded plugins and their tools."""
        info = proxy.list_plugins()
        lines = [f"Proxy: {info['total_plugins']} plugins, {info['total_tools']} tools\n"]
        for name, p in info["plugins"].items():
            tools_str = ", ".join(p["tools"][:5])
            if p["tool_count"] > 5:
                tools_str += f" (+{p['tool_count'] - 5} more)"
            lines.append(f"  {name}: {tools_str}")
        return "\n".join(lines)

    @mcp.tool()
    def proxy__list() -> str:
        """List all available tools across all plugins."""
        info = proxy.list_plugins()
        all_tools = []
        for p in info["plugins"].values():
            all_tools.extend(p["tools"])
        return "\n".join(sorted(all_tools)) or "(no tools loaded)"
