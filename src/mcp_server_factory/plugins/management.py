"""Management plugin — factory__status, factory__list."""

from __future__ import annotations
from typing import Any
from mcp_server_factory import __version__

_factory = None


def register(mcp, config: dict[str, Any]) -> None:
    global _factory
    _factory = config.get("_factory")

    @mcp.tool()
    def factory__status() -> str:
        """Show factory status: version, transport, plugins, tools."""
        if _factory is None:
            return "Factory reference not available"
        summary = _factory.get_plugin_summary()
        fc = _factory.config
        lines = [
            f"MCP Factory v{__version__}",
            f"  Server:    {fc.get('server_name', 'MCP Factory')}",
            f"  Transport: {fc.get('transport', 'stdio')}",
        ]
        if fc.get("transport") != "stdio":
            lines.append(f"  Port:      {fc.get('port', 'n/a')}")
            lines.append(f"  Health:    {fc.get('health_port', 'n/a')}")
        lines.append(f"  Plugins:   {summary['total_plugins']} loaded")
        lines.append(f"  Tools:     {summary['total_tools']} registered")
        from .logging import log_settings
        lines.append(f"  Log:       {'ON' if log_settings.log_enabled else 'OFF'}")
        lines.append(f"  Transcript: {'ON' if log_settings.transcript_enabled else 'OFF'}")
        return "\n".join(lines)

    @mcp.tool()
    def factory__list() -> str:
        """List loaded plugins and their tools."""
        if _factory is None:
            return "Factory reference not available"
        summary = _factory.get_plugin_summary()
        lines = ["Loaded plugins:\n"]
        for name, info in summary["plugins"].items():
            label = " (internal)" if info["internal"] else ""
            tools_str = ", ".join(info["tools"][:5])
            if len(info["tools"]) > 5:
                tools_str += f", ... (+{len(info['tools']) - 5})"
            lines.append(f"  {name:<20} {info['tool_count']:>3} tools{label}")
            lines.append(f"    [{tools_str}]")
        lines.append(f"  {'─' * 40}")
        lines.append(f"  Total: {summary['total_tools']} tools, {summary['total_plugins']} plugins")
        return "\n".join(lines)
