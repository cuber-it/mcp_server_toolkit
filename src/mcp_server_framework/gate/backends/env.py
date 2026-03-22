"""EnvBackend — Read TOTP secret from environment variable.

Default backend. Zero dependencies. Works everywhere.

config.yaml::

    secret_backend: env
    groups:
      shell:
        secret_ref: MCP_GATE_SECRET_SHELL   # name of env var
"""

from __future__ import annotations
import os
from . import SecretBackend


class EnvBackend(SecretBackend):
    def get(self, ref: str) -> str:
        value = os.environ.get(ref)
        if not value:
            raise RuntimeError(f"Environment variable '{ref}' not set.")
        return value.strip()
