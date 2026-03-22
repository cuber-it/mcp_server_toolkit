"""VaultwardenBackend — Fetch TOTP secrets from Vaultwarden API.

Optional backend. Requires: requests (pip install requests)

Secrets live in Vaultwarden as secure notes or login items.
secret_ref is the item name in Vaultwarden.

The secret is cached in memory with a configurable TTL (default: 3600s).
To pick up a rotated secret immediately, restart the proxy or call invalidate().

config.yaml::

    secret_backend: vaultwarden
    vaultwarden_url: https://v.uc-it.de
    vaultwarden_token: ${VW_TOKEN}   # resolved from env at startup
    vaultwarden_cache_ttl: 3600      # optional, seconds (0 = no cache)
    groups:
      shell:
        secret_ref: mcp-gate/shell   # Vaultwarden item name (secure note)
"""

from __future__ import annotations
import logging
import time
from . import SecretBackend

logger = logging.getLogger(__name__)


class VaultwardenBackend(SecretBackend):
    def __init__(self, url: str, token: str, cache_ttl: int = 3600) -> None:
        try:
            import requests
            self._requests = requests
        except ImportError:
            raise RuntimeError(
                "VaultwardenBackend requires 'requests': pip install requests"
            )
        self._url = url.rstrip("/")
        self._token = token
        self._cache_ttl = cache_ttl
        self._cache: dict[str, tuple[str, float]] = {}  # ref → (secret, fetched_at)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def _is_cached(self, ref: str) -> bool:
        if ref not in self._cache:
            return False
        if self._cache_ttl == 0:
            return False
        _, fetched_at = self._cache[ref]
        return (time.time() - fetched_at) < self._cache_ttl

    def get(self, ref: str) -> str:
        if self._is_cached(ref):
            return self._cache[ref][0]

        resp = self._requests.get(
            f"{self._url}/api/list/object/items",
            headers=self._headers(),
            params={"search": ref},
            timeout=10,
        )
        resp.raise_for_status()

        items = resp.json().get("data", {}).get("data", [])
        for item in items:
            if item.get("name") == ref:
                secret = (
                    item.get("notes")
                    or (item.get("login") or {}).get("password")
                )
                if secret:
                    self._cache[ref] = (secret.strip(), time.time())
                    logger.debug("Gate: secret '%s' fetched from Vaultwarden", ref)
                    return self._cache[ref][0]

        raise RuntimeError(f"Vaultwarden: item '{ref}' not found or has no value.")

    def invalidate(self, ref: str | None = None) -> None:
        """Invalidate cache. ref=None clears all entries."""
        if ref is None:
            self._cache.clear()
        else:
            self._cache.pop(ref, None)
