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
    """Proxy around FastMCP that tracks tool registrations and wraps for logging."""

    def __init__(self, mcp: FastMCP):
        self._mcp = mcp
        self._registered: list[str] = []

    @property
    def registered_tools(self) -> list[str]:
        return list(self._registered)

    def tool(self, *args, **kwargs):
        real_decorator = self._mcp.tool(*args, **kwargs)

        def tracking_decorator(func):
            tool_name = func.__name__
            wrapped = _make_logged_wrapper(func, tool_name)
            result = real_decorator(wrapped)
            self._registered.append(tool_name)
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
