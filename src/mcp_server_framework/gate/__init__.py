"""mcp_gate — Session-based TOTP gate for MCP tool groups.

Pure stdlib. No mandatory dependencies.
Optional: requests (for VaultwardenBackend)

Quick start::

    from mcp_gate import Gate

    def register(mcp, config):
        gate = Gate(config.get("gate", {}))
        gate.register_tools(mcp)   # adds gate_unlock, gate_lock, gate_status

        @gate.protect("shell")
        @mcp.tool()
        def shell_exec(command: str) -> str: ...
"""

from .gate import Gate, GateLocked
from .config import GateConfig, GroupConfig, AuditConfig
from .state import GateState
from .totp import verify_totp, generate_secret
from .backends import SecretBackend

__all__ = [
    "Gate", "GateLocked",
    "GateConfig", "GroupConfig", "AuditConfig",
    "GateState",
    "SecretBackend",
    "verify_totp", "generate_secret",
]
