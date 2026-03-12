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

# Optional pre-call validator.
# Signature: (tool_name: str, params: dict) -> str | None
# Return error message to reject the call, or None to allow.
_pre_call_validator: Callable | None = None


def set_log_callback(callback: Callable | None) -> None:
    """Set a callback for tool call logging. Pass None to disable."""
    global _log_callback
    _log_callback = callback


def set_pre_call_validator(validator: Callable | None) -> None:
    """Set a validator called before each tool invocation.

    Args:
        validator: Callable(tool_name, params) -> str | None.
            Return an error string to reject the call, None to allow.
    """
    global _pre_call_validator
    _pre_call_validator = validator


class ToolTracker:
    """Proxy around FastMCP that tracks tool, resource and prompt registrations.

    Args:
        mcp: FastMCP instance to register on.
        prefix: Optional prefix for tool names. When set, tools are registered
            as ``{prefix}_{original_name}`` unless they already start with the prefix.
    """

    def __init__(self, mcp: FastMCP, prefix: str | None = None):
        self._mcp = mcp
        self._registered: list[str] = []
        self._registered_resources: list[str] = []
        self._registered_prompts: list[str] = []
        self._prefix = prefix

    @property
    def registered_tools(self) -> list[str]:
        return list(self._registered)

    @property
    def registered_resources(self) -> list[str]:
        return list(self._registered_resources)

    @property
    def registered_prompts(self) -> list[str]:
        return list(self._registered_prompts)

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

    def resource(self, uri: str, *args, **kwargs):
        real_decorator = self._mcp.resource(uri, *args, **kwargs)

        def tracking_decorator(func):
            result = real_decorator(func)
            self._registered_resources.append(uri)
            return result

        return tracking_decorator

    def prompt(self, *args, **kwargs):
        real_decorator = self._mcp.prompt(*args, **kwargs)

        def tracking_decorator(func):
            name = kwargs.get("name", func.__name__)
            result = real_decorator(func)
            self._registered_prompts.append(name)
            return result

        return tracking_decorator

    def __getattr__(self, name: str) -> Any:
        return getattr(self._mcp, name)


def _make_logged_wrapper(func, tool_name: str):
    """Wrap a tool function with optional pre-call validation and logging."""
    if asyncio.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            if _pre_call_validator:
                error = _pre_call_validator(tool_name, kwargs)
                if error:
                    return f"Rejected: {error}"
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
            if _pre_call_validator:
                error = _pre_call_validator(tool_name, kwargs)
                if error:
                    return f"Rejected: {error}"
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
