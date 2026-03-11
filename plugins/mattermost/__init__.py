"""Mattermost adapter — MCP plugin for Mattermost REST API.

Config keys:
    url: Mattermost server URL (required)
    token: Bearer token (or use username+password)
    username: Login username
    password: Login password
"""

from __future__ import annotations

from .client import MattermostClient
from . import tools


def register(mcp, config: dict) -> None:
    """Register Mattermost tools as MCP tools."""
    url = config.get("url")
    if not url:
        raise ValueError("Mattermost plugin requires 'url' in config")

    client = MattermostClient(
        url=url,
        token=config.get("token"),
        username=config.get("username"),
        password=config.get("password"),
    )

    @mcp.tool()
    def mm_send_message(channel_id: str, message: str) -> str:
        """Send a message to a Mattermost channel."""
        return tools.send_message(client, channel_id, message)

    @mcp.tool()
    def mm_get_channels(team_id: str) -> str:
        """List public channels for a Mattermost team."""
        return tools.get_channels(client, team_id)

    @mcp.tool()
    def mm_get_posts(channel_id: str, limit: int = 10) -> str:
        """Get recent posts from a Mattermost channel."""
        return tools.get_posts(client, channel_id, limit)

    @mcp.tool()
    def mm_search_posts(query: str, team_id: str) -> str:
        """Search posts across a Mattermost team."""
        return tools.search_posts(client, query, team_id)

    @mcp.tool()
    def mm_get_user(user_id: str) -> str:
        """Get Mattermost user info by ID."""
        return tools.get_user(client, user_id)
