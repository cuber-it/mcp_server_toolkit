"""Management plugin — factory__status, factory__list."""

from __future__ import annotations

from typing import Any
from mcp_server_factory import __version__
from mcp_server_framework.plugins import plugin_status, plugin_list

_factory = None


def register(mcp, config: dict[str, Any]) -> None:
    global _factory
    _factory = config.get("_factory")

    @mcp.tool()
    def factory__status() -> str:
        """Show factory status: version, transport, plugins, tools."""
        if _factory is None:
            return "Factory reference not available"
        lines = [f"MCP Factory v{__version__}"]
        lines.append(plugin_status(_factory.registry))
        from .logging import log_settings
        lines.append(f"Log:       {'ON' if log_settings.log_enabled else 'OFF'}")
        lines.append(f"Transcript: {'ON' if log_settings.transcript_enabled else 'OFF'}")
        return "\n".join(lines)

    @mcp.tool()
    def factory__list() -> str:
        """List loaded plugins and their tools."""
        if _factory is None:
            return "Factory reference not available"
        return "Loaded plugins:\n\n" + plugin_list(_factory.registry)
