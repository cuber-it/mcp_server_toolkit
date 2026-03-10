"""Tests for factory core."""
from mcp.server.fastmcp import FastMCP
from mcp_server_factory.factory import Factory


def _make_factory() -> Factory:
    mcp = FastMCP("Test Factory")
    config = {"_factory": None}
    factory = Factory(mcp, config)
    config["_factory"] = factory
    return factory


def test_load_internals():
    factory = _make_factory()
    factory.load_internals()
    assert "factory_management" in factory.plugins
    assert "factory_logging" in factory.plugins
    assert factory.plugins["factory_management"].internal is True

def test_load_echo_plugin():
    factory = _make_factory()
    loaded = factory.load_externals(["echo"])
    assert "echo" in loaded
    assert "echo" in factory.plugins
    assert "echo" in factory.plugins["echo"].tools
    assert "echo_upper" in factory.plugins["echo"].tools
    assert factory.plugins["echo"].internal is False

def test_load_unknown_plugin():
    factory = _make_factory()
    assert factory.load_externals(["nonexistent_xyz_42"]) == []

def test_collision_detection():
    factory = _make_factory()
    factory.load_externals(["echo"])
    assert factory.load_externals(["echo"]) == []

def test_plugin_summary():
    factory = _make_factory()
    factory.load_internals()
    factory.load_externals(["echo"])
    summary = factory.get_plugin_summary()
    assert summary["total_plugins"] == 3
    assert summary["total_tools"] >= 6
    assert "echo" in summary["plugins"]

def test_disabled_plugin():
    mcp = FastMCP("Test")
    config = {"plugins": {"echo": {"enabled": False}}}
    factory = Factory(mcp, config)
    assert factory.load_externals(["echo"]) == []
