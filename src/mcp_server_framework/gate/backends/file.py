"""FileBackend — Read TOTP secrets from a key=value file.

The file lives outside the repo. Security via filesystem permissions (chmod 600).
File is re-read on every get() call — secret rotation takes effect immediately.

File format (~/.mcp_gate_secrets)::

    # comment
    shell=JBSWY3DPEHPK3PXP
    vault=JBSWY3DPEHPK3PXQ

config.yaml::

    secret_backend: file
    secret_file: ~/.mcp_gate_secrets   # default
    groups:
      shell:
        secret_ref: shell              # key in the file
"""

from __future__ import annotations
import logging
import stat
from pathlib import Path
from . import SecretBackend

logger = logging.getLogger(__name__)


class FileBackend(SecretBackend):
    def __init__(self, path: str = "~/.mcp_gate_secrets") -> None:
        self._path = Path(path).expanduser()
        self._warn_permissions()

    def _warn_permissions(self) -> None:
        if not self._path.exists():
            return
        mode = self._path.stat().st_mode
        if mode & (stat.S_IRGRP | stat.S_IROTH):
            logger.warning(
                "Gate: secret file %s is readable by group/others. "
                "Run: chmod 600 %s",
                self._path, self._path,
            )

    def _load(self) -> dict[str, str]:
        if not self._path.exists():
            raise RuntimeError(
                f"Gate secret file not found: {self._path}\n"
                f"Create it with: touch {self._path} && chmod 600 {self._path}"
            )
        secrets: dict[str, str] = {}
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
            raise RuntimeError(
                f"Gate: secret '{ref}' not found in {self._path}"
            )
        return secrets[ref]
