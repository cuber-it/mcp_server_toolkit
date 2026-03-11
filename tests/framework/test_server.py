"""Tests for server factory — including OAuth integration."""

from mcp.server.fastmcp import FastMCP
from mcp_server_framework.server import create_server, _build_oauth


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


# --- OAuth ---

def test_build_oauth_disabled():
    """Returns (None, None) when OAuth disabled."""
    verifier, auth = _build_oauth({"oauth_enabled": False})
    assert verifier is None
    assert auth is None


def test_build_oauth_urls_missing_stdio():
    """No warning for stdio when URLs missing."""
    verifier, auth = _build_oauth({
        "oauth_enabled": True,
        "oauth_server_url": None,
        "oauth_public_url": None,
        "transport": "stdio",
    })
    assert verifier is None
    assert auth is None


def test_build_oauth_urls_missing_http(caplog):
    """Warning for HTTP when OAuth enabled but URLs missing."""
    verifier, auth = _build_oauth({
        "oauth_enabled": True,
        "oauth_server_url": None,
        "oauth_public_url": None,
        "transport": "http",
    })
    assert verifier is None
    assert auth is None
    assert "WITHOUT authentication" in caplog.text


def test_build_oauth_fully_configured():
    """OAuth with all URLs returns verifier and auth settings."""
    verifier, auth = _build_oauth({
        "oauth_enabled": True,
        "oauth_server_url": "https://auth.example.com",
        "oauth_public_url": "https://mcp.example.com",
    })
    assert verifier is not None
    assert auth is not None


def test_create_server_oauth_disabled():
    """Server without OAuth when explicitly disabled."""
    config = {
        "server_name": "NoAuth",
        "instructions": "",
        "host": "127.0.0.1",
        "port": 12345,
        "oauth_enabled": False,
    }
    mcp = create_server(config)
    assert mcp.name == "NoAuth"


def test_create_server_oauth_enabled_but_not_configured():
    """Server starts without auth when OAuth URLs missing."""
    config = {
        "server_name": "Unconfigured",
        "instructions": "",
        "host": "127.0.0.1",
        "port": 12345,
        "oauth_enabled": True,
        "oauth_server_url": None,
        "oauth_public_url": None,
        "transport": "http",
    }
    mcp = create_server(config)
    assert mcp.name == "Unconfigured"
