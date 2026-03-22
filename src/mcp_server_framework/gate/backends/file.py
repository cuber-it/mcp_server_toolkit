"""FileBackend — Read TOTP secrets from a simple key=value file.

The file lives outside the repo, chmod 600.
No encryption dependency — security via filesystem permissions.
For stronger protection: encrypt with age/gpg and decrypt at startup.

File format (~/.mcp_gate_secrets)::

    shell=JBSWY3DPEHPK3PXP
    vault=JBSWY3DPEHPK3PXQ

config.yaml::

    secret_backend: file
    secret_file: ~/.mcp_gate_secrets
    groups:
      shell:
        secret_ref: shell     # key in the file
"""

from __future__ import annotations
import os
from pathlib import Path
from . import SecretBackend


class FileBackend(SecretBackend):
    def __init__(self, path: str = "~/.mcp_gate_secrets") -> None:
        self._path = Path(path).expanduser()

    def _load(self) -> dict[str, str]:
        if not self._path.exists():
            raise RuntimeError(f"Secret file not found: {self._path}")
        secrets = {}
        for line in self._path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            secrets[key.strip()] = value.strip()
        return secrets

    def get(self, ref: str) -> str:
        secrets = self._load()
        if ref not in secrets:
            raise RuntimeError(f"Secret '{ref}' not found in {self._path}")
        return secrets[ref]
