"""Mattermost tool functions — pure Python, no MCP dependency.

Each function takes a MattermostClient and returns a formatted string.
These are the building blocks that register() wraps as MCP tools.
"""

from __future__ import annotations

import json
from typing import Any

from .client import MattermostClient


def send_message(client: MattermostClient, channel_id: str, message: str) -> str:
    """Send a message to a channel. Returns post ID."""
    result = client.post("/posts", data={"channel_id": channel_id, "message": message})
    return f"Message sent (post_id: {result['id']})"


def get_channels(client: MattermostClient, team_id: str) -> str:
    """List public channels for a team."""
    channels = client.get(f"/teams/{team_id}/channels")
    lines = []
    for ch in channels:
        name = ch.get("display_name") or ch.get("name", "?")
        lines.append(f"- {name} (id: {ch['id']}, type: {ch.get('type', '?')})")
    return "\n".join(lines) or "(no channels)"


def get_posts(client: MattermostClient, channel_id: str, limit: int = 10) -> str:
    """Get recent posts from a channel."""
    data = client.get(f"/channels/{channel_id}/posts", params={"per_page": limit})
    posts = []
    for post_id in data.get("order", []):
        post = data["posts"][post_id]
        user = post.get("user_id", "?")[:8]
        msg = post.get("message", "")[:200]
        posts.append(f"[{user}] {msg}")
    return "\n".join(posts) or "(no posts)"


def search_posts(client: MattermostClient, query: str, team_id: str) -> str:
    """Search posts across a team."""
    data = client.post("/posts/search", data={"terms": query, "team_id": team_id})
    posts = []
    for post_id in data.get("order", []):
        post = data["posts"][post_id]
        msg = post.get("message", "")[:200]
        posts.append(f"- {msg}")
    return "\n".join(posts[:10]) or "(no results)"


def get_user(client: MattermostClient, user_id: str) -> str:
    """Get user info by ID."""
    user = client.get(f"/users/{user_id}")
    return f"{user.get('username', '?')} ({user.get('email', '?')}), roles: {user.get('roles', '?')}"
