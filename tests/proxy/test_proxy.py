"""Tests for PluginManager — load, unload, reload, collision detection."""

import pytest
from mcp.server.fastmcp import FastMCP

from mcp_server_proxy.proxy import PluginManager, LoadResult, UnloadResult


@pytest.fixture
def mcp():
    return FastMCP("test-proxy")


@pytest.fixture
def proxy(mcp):
    return PluginManager(mcp, config={})


class TestLoad:
    def test_load_echo(self, proxy):
        result = proxy.load("echo")
        assert result.ok
        assert "echo" in result.tools
        assert "echo_upper" in result.tools
        assert "echo" in proxy.plugins

    def test_load_unknown_plugin(self, proxy):
        result = proxy.load("nonexistent_plugin_xyz")
        assert not result.ok
        assert "not found" in result.error

    def test_load_duplicate(self, proxy):
        proxy.load("echo")
        result = proxy.load("echo")
        assert not result.ok
        assert "already loaded" in result.error

    def test_load_disabled_plugin(self, proxy):
        proxy.config["plugins"] = {"echo": {"enabled": False}}
        result = proxy.load("echo")
        assert not result.ok
        assert "disabled" in result.error

    def test_tools_registered_in_mcp(self, proxy):
        proxy.load("echo")
        tool_manager = getattr(proxy.mcp, "_tool_manager", None)
        tools_dict = getattr(tool_manager, "_tools", {})
        assert "echo" in tools_dict
        assert "echo_upper" in tools_dict


class TestUnload:
    def test_unload(self, proxy):
        proxy.load("echo")
        result = proxy.unload("echo")
        assert result.ok
        assert "echo" in result.removed
        assert "echo" not in proxy.plugins

    def test_unload_not_loaded(self, proxy):
        result = proxy.unload("echo")
        assert not result.ok
        assert "not loaded" in result.error

    def test_unload_removes_from_mcp(self, proxy):
        proxy.load("echo")
        proxy.unload("echo")
        tool_manager = getattr(proxy.mcp, "_tool_manager", None)
        tools_dict = getattr(tool_manager, "_tools", {})
        assert "echo" not in tools_dict
        assert "echo_upper" not in tools_dict

    def test_unload_clears_tracking(self, proxy):
        proxy.load("echo")
        proxy.unload("echo")
        assert len(proxy._all_tools) == 0


class TestReload:
    def test_reload(self, proxy):
        proxy.load("echo")
        result = proxy.reload("echo")
        assert result.ok
        assert "echo" in result.tools

    def test_reload_not_loaded(self, proxy):
        result = proxy.reload("echo")
        assert not result.ok
        assert "not loaded" in result.error


class TestMultiPlugin:
    def test_load_two_plugins(self, proxy):
        r1 = proxy.load("echo")
        r2 = proxy.load("greet")
        assert r1.ok
        assert r2.ok
        assert len(proxy.plugins) == 2
        assert "greet" in proxy._all_tools

    def test_unload_one_keeps_other(self, proxy):
        proxy.load("echo")
        proxy.load("greet")
        proxy.unload("echo")
        assert "echo" not in proxy.plugins
        assert "greet" in proxy.plugins
        tool_manager = getattr(proxy.mcp, "_tool_manager", None)
        tools_dict = getattr(tool_manager, "_tools", {})
        assert "greet" in tools_dict
        assert "echo" not in tools_dict


class TestListPlugins:
    def test_empty(self, proxy):
        info = proxy.list_plugins()
        assert info["total_plugins"] == 0
        assert info["total_tools"] == 0

    def test_with_plugins(self, proxy):
        proxy.load("echo")
        proxy.load("greet")
        info = proxy.list_plugins()
        assert info["total_plugins"] == 2
        assert info["total_tools"] == 3  # echo, echo_upper, greet
        assert "echo" in info["plugins"]
        assert "greet" in info["plugins"]
