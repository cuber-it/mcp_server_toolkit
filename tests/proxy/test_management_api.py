"""Tests for the Management API endpoints."""

import pytest
from fastapi.testclient import TestClient
from mcp.server.fastmcp import FastMCP

from mcp_server_proxy.proxy import PluginManager
from mcp_server_proxy.management import create_management_app


@pytest.fixture
def proxy():
    mcp = FastMCP("test-mgmt")
    return PluginManager(mcp, config={})


@pytest.fixture
def client(proxy):
    app = create_management_app(proxy)
    return TestClient(app)


class TestStatusEndpoint:
    def test_empty_status(self, client):
        resp = client.get("/proxy/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_plugins"] == 0
        assert data["total_tools"] == 0

    def test_status_with_plugin(self, client, proxy):
        proxy.load("echo")
        resp = client.get("/proxy/status")
        data = resp.json()
        assert data["total_plugins"] == 1
        assert "echo" in data["plugins"]


class TestPluginsEndpoint:
    def test_empty(self, client):
        resp = client.get("/proxy/plugins")
        assert resp.json() == {"plugins": []}

    def test_with_plugins(self, client, proxy):
        proxy.load("echo")
        resp = client.get("/proxy/plugins")
        assert "echo" in resp.json()["plugins"]


class TestLoadEndpoint:
    def test_load(self, client):
        resp = client.post("/proxy/load", json={"plugin": "echo"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"]
        assert "echo" in data["tools"]

    def test_load_unknown(self, client):
        resp = client.post("/proxy/load", json={"plugin": "nonexistent"})
        assert resp.status_code == 400
        assert not resp.json()["ok"]

    def test_load_duplicate(self, client, proxy):
        proxy.load("echo")
        resp = client.post("/proxy/load", json={"plugin": "echo"})
        assert resp.status_code == 400
        assert "already loaded" in resp.json()["error"]


class TestUnloadEndpoint:
    def test_unload(self, client, proxy):
        proxy.load("echo")
        resp = client.post("/proxy/unload", json={"plugin": "echo"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"]
        assert "echo" in data["removed"]

    def test_unload_not_loaded(self, client):
        resp = client.post("/proxy/unload", json={"plugin": "echo"})
        assert resp.status_code == 400


class TestReloadEndpoint:
    def test_reload(self, client, proxy):
        proxy.load("echo")
        resp = client.post("/proxy/reload", json={"plugin": "echo"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"]
        assert "echo" in data["tools"]

    def test_reload_not_loaded(self, client):
        resp = client.post("/proxy/reload", json={"plugin": "echo"})
        assert resp.status_code == 400
