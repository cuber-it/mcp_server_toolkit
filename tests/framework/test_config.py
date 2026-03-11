"""Tests for configuration."""

import os

import pytest

from mcp_server_framework.config import load_config


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Remove MCP_* ENV variables for clean tests."""
    for key in list(os.environ):
        if key.startswith("MCP_"):
            monkeypatch.delenv(key)


def test_defaults():
    """Config without file returns defaults."""
    config = load_config()
    assert config["server_name"] == "MCP Server"
    assert config["log_level"] == "INFO"
    assert config["transport"] == "stdio"
    assert config["port"] == 12201
    assert config["health_port"] == 12202  # port + 1
    assert config["oauth_enabled"] is True  # enabled by default
    assert config["oauth_server_url"] is None
    assert config["oauth_public_url"] is None
    assert config["tools"] == []


def test_env_override(monkeypatch):
    """Environment variables override defaults."""
    monkeypatch.setenv("MCP_SERVER_NAME", "Test Server")
    monkeypatch.setenv("MCP_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("MCP_PORT", "12301")
    monkeypatch.setenv("MCP_OAUTH_ENABLED", "false")
    monkeypatch.setenv("MCP_OAUTH_SERVER_URL", "https://auth.example.com")
    monkeypatch.setenv("MCP_PUBLIC_URL", "https://mcp.example.com")
    config = load_config()
    assert config["server_name"] == "Test Server"
    assert config["log_level"] == "DEBUG"
    assert config["port"] == 12301
    assert config["health_port"] == 12302  # port + 1
    assert config["oauth_enabled"] is False
    assert config["oauth_server_url"] == "https://auth.example.com"
    assert config["oauth_public_url"] == "https://mcp.example.com"


def test_env_invalid_port(monkeypatch):
    """Invalid port value is ignored."""
    monkeypatch.setenv("MCP_PORT", "not_a_number")
    config = load_config()
    assert config["port"] == 12201  # default stays


def test_yaml_config(tmp_path):
    """YAML file is loaded."""
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(
        "server_name: YAML Server\n"
        "port: 12301\n"
        "service_type: shell\n"
    )
    config = load_config(yaml_file)
    assert config["server_name"] == "YAML Server"
    assert config["port"] == 12301
    assert config["service_type"] == "shell"


def test_env_overrides_yaml(tmp_path, monkeypatch):
    """ENV wins over YAML."""
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text("server_name: YAML Server\n")
    monkeypatch.setenv("MCP_SERVER_NAME", "ENV Server")
    config = load_config(yaml_file)
    assert config["server_name"] == "ENV Server"
