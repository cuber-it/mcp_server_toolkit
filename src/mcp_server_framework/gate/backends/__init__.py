"""SecretBackend — Abstract base for secret retrieval.

Implementations:
  EnvBackend          — reads from environment variable (default, zero deps)
  FileBackend         — reads from a key=value file (chmod 600)
  VaultwardenBackend  — fetches from Vaultwarden API (optional, needs requests)
"""

from __future__ import annotations
from abc import ABC, abstractmethod


class SecretBackend(ABC):
    """Retrieve a TOTP secret by reference string."""

    @abstractmethod
    def get(self, ref: str) -> str:
        """Return the raw Base32 secret. Raise RuntimeError if unavailable."""
        ...

    @classmethod
    def from_config(cls, config: dict) -> "SecretBackend":
        """Factory: create backend from config dict.

        config keys:
          secret_backend: env | file | vaultwarden   (default: env)
          + backend-specific keys (see each backend's docstring)
        """
        backend = config.get("secret_backend", "env")

        if backend == "env":
            from .env import EnvBackend
            return EnvBackend()

        if backend == "file":
            from .file import FileBackend
            return FileBackend(config.get("secret_file", "~/.mcp_gate_secrets"))

        if backend == "vaultwarden":
            url = config.get("vaultwarden_url")
            token = config.get("vaultwarden_token")
            if not url or not token:
                raise ValueError(
                    "VaultwardenBackend requires 'vaultwarden_url' and 'vaultwarden_token' in config."
                )
            from .vaultwarden import VaultwardenBackend
            return VaultwardenBackend(
                url=url,
                token=token,
                cache_ttl=config.get("vaultwarden_cache_ttl", 3600),
            )

        raise ValueError(f"Unknown secret_backend: '{backend}'. Valid: env, file, vaultwarden")
