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


class TestAutoPrefix:
    def test_prefix_disabled_by_default(self):
        mcp = FastMCP("test-noprefix")
        proxy = PluginManager(mcp, config={})
        result = proxy.load("echo")
        assert result.ok
        assert "echo" in result.tools  # no prefix

    def test_auto_prefix_adds_plugin_name(self):
        mcp = FastMCP("test-autoprefix")
        proxy = PluginManager(mcp, config={"auto_prefix": True})
        result = proxy.load("echo")
        assert result.ok
        # "echo" → "echo_echo", "echo_upper" already starts with "echo_" → kept
        assert "echo_echo" in result.tools
        assert "echo_upper" in result.tools  # no double prefix

    def test_auto_prefix_on_unprefixed_tool(self):
        """Tools without matching prefix get prefixed."""
        mcp = FastMCP("test-prefix-greet")
        proxy = PluginManager(mcp, config={"auto_prefix": True})
        result = proxy.load("greet")
        assert result.ok
        # "greet" does not start with "greet_", so it becomes "greet_greet"
        assert "greet_greet" in result.tools

    def test_custom_prefix_per_plugin(self):
        mcp = FastMCP("test-customprefix")
        proxy = PluginManager(mcp, config={
            "auto_prefix": False,
            "plugins": {"echo": {"prefix": "myecho"}},
        })
        result = proxy.load("echo")
        assert result.ok
        assert "myecho_echo" in result.tools
        assert "myecho_echo_upper" in result.tools

    def test_prefix_false_disables(self):
        mcp = FastMCP("test-prefixoff")
        proxy = PluginManager(mcp, config={
            "auto_prefix": True,
            "plugins": {"echo": {"prefix": False}},
        })
        result = proxy.load("echo")
        assert result.ok
        assert "echo" in result.tools  # no prefix despite auto_prefix

    def test_prefixed_tools_unload_correctly(self):
        mcp = FastMCP("test-prefix-unload")
        proxy = PluginManager(mcp, config={"auto_prefix": True})
        proxy.load("echo")
        result = proxy.unload("echo")
        assert result.ok
        assert "echo_echo" in result.removed
        tool_manager = getattr(mcp, "_tool_manager", None)
        tools_dict = getattr(tool_manager, "_tools", {})
        assert "echo_echo" not in tools_dict


class TestCommandRegistry:
    def test_register_and_run(self, proxy):
        proxy.register_command("ping", lambda p: "pong")
        assert "ping" in proxy.commands
        assert proxy.run_command("ping") == "pong"

    def test_unknown_command(self, proxy):
        result = proxy.run_command("nonexistent")
        assert "Unknown" in result

    def test_command_receives_proxy(self, proxy):
        def my_cmd(p, **kwargs):
            return f"plugins: {len(p.plugins)}"
        proxy.register_command("count", my_cmd)
        assert proxy.run_command("count") == "plugins: 0"

    def test_command_error_handling(self, proxy):
        proxy.register_command("fail", lambda p: 1/0)
        result = proxy.run_command("fail")
        assert "failed" in result


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
