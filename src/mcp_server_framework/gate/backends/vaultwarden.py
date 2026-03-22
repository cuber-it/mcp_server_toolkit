"""VaultwardenBackend — Fetch TOTP secrets from Vaultwarden API.

Optional backend. Requires: requests (pip install requests)

Secrets live in Vaultwarden as secure notes or login items.
secret_ref is the item name in Vaultwarden.

config.yaml::

    secret_backend: vaultwarden
    vaultwarden_url: https://v.uc-it.de
    vaultwarden_token: ${VW_TOKEN}   # or hardcode (not recommended)
    groups:
      shell:
        secret_ref: mcp-gate/shell   # Vaultwarden item name
"""

from __future__ import annotations
from . import SecretBackend


class VaultwardenBackend(SecretBackend):
    def __init__(self, url: str, token: str) -> None:
        try:
            import requests
            self._requests = requests
        except ImportError:
            raise RuntimeError(
                "VaultwardenBackend requires 'requests': pip install requests"
            )
        self._url = url.rstrip("/")
        self._token = token
        self._cache: dict[str, str] = {}

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def get(self, ref: str) -> str:
        if ref in self._cache:
            return self._cache[ref]

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
                # Secure note: value in notes field
                # Login item: value in login.password or custom fields
                secret = (
                    item.get("notes")
                    or (item.get("login") or {}).get("password")
                )
                if secret:
                    self._cache[ref] = secret.strip()
                    return self._cache[ref]

        raise RuntimeError(f"Vaultwarden: item '{ref}' not found or has no value.")
