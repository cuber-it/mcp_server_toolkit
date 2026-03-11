"""Mattermost REST client — pure Python, no MCP dependency.

Handles authentication (token or username/password) and provides
typed wrappers around the Mattermost REST API v4.
"""

from __future__ import annotations

from typing import Any

import httpx


class MattermostClient:
    """Lightweight Mattermost API client using httpx."""

    def __init__(
        self,
        url: str,
        token: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 10.0,
    ):
        self.base_url = url.rstrip("/")
        self._token = token
        self._username = username
        self._password = password
        self._timeout = timeout
        self._client = httpx.Client(timeout=timeout)
        self._authenticated = token is not None

    def _ensure_auth(self) -> None:
        """Lazy login — only called on first request if no token."""
        if self._authenticated:
            return
        if not self._username or not self._password:
            raise ValueError("Either token or username+password required")
        resp = self._client.post(
            f"{self.base_url}/api/v4/users/login",
            json={"login_id": self._username, "password": self._password},
        )
        resp.raise_for_status()
        self._token = resp.headers["Token"]
        self._authenticated = True

    def _headers(self) -> dict[str, str]:
        self._ensure_auth()
        return {"Authorization": f"Bearer {self._token}"}

    def get(self, path: str, params: dict | None = None) -> Any:
        resp = self._client.get(
            f"{self.base_url}/api/v4{path}",
            headers=self._headers(),
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, data: dict | None = None) -> Any:
        resp = self._client.post(
            f"{self.base_url}/api/v4{path}",
            headers=self._headers(),
            json=data,
        )
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()
