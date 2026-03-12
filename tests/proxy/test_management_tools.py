"""Tests for proxy management MCP tools — tool_list_changed notification."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp.server.fastmcp import FastMCP

from mcp_server_proxy.plugins.management import register
from mcp_server_proxy.proxy import PluginManager


@pytest.fixture
def mcp():
    return FastMCP("test-mgmt-tools")


@pytest.fixture
def proxy(mcp):
    return PluginManager(mcp, config={})


@pytest.fixture
def ctx():
    """Mock Context with session.send_notification and request_context."""
    mock = MagicMock()
    mock.session = MagicMock()
    mock.session.send_notification = AsyncMock()
    # Public API only — no _request_context
    rc = MagicMock()
    rc.request_id = "test-req-1"
    mock.request_context = rc
    return mock


def _get_tool_fn(mcp, name: str):
    """Extract a registered tool function by name."""
    tool_manager = getattr(mcp, "_tool_manager", None)
    tools = getattr(tool_manager, "_tools", {})
    tool = tools.get(name)
    if tool is None:
        raise KeyError(f"Tool '{name}' not registered. Available: {list(tools.keys())}")
    return tool.fn


class TestToolListChangedNotification:
    def test_load_sends_notification(self, mcp, proxy, ctx):
        config = {"_proxy": proxy}
        register(mcp, config)
        fn = _get_tool_fn(mcp, "proxy__load")
        result = asyncio.get_event_loop().run_until_complete(fn("echo", ctx))
        assert "Loaded" in result
        ctx.session.send_notification.assert_awaited_once()
        call_args = ctx.session.send_notification.call_args
        assert call_args.kwargs.get("related_request_id") == "test-req-1"

    def test_load_error_no_notification(self, mcp, proxy, ctx):
        config = {"_proxy": proxy}
        register(mcp, config)
        fn = _get_tool_fn(mcp, "proxy__load")
        result = asyncio.get_event_loop().run_until_complete(fn("nonexistent_xyz", ctx))
        assert "Error" in result
        ctx.session.send_notification.assert_not_awaited()

    def test_unload_sends_notification(self, mcp, proxy, ctx):
        proxy.load("echo")
        config = {"_proxy": proxy}
        register(mcp, config)
        fn = _get_tool_fn(mcp, "proxy__unload")
        result = asyncio.get_event_loop().run_until_complete(fn("echo", ctx))
        assert "Unloaded" in result
        ctx.session.send_notification.assert_awaited_once()

    def test_unload_error_no_notification(self, mcp, proxy, ctx):
        config = {"_proxy": proxy}
        register(mcp, config)
        fn = _get_tool_fn(mcp, "proxy__unload")
        result = asyncio.get_event_loop().run_until_complete(fn("echo", ctx))
        assert "Error" in result
        ctx.session.send_notification.assert_not_awaited()

    def test_reload_sends_notification(self, mcp, proxy, ctx):
        proxy.load("echo")
        config = {"_proxy": proxy}
        register(mcp, config)
        fn = _get_tool_fn(mcp, "proxy__reload")
        result = asyncio.get_event_loop().run_until_complete(fn("echo", ctx))
        assert "Reloaded" in result
        ctx.session.send_notification.assert_awaited_once()

    def test_reload_error_no_notification(self, mcp, proxy, ctx):
        config = {"_proxy": proxy}
        register(mcp, config)
        fn = _get_tool_fn(mcp, "proxy__reload")
        result = asyncio.get_event_loop().run_until_complete(fn("echo", ctx))
        assert "Error" in result
        ctx.session.send_notification.assert_not_awaited()


class TestNoProxy:
    def test_register_without_proxy_is_noop(self, mcp):
        register(mcp, {})
        tool_manager = getattr(mcp, "_tool_manager", None)
        tools = getattr(tool_manager, "_tools", {})
        assert "proxy__load" not in tools
