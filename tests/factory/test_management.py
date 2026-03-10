"""Tests for management plugin."""
from mcp.server.fastmcp import FastMCP
from mcp_server_factory.factory import Factory


def _make_loaded_factory() -> Factory:
    mcp = FastMCP("Test Factory")
    config = {"server_name": "Test Factory", "transport": "stdio"}
    factory = Factory(mcp, config)
    config["_factory"] = factory
    factory.load_internals()
    factory.load_externals(["echo"])
    return factory

def test_status_tool_registered():
    factory = _make_loaded_factory()
    assert "factory__status" in factory.plugins["factory_management"].tools

def test_list_tool_registered():
    factory = _make_loaded_factory()
    assert "factory__list" in factory.plugins["factory_management"].tools

def test_management_tool_count():
    factory = _make_loaded_factory()
    assert len(factory.plugins["factory_management"].tools) == 2
