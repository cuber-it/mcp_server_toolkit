"""ToolTracker — Proxy that intercepts tool registrations."""

from __future__ import annotations

import asyncio
import functools
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


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
    from .plugins.logging import log_settings
    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)
                log_settings.log_call(tool_name, kwargs, str(result), True)
                return result
            except Exception as e:
                log_settings.log_call(tool_name, kwargs, str(e), False)
                raise
        return async_wrapper
    else:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                log_settings.log_call(tool_name, kwargs, str(result), True)
                return result
            except Exception as e:
                log_settings.log_call(tool_name, kwargs, str(e), False)
                raise
        return sync_wrapper
