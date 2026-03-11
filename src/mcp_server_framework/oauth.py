"""OAuth 2.0 Token Introspection (RFC 7662) for MCP servers.

Verifies bearer tokens against an OAuth introspection endpoint.
Implements the MCP SDK TokenVerifier protocol.

Features:
    - Persistent connection pool (reuses connections across requests)
    - SSRF protection (only HTTPS and localhost allowed)
    - RFC 8707 resource validation (optional)
    - Configurable timeouts
    - No external dependencies beyond httpx (already in MCP SDK)
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.shared.auth_utils import check_resource_allowed, resource_url_from_server_url

logger = logging.getLogger(__name__)

_SAFE_SCHEMES = ("https://", "http://localhost", "http://127.0.0.1")


class IntrospectionTokenVerifier(TokenVerifier):
    """Token verifier using OAuth 2.0 Token Introspection (RFC 7662).

    Maintains a persistent httpx.AsyncClient for connection pooling.
    Call close() or use as async context manager for clean shutdown.

    Args:
        introspection_endpoint: URL of the introspection endpoint.
        server_url: Public URL of this MCP server (for resource matching).
        validate_resource: Enable RFC 8707 audience/resource validation.
        timeout: Request timeout in seconds (default: 10).
        max_connections: Connection pool size (default: 10).
    """

    def __init__(
        self,
        introspection_endpoint: str,
        server_url: str,
        validate_resource: bool = False,
        timeout: float = 10.0,
        max_connections: int = 10,
    ) -> None:
        self.introspection_endpoint = introspection_endpoint
        self.server_url = server_url
        self.validate_resource = validate_resource
        self.resource_url = resource_url_from_server_url(server_url)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=5.0),
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_connections,
            ),
            verify=True,
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify token via introspection endpoint.

        Returns AccessToken on success, None on any failure.
        Never raises — all errors are logged and result in rejection.
        """
        if not self._is_safe_endpoint():
            return None

        try:
            response = await self._client.post(
                self.introspection_endpoint,
                data={"token": token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except httpx.TimeoutException:
            logger.warning("Token introspection timed out: %s", self.introspection_endpoint)
            return None
        except httpx.HTTPError as exc:
            logger.warning("Token introspection failed: %s", exc)
            return None

        if response.status_code != 200:
            logger.debug("Token introspection returned status %d", response.status_code)
            return None

        data: dict[str, Any] = response.json()

        if not data.get("active", False):
            return None

        if self.validate_resource and not self._check_audience(data):
            logger.warning(
                "Token resource validation failed — expected: %s", self.resource_url,
            )
            return None

        aud = data.get("aud")
        if isinstance(aud, list):
            aud = aud[0] if aud else None

        return AccessToken(
            token=token,
            client_id=data.get("client_id", "unknown"),
            scopes=data.get("scope", "").split() if data.get("scope") else [],
            expires_at=data.get("exp"),
            resource=aud,
        )

    def _is_safe_endpoint(self) -> bool:
        """SSRF protection: only allow HTTPS and localhost."""
        if not any(self.introspection_endpoint.startswith(s) for s in _SAFE_SCHEMES):
            logger.warning(
                "Rejecting introspection endpoint with unsafe scheme: %s",
                self.introspection_endpoint,
            )
            return False
        return True

    def _check_audience(self, token_data: dict[str, Any]) -> bool:
        """RFC 8707 audience validation."""
        aud = token_data.get("aud")
        if aud is None:
            return False
        audiences = aud if isinstance(aud, list) else [aud]
        return any(
            check_resource_allowed(
                requested_resource=self.resource_url,
                configured_resource=a,
            )
            for a in audiences
        )

    async def close(self) -> None:
        """Close the HTTP connection pool."""
        await self._client.aclose()

    async def __aenter__(self) -> IntrospectionTokenVerifier:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
