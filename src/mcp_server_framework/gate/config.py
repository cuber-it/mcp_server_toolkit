"""GateConfig — Configuration model.

Loaded from config dict (passed by proxy to register()).

Minimal config.yaml example (env backend)::

    gate:
      secret_backend: env
      groups:
        shell:
          timeout: 7200
          secret_ref: MCP_GATE_SECRET_SHELL

Full config.yaml example (vaultwarden backend)::

    gate:
      secret_backend: vaultwarden
      vaultwarden_url: https://v.uc-it.de
      vaultwarden_token: ${VW_TOKEN}
      audit:
        enabled: true
        log_blocked: true
      groups:
        shell:
          timeout: 7200
          secret_ref: mcp-gate/shell
          tools: [shell_exec, shell_file_read, shell_file_write]
        vault:
          timeout: 3600
          secret_ref: mcp-gate/vault
          tools: [vault_read, vault_write]
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GroupConfig:
    secret_ref: str = ""
    timeout: int = 7200
    tools: list[str] = field(default_factory=list)


@dataclass
class AuditConfig:
    enabled: bool = True
    log_blocked: bool = True


@dataclass
class GateConfig:
    groups: dict[str, GroupConfig] = field(default_factory=dict)
    audit: AuditConfig = field(default_factory=AuditConfig)
    # backend config passed as-is to SecretBackend.from_config()
    backend_config: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GateConfig":
        groups = {
            name: GroupConfig(
                secret_ref=cfg.get("secret_ref", name),
                timeout=cfg.get("timeout", 7200),
                tools=cfg.get("tools", []),
            )
            for name, cfg in data.get("groups", {}).items()
        }
        audit_raw = data.get("audit", {})
        audit = AuditConfig(
            enabled=audit_raw.get("enabled", True),
            log_blocked=audit_raw.get("log_blocked", True),
        )
        return cls(groups=groups, audit=audit, backend_config=data)

    def group_for_tool(self, tool_name: str) -> str | None:
        for name, cfg in self.groups.items():
            if tool_name in cfg.tools:
                return name
        return None
