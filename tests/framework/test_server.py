"""Tests for server factory."""

from mcp.server.fastmcp import FastMCP
from mcp_server_framework.server import create_server


def test_create_server_minimal():
    """Server with minimal config."""
    config = {
        "server_name": "Test",
        "instructions": "Test server",
        "version": "1.0.0",
    }
    mcp = create_server(config)
    assert isinstance(mcp, FastMCP)
    assert mcp.name == "Test"


def test_create_server_defaults():
    """Server with empty config uses defaults."""
    mcp = create_server({})
    assert isinstance(mcp, FastMCP)
    assert mcp.name == "MCP Server"


def test_create_server_from_load_config():
    """Integration: load_config() → create_server()."""
    from mcp_server_framework.config import load_config
    config = load_config()
    mcp = create_server(config)
    assert isinstance(mcp, FastMCP)
