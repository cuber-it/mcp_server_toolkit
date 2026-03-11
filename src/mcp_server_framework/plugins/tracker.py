"""ToolTracker — Proxy that intercepts tool registrations.

Used by Factory and Proxy to track which tools a plugin registers.
Optionally wraps tools with a logging callback.
"""

from __future__ import annotations

import asyncio
import functools
import logging
from typing import Any, Callable

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Optional callback for tool call logging.
# Signature: (tool_name: str, params: dict, result: str, success: bool) -> None
_log_callback: Callable | None = None


def set_log_callback(callback: Callable | None) -> None:
    """Set a callback for tool call logging. Pass None to disable."""
    global _log_callback
    _log_callback = callback


class ToolTracker:
    """Proxy around FastMCP that tracks tool registrations and wraps for logging.

    Args:
        mcp: FastMCP instance to register tools on.
        prefix: Optional prefix for tool names. When set, tools are registered
            as ``{prefix}_{original_name}`` unless they already start with the prefix.
    """

    def __init__(self, mcp: FastMCP, prefix: str | None = None):
        self._mcp = mcp
        self._registered: list[str] = []
        self._prefix = prefix

    @property
    def registered_tools(self) -> list[str]:
        return list(self._registered)

    def _apply_prefix(self, name: str) -> str:
        """Apply prefix to tool name, avoiding double-prefixing."""
        if not self._prefix:
            return name
        if name.startswith(f"{self._prefix}_"):
            return name
        return f"{self._prefix}_{name}"

    def tool(self, *args, **kwargs):
        real_decorator = self._mcp.tool(*args, **kwargs)

        def tracking_decorator(func):
            original_name = func.__name__
            prefixed_name = self._apply_prefix(original_name)
            # Rename function so FastMCP registers it under the prefixed name
            func.__name__ = prefixed_name
            wrapped = _make_logged_wrapper(func, prefixed_name)
            result = real_decorator(wrapped)
            self._registered.append(prefixed_name)
            return result

        return tracking_decorator

    def __getattr__(self, name: str) -> Any:
        return getattr(self._mcp, name)


def _make_logged_wrapper(func, tool_name: str):
    """Wrap a tool function with optional logging."""
    if asyncio.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)
                if _log_callback:
                    _log_callback(tool_name, kwargs, str(result), True)
                return result
            except Exception as e:
                if _log_callback:
                    _log_callback(tool_name, kwargs, str(e), False)
                raise

        return async_wrapper
    else:

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                if _log_callback:
                    _log_callback(tool_name, kwargs, str(result), True)
                return result
            except Exception as e:
                if _log_callback:
                    _log_callback(tool_name, kwargs, str(e), False)
                raise

        return sync_wrapper
