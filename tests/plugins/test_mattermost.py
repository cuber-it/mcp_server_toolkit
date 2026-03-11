"""Tests for Mattermost adapter — client, tools, and proxy integration."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from mcp.server.fastmcp import FastMCP

from mcp_server_framework.plugins.loader import add_plugin_dir

# Make plugins/ loadable
_plugins_dir = Path(__file__).parent.parent.parent / "plugins"
add_plugin_dir(_plugins_dir)

# Add plugins dir to sys.path so imports work
if str(_plugins_dir) not in sys.path:
    sys.path.insert(0, str(_plugins_dir))

from mattermost.client import MattermostClient
from mattermost import tools


# --- Client Tests ---

class TestClient:
    def test_token_auth(self):
        client = MattermostClient(url="http://mm.test", token="test-token")
        assert client._authenticated
        headers = client._headers()
        assert headers["Authorization"] == "Bearer test-token"

    def test_lazy_login(self):
        client = MattermostClient(url="http://mm.test", username="user", password="pass")
        assert not client._authenticated

    def test_no_credentials_raises(self):
        client = MattermostClient(url="http://mm.test")
        with pytest.raises(ValueError, match="token or username"):
            client._ensure_auth()

    def test_login_flow(self):
        client = MattermostClient(url="http://mm.test", username="user", password="pass")
        mock_resp = MagicMock()
        mock_resp.headers = {"Token": "session-token-123"}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client._client, "post", return_value=mock_resp) as mock_post:
            client._ensure_auth()

        mock_post.assert_called_once()
        assert client._token == "session-token-123"
        assert client._authenticated


# --- Tool Tests (pure Python, mocked client) ---

class TestTools:
    @pytest.fixture
    def mock_client(self):
        return MagicMock(spec=MattermostClient)

    def test_send_message(self, mock_client):
        mock_client.post.return_value = {"id": "post123"}
        result = tools.send_message(mock_client, "ch1", "hello")
        assert "post123" in result
        mock_client.post.assert_called_once_with("/posts", data={"channel_id": "ch1", "message": "hello"})

    def test_get_channels(self, mock_client):
        mock_client.get.return_value = [
            {"id": "ch1", "display_name": "General", "type": "O"},
            {"id": "ch2", "display_name": "Dev", "type": "O"},
        ]
        result = tools.get_channels(mock_client, "team1")
        assert "General" in result
        assert "Dev" in result

    def test_get_channels_empty(self, mock_client):
        mock_client.get.return_value = []
        result = tools.get_channels(mock_client, "team1")
        assert result == "(no channels)"

    def test_get_posts(self, mock_client):
        mock_client.get.return_value = {
            "order": ["p1", "p2"],
            "posts": {
                "p1": {"user_id": "user1234", "message": "Hello"},
                "p2": {"user_id": "user5678", "message": "World"},
            },
        }
        result = tools.get_posts(mock_client, "ch1", limit=5)
        assert "Hello" in result
        assert "World" in result

    def test_search_posts(self, mock_client):
        mock_client.post.return_value = {
            "order": ["p1"],
            "posts": {"p1": {"message": "found it"}},
        }
        result = tools.search_posts(mock_client, "search term", "team1")
        assert "found it" in result

    def test_get_user(self, mock_client):
        mock_client.get.return_value = {
            "username": "jdoe",
            "email": "jdoe@example.com",
            "roles": "system_user",
        }
        result = tools.get_user(mock_client, "uid123")
        assert "jdoe" in result
        assert "jdoe@example.com" in result


# --- Proxy Integration ---

class TestProxyIntegration:
    def test_load_mattermost_via_proxy(self):
        from mcp_server_proxy.proxy import PluginManager

        mcp = FastMCP("test-mm")
        proxy = PluginManager(mcp, config={
            "plugins": {
                "mattermost": {"url": "http://mm.test", "token": "fake"},
            },
        })
        result = proxy.load("mattermost")
        assert result.ok
        assert "mm_send_message" in result.tools
        assert "mm_get_channels" in result.tools
        assert "mm_get_posts" in result.tools
        assert "mm_search_posts" in result.tools
        assert "mm_get_user" in result.tools
        assert len(result.tools) == 5

    def test_unload_mattermost(self):
        from mcp_server_proxy.proxy import PluginManager

        mcp = FastMCP("test-mm-unload")
        proxy = PluginManager(mcp, config={
            "plugins": {
                "mattermost": {"url": "http://mm.test", "token": "fake"},
            },
        })
        proxy.load("mattermost")
        result = proxy.unload("mattermost")
        assert result.ok
        assert "mm_send_message" in result.removed

    def test_load_without_url_fails(self):
        from mcp_server_proxy.proxy import PluginManager

        mcp = FastMCP("test-mm-nourl")
        proxy = PluginManager(mcp, config={})
        result = proxy.load("mattermost")
        assert not result.ok
        assert "url" in result.error.lower()
