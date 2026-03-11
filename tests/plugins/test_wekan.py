"""Tests for Wekan adapter — client and proxy integration."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from mcp.server.fastmcp import FastMCP

from mcp_server_framework.plugins.loader import add_plugin_dir

_plugins_dir = Path(__file__).parent.parent.parent / "plugins"
add_plugin_dir(_plugins_dir)

if str(_plugins_dir) not in sys.path:
    sys.path.insert(0, str(_plugins_dir))

from wekan.client import WekanClient
from wekan import tools


class TestClient:
    def test_needs_auth(self):
        client = WekanClient(url="http://wekan.test", username="u", password="p")
        assert client._token is None

    def test_bid_default(self):
        client = WekanClient(url="http://wekan.test", username="u", password="p", default_board="b1")
        assert client._bid(None) == "b1"

    def test_bid_no_default_raises(self):
        client = WekanClient(url="http://wekan.test", username="u", password="p")
        with pytest.raises(ValueError, match="board_id required"):
            client._bid(None)

    def test_bid_explicit(self):
        client = WekanClient(url="http://wekan.test", username="u", password="p", default_board="b1")
        assert client._bid("b2") == "b2"


class TestTools:
    @pytest.fixture
    def mock_client(self):
        client = MagicMock(spec=WekanClient)
        client._bid.side_effect = lambda bid: bid or "default_board"
        client._user_id = "user123"
        return client

    def test_list_boards(self, mock_client):
        mock_client.get.return_value = [
            {"_id": "b1", "title": "Board 1"},
            {"_id": "b2", "title": "Board 2", "archived": True},
        ]
        result = tools.list_boards(mock_client)
        assert "Board 1" in result
        assert "Board 2" not in result  # archived

    def test_list_lists(self, mock_client):
        mock_client.get.return_value = [{"_id": "l1", "title": "Backlog"}]
        result = tools.list_lists(mock_client, "b1")
        assert "Backlog" in result

    def test_board_summary(self, mock_client):
        mock_client.get.side_effect = [
            [{"_id": "l1", "title": "Todo"}],  # lists
            [{"_id": "c1", "title": "Card 1"}],  # cards in l1
        ]
        result = tools.board_summary(mock_client, "b1")
        assert "Card 1" in result
        assert "total_cards" in result


class TestProxyIntegration:
    def test_load_wekan_via_proxy(self):
        from mcp_server_proxy.proxy import PluginManager

        mcp = FastMCP("test-wekan")
        proxy = PluginManager(mcp, config={
            "plugins": {
                "wekan": {"url": "http://wekan.test", "username": "u", "password": "p"},
            },
        })
        result = proxy.load("wekan")
        assert result.ok
        assert "wekan_list_boards" in result.tools
        assert "wekan_create_card" in result.tools
        assert len(result.tools) >= 15

    def test_load_without_url_fails(self):
        from mcp_server_proxy.proxy import PluginManager

        mcp = FastMCP("test-wekan-nourl")
        proxy = PluginManager(mcp, config={})
        result = proxy.load("wekan")
        assert not result.ok
        assert "url" in result.error.lower()
