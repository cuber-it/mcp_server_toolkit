"""GateConfig — Configuration model for mcp_server_framework.gate.

Loaded from the 'gate' key of a plugin's config.yaml.

Minimal config (env backend, shell group)::

    gate:
      enabled: true
      secret_backend: env
      groups:
        shell:
          timeout: 7200
          secret_ref: MCP_GATE_SECRET_SHELL

Full config (vaultwarden backend, multiple groups)::

    gate:
      enabled: true
      secret_backend: vaultwarden
      vaultwarden_url: https://v.uc-it.de
      vaultwarden_token: ${VW_TOKEN}
      vaultwarden_cache_ttl: 3600
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

Disabled (tools work without authentication)::

    gate:
      enabled: false
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GroupConfig:
    secret_ref: str = ""       # reference passed to SecretBackend.get()
    timeout: int = 7200        # inactivity timeout in seconds
    tools: list[str] = field(default_factory=list)  # informational only


@dataclass
class AuditConfig:
    enabled: bool = True
    log_blocked: bool = True   # log WARNING for every blocked tool call


@dataclass
class GateConfig:
    enabled: bool = True
    groups: dict[str, GroupConfig] = field(default_factory=dict)
    audit: AuditConfig = field(default_factory=AuditConfig)
    backend_config: dict = field(default_factory=dict)  # passed as-is to SecretBackend

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GateConfig":
        enabled = data.get("enabled", True)
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
        return cls(enabled=enabled, groups=groups, audit=audit, backend_config=data)

    def group_for_tool(self, tool_name: str) -> str | None:
        """Return group name for a tool, or None if ungated."""
        for name, cfg in self.groups.items():
            if tool_name in cfg.tools:
                return name
        return None
