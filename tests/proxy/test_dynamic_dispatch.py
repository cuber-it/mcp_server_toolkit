"""Tests for dynamic dispatch — proxy__run, startup vs dynamic tools."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp.server.fastmcp import FastMCP

from mcp_server_proxy.plugins.management import register
from mcp_server_proxy.proxy import PluginManager


@pytest.fixture
def mcp():
    return FastMCP("test-dispatch")


@pytest.fixture
def proxy_with_dispatch(mcp):
    return PluginManager(mcp, config={"dynamic_dispatch": True})


@pytest.fixture
def proxy_without_dispatch(mcp):
    return PluginManager(mcp, config={})


@pytest.fixture
def ctx():
    mock = MagicMock()
    mock.session = MagicMock()
    mock.session.send_notification = AsyncMock()
    rc = MagicMock()
    rc.request_id = "test-req-1"
    mock.request_context = rc
    return mock


def _get_tool_fn(mcp, name: str):
    tool_manager = getattr(mcp, "_tool_manager", None)
    tools = getattr(tool_manager, "_tools", {})
    tool = tools.get(name)
    if tool is None:
        raise KeyError(f"Tool '{name}' not registered. Available: {list(tools.keys())}")
    return tool.fn


class TestStartupTracking:
    def test_startup_not_complete_by_default(self, proxy_with_dispatch):
        assert not proxy_with_dispatch._startup_complete

    def test_mark_startup_done(self, proxy_with_dispatch):
        proxy_with_dispatch.load("echo")
        proxy_with_dispatch.mark_startup_done()
        assert proxy_with_dispatch._startup_complete
        assert "echo" in proxy_with_dispatch._startup_tools
        assert "echo_upper" in proxy_with_dispatch._startup_tools

    def test_plugin_loaded_before_startup_is_static(self, proxy_with_dispatch):
        proxy_with_dispatch.load("echo")
        assert proxy_with_dispatch.plugins["echo"].startup is True

    def test_plugin_loaded_after_startup_is_dynamic(self, proxy_with_dispatch):
        proxy_with_dispatch.mark_startup_done()
        proxy_with_dispatch.load("echo")
        assert proxy_with_dispatch.plugins["echo"].startup is False

    def test_dynamic_tools_empty_before_runtime_load(self, proxy_with_dispatch):
        proxy_with_dispatch.load("echo")
        proxy_with_dispatch.mark_startup_done()
        assert proxy_with_dispatch.dynamic_tools == []

    def test_dynamic_tools_after_runtime_load(self, proxy_with_dispatch):
        proxy_with_dispatch.load("echo")
        proxy_with_dispatch.mark_startup_done()
        proxy_with_dispatch.load("greet")
        assert "greet" in proxy_with_dispatch.dynamic_tools
        assert "echo" not in proxy_with_dispatch.dynamic_tools


class TestDynamicDispatchEnabled:
    def test_proxy_run_registered_when_enabled(self, mcp, proxy_with_dispatch):
        register(mcp, {"_proxy": proxy_with_dispatch})
        tool_manager = getattr(mcp, "_tool_manager", None)
        tools = getattr(tool_manager, "_tools", {})
        assert "proxy__run" in tools

    def test_proxy_run_not_registered_when_disabled(self, mcp, proxy_without_dispatch):
        register(mcp, {"_proxy": proxy_without_dispatch})
        tool_manager = getattr(mcp, "_tool_manager", None)
        tools = getattr(tool_manager, "_tools", {})
        assert "proxy__run" not in tools


class TestProxyRun:
    def test_run_dynamic_tool(self, mcp, proxy_with_dispatch):
        register(mcp, {"_proxy": proxy_with_dispatch})
        proxy_with_dispatch.load("echo")
        proxy_with_dispatch.mark_startup_done()
        proxy_with_dispatch.load("greet")

        fn = _get_tool_fn(mcp, "proxy__run")
        result = asyncio.get_event_loop().run_until_complete(
            fn("greet", {"name": "World"})
        )
        assert "World" in result

    def test_run_static_tool_rejected(self, mcp, proxy_with_dispatch):
        proxy_with_dispatch.load("echo")
        proxy_with_dispatch.mark_startup_done()
        register(mcp, {"_proxy": proxy_with_dispatch})

        fn = _get_tool_fn(mcp, "proxy__run")
        result = asyncio.get_event_loop().run_until_complete(
            fn("echo", {})
        )
        assert "static tool" in result
        assert "call it directly" in result

    def test_run_unknown_tool(self, mcp, proxy_with_dispatch):
        proxy_with_dispatch.mark_startup_done()
        register(mcp, {"_proxy": proxy_with_dispatch})

        fn = _get_tool_fn(mcp, "proxy__run")
        result = asyncio.get_event_loop().run_until_complete(
            fn("nonexistent", {})
        )
        assert "not found" in result

    def test_run_no_arguments(self, mcp, proxy_with_dispatch):
        register(mcp, {"_proxy": proxy_with_dispatch})
        proxy_with_dispatch.load("echo")
        proxy_with_dispatch.mark_startup_done()
        proxy_with_dispatch.load("greet")

        fn = _get_tool_fn(mcp, "proxy__run")
        result = asyncio.get_event_loop().run_until_complete(
            fn("greet", {"name": "Test"})
        )
        assert "Test" in result


class TestProxyToolsDynamicOnly:
    def test_dynamic_only_filter(self, mcp, proxy_with_dispatch):
        proxy_with_dispatch.load("echo")
        proxy_with_dispatch.mark_startup_done()
        proxy_with_dispatch.load("greet")
        register(mcp, {"_proxy": proxy_with_dispatch})

        fn = _get_tool_fn(mcp, "proxy__tools")
        all_result = fn(False)
        dynamic_result = fn(True)
        assert "echo" in all_result
        assert "greet" in all_result
        assert "echo" not in dynamic_result
        assert "greet" in dynamic_result

    def test_dynamic_only_empty(self, mcp, proxy_with_dispatch):
        proxy_with_dispatch.load("echo")
        proxy_with_dispatch.mark_startup_done()
        register(mcp, {"_proxy": proxy_with_dispatch})

        fn = _get_tool_fn(mcp, "proxy__tools")
        result = fn(True)
        assert "no dynamic tools" in result


class TestLoadHint:
    def test_load_hint_when_dynamic_dispatch(self, mcp, proxy_with_dispatch, ctx):
        proxy_with_dispatch.mark_startup_done()
        register(mcp, {"_proxy": proxy_with_dispatch})
        fn = _get_tool_fn(mcp, "proxy__load")
        result = asyncio.get_event_loop().run_until_complete(fn("echo", ctx))
        assert "proxy__run" in result

    def test_no_hint_during_startup(self, mcp, proxy_with_dispatch, ctx):
        register(mcp, {"_proxy": proxy_with_dispatch})
        fn = _get_tool_fn(mcp, "proxy__load")
        result = asyncio.get_event_loop().run_until_complete(fn("echo", ctx))
        assert "proxy__run" not in result

    def test_no_hint_when_dispatch_disabled(self, mcp, proxy_without_dispatch, ctx):
        proxy_without_dispatch.mark_startup_done()
        register(mcp, {"_proxy": proxy_without_dispatch})
        fn = _get_tool_fn(mcp, "proxy__load")
        result = asyncio.get_event_loop().run_until_complete(fn("echo", ctx))
        assert "proxy__run" not in result
