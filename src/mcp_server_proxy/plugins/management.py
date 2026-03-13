"""Proxy management tools — load, unload, reload and inspect plugins via MCP."""

from __future__ import annotations

import logging

from mcp import types
from mcp.server.fastmcp import Context
from mcp_server_framework.plugins import list_available_plugins, plugin_status, plugin_list, tool_list

logger = logging.getLogger(__name__)


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

    if proxy.dynamic_dispatch_enabled:
        @mcp.tool()
        async def proxy__run(tool: str, arguments: dict | None = None) -> str:
            """Run a dynamically loaded tool by name.

            Only tools loaded at runtime (after startup) are available.
            Use proxy__tools(dynamic_only=true) to see available dynamic tools.
            """
            dynamic = proxy.dynamic_tools
            if tool not in dynamic:
                if tool in proxy._startup_tools:
                    return f"Error: '{tool}' is a static tool — call it directly, not via proxy__run."
                return f"Error: '{tool}' not found. Available dynamic tools: {', '.join(dynamic) or '(none)'}"
            try:
                result = await proxy.mcp.call_tool(tool, arguments or {})
                # call_tool returns (content_blocks, raw_result) tuple
                blocks = result[0] if isinstance(result, tuple) else result
                parts = []
                for block in blocks:
                    if hasattr(block, "text"):
                        parts.append(block.text)
                    else:
                        parts.append(str(block))
                return "\n".join(parts) or "(empty result)"
            except Exception as e:
                logger.error("proxy__run '%s' failed: %s", tool, e)
                return f"Error calling '{tool}': {e}"

    @mcp.tool()
    async def proxy__load(plugin: str, ctx: Context) -> str:
        """Load a plugin by name. Makes its tools available immediately."""
        result = proxy.load(plugin)
        if result.ok:
            await _send_list_changed_notifications(ctx, proxy, plugin)
            msg = f"Loaded '{plugin}': {', '.join(result.tools or [])}"
            if proxy.dynamic_dispatch_enabled and proxy._startup_complete:
                msg += (
                    f"\n\nThese tools are dynamically loaded. "
                    f"Call them via proxy__run(tool='<name>', arguments={{...}}). "
                    f"Example: proxy__run(tool='{(result.tools or ['tool_name'])[0]}')"
                )
            return msg
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
        return plugin_status(proxy.registry)

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
    def proxy__tools(dynamic_only: bool = False) -> str:
        """List loaded tools. Set dynamic_only=true to see only dynamically loaded tools (usable via proxy__run)."""
        if dynamic_only:
            tools = proxy.dynamic_tools
            if not tools:
                return "(no dynamic tools loaded)"
            return "\n".join(tools)
        return tool_list(proxy.registry)
