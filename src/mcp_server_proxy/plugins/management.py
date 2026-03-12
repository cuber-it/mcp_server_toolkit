"""Proxy management tools — load, unload, reload and inspect plugins via MCP."""

from __future__ import annotations

from mcp import types
from mcp.server.fastmcp import Context
from mcp_server_framework.plugins import list_available_plugins


def _get_request_id(ctx: Context):
    """Extract request_id from context without using private API."""
    try:
        return ctx.request_context.request_id
    except (AttributeError, RuntimeError):
        return None


async def _send_list_changed_notifications(ctx: Context, proxy, plugin_name: str) -> None:
    """Send spec-conformant list_changed notifications for affected capabilities."""
    request_id = _get_request_id(ctx)
    plugin = proxy.plugins.get(plugin_name)

    # Always send tools/list_changed (load/unload always affects tools)
    await ctx.session.send_notification(
        types.ServerNotification(types.ToolListChangedNotification()),
        related_request_id=request_id,
    )

    # Send resources/list_changed if plugin has resources
    if plugin and plugin.resources:
        await ctx.session.send_notification(
            types.ServerNotification(types.ResourceListChangedNotification()),
            related_request_id=request_id,
        )

    # Send prompts/list_changed if plugin has prompts
    if plugin and plugin.prompts:
        await ctx.session.send_notification(
            types.ServerNotification(types.PromptListChangedNotification()),
            related_request_id=request_id,
        )


def register(mcp, config: dict) -> None:
    """Register proxy management tools."""
    proxy = config.get("_proxy")
    if proxy is None:
        return

    @mcp.tool()
    async def proxy__load(plugin: str, ctx: Context) -> str:
        """Load a plugin by name. Makes its tools available immediately."""
        result = proxy.load(plugin)
        if result.ok:
            await _send_list_changed_notifications(ctx, proxy, plugin)
            return f"Loaded '{plugin}': {', '.join(result.tools or [])}"
        return f"Error: {result.error}"

    @mcp.tool()
    async def proxy__unload(plugin: str, ctx: Context) -> str:
        """Unload a plugin. Removes its tools immediately."""
        # Capture plugin info before unload removes it
        had_resources = bool(proxy.plugins.get(plugin, None) and proxy.plugins[plugin].resources)
        had_prompts = bool(proxy.plugins.get(plugin, None) and proxy.plugins[plugin].prompts)
        result = proxy.unload(plugin)
        if result.ok:
            request_id = _get_request_id(ctx)
            await ctx.session.send_notification(
                types.ServerNotification(types.ToolListChangedNotification()),
                related_request_id=request_id,
            )
            if had_resources:
                await ctx.session.send_notification(
                    types.ServerNotification(types.ResourceListChangedNotification()),
                    related_request_id=request_id,
                )
            if had_prompts:
                await ctx.session.send_notification(
                    types.ServerNotification(types.PromptListChangedNotification()),
                    related_request_id=request_id,
                )
            return f"Unloaded '{plugin}': removed {', '.join(result.removed or [])}"
        return f"Error: {result.error}"

    @mcp.tool()
    async def proxy__reload(plugin: str, ctx: Context) -> str:
        """Reload a plugin. Picks up code changes without full restart."""
        result = proxy.reload(plugin)
        if result.ok:
            await _send_list_changed_notifications(ctx, proxy, plugin)
            return f"Reloaded '{plugin}': {', '.join(result.tools or [])}"
        return f"Error: {result.error}"

    @mcp.tool()
    def proxy__status() -> str:
        """Show all loaded plugins and their tools, resources, prompts."""
        info = proxy.list_plugins()
        parts = [f"{info['total_tools']} tools"]
        if info["total_resources"]:
            parts.append(f"{info['total_resources']} resources")
        if info["total_prompts"]:
            parts.append(f"{info['total_prompts']} prompts")
        lines = [f"Proxy: {info['total_plugins']} plugins, {', '.join(parts)}\n"]
        for name, p in info["plugins"].items():
            tools_str = ", ".join(p["tools"][:5])
            if p["tool_count"] > 5:
                tools_str += f" (+{p['tool_count'] - 5} more)"
            extras = []
            if p["resource_count"]:
                extras.append(f"{p['resource_count']} resources")
            if p["prompt_count"]:
                extras.append(f"{p['prompt_count']} prompts")
            extra_str = f" [{', '.join(extras)}]" if extras else ""
            lines.append(f"  {name}: {tools_str}{extra_str}")
        return "\n".join(lines)

    @mcp.tool()
    def proxy__list() -> str:
        """List available plugins in configured plugin directories."""
        available = list_available_plugins()
        if not available:
            return "(no plugins found in plugin directories)"
        lines = []
        for p in available:
            desc = f" — {p['description']}" if p["description"] else ""
            lines.append(f"  {p['name']}{desc}")
        return "\n".join(lines)

    @mcp.tool()
    def proxy__tools() -> str:
        """List all loaded tools across all plugins."""
        info = proxy.list_plugins()
        all_tools = []
        for p in info["plugins"].values():
            all_tools.extend(p["tools"])
        return "\n".join(sorted(all_tools)) or "(no tools loaded)"
