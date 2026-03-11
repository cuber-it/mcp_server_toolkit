"""Wekan REST client — pure Python, httpx only.

Handles authentication (username/password login) and provides
typed wrappers around the Wekan REST API.

Note: Wekan (Meteor) sometimes resets connections after POST/PUT.
All write operations handle RemoteProtocolError gracefully.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class WekanClient:
    """Wekan API client using httpx for all operations."""

    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        default_board: str | None = None,
        timeout: float = 10.0,
    ):
        self.base_url = url.rstrip("/")
        self._username = username
        self._password = password
        self.default_board = default_board
        self._timeout = timeout
        self._client = httpx.Client(timeout=timeout)
        self._token: str | None = None
        self._user_id: str | None = None

    def _ensure_auth(self) -> None:
        if self._token is not None:
            return
        resp = self._client.post(
            f"{self.base_url}/users/login",
            json={"username": self._username, "password": self._password},
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["token"]
        self._user_id = data["id"]

    def _headers(self) -> dict[str, str]:
        self._ensure_auth()
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def _bid(self, board_id: str | None) -> str:
        bid = board_id or self.default_board
        if not bid:
            raise ValueError("board_id required (no default configured)")
        return bid

    # --- Safe HTTP helpers (handle Meteor connection resets) ---

    def get(self, path: str, params: dict | None = None) -> Any:
        resp = self._client.get(
            f"{self.base_url}/api{path}", headers=self._headers(), params=params,
        )
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, data: dict | None = None) -> Any:
        try:
            resp = self._client.post(
                f"{self.base_url}/api{path}", headers=self._headers(), json=data,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.RemoteProtocolError:
            logger.warning("Connection reset after POST %s (Meteor quirk)", path)
            return {"status": "created_with_connection_reset"}

    def put(self, path: str, data: dict | None = None) -> Any:
        try:
            resp = self._client.put(
                f"{self.base_url}/api{path}", headers=self._headers(), json=data,
            )
            resp.raise_for_status()
            return resp.json() if resp.text.strip() else {"status": "updated"}
        except httpx.RemoteProtocolError:
            logger.warning("Connection reset after PUT %s (Meteor quirk)", path)
            return {"status": "updated_with_connection_reset"}

    def delete(self, path: str) -> Any:
        try:
            resp = self._client.delete(
                f"{self.base_url}/api{path}", headers=self._headers(),
            )
            resp.raise_for_status()
            return {"status": "deleted"}
        except httpx.RemoteProtocolError:
            return {"status": "deleted_with_connection_reset"}

    def close(self) -> None:
        self._client.close()
