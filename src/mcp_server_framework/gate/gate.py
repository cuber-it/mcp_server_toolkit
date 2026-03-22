"""Gate — Core: unlock, lock, check, protect, register_tools."""

from __future__ import annotations
import functools, logging
from typing import Any, Callable

from .backends import SecretBackend
from .config import GateConfig
from .state import GateState
from .totp import verify_totp

logger = logging.getLogger(__name__)

MAX_FAILURES = 5  # lockout after N consecutive failed unlock attempts


class GateLocked(Exception):
    def __init__(self, group: str):
        self.group = group
        super().__init__(
            f"Group '{group}' is locked. "
            f"Call gate_unlock(group='{group}', code='<totp>') first."
        )


class Gate:
    """Session-based TOTP gate for MCP tool groups.

    Args:
        config: dict from plugin config.yaml, key 'gate' (or full dict).

    Usage::

        gate = Gate(config.get("gate", {}))
        gate.register_tools(mcp)

        @mcp.tool()
        def shell_exec(command: str) -> str:
            gate.check_or_raise("shell")
            gate.touch("shell")
            ...

        # or decorator:
        @gate.protect("shell")
        @mcp.tool()
        def shell_exec(command: str) -> str: ...
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.cfg = GateConfig.from_dict(config)
        self.state = GateState()
        self._backend: SecretBackend = SecretBackend.from_config(config)
        self._failures: dict[str, int] = {}  # group → consecutive failures

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------

    def unlock(self, group: str, code: str) -> tuple[bool, str]:
        if group not in self.cfg.groups:
            return False, f"Unknown group '{group}'."

        if self._failures.get(group, 0) >= MAX_FAILURES:
            return False, f"Group '{group}' locked out after {MAX_FAILURES} failed attempts. Restart proxy to reset."

        try:
            secret = self._backend.get(self.cfg.groups[group].secret_ref)
        except RuntimeError as e:
            return False, str(e)

        if not verify_totp(secret, code):
            self._failures[group] = self._failures.get(group, 0) + 1
            remaining = MAX_FAILURES - self._failures[group]
            logger.warning("Gate: failed unlock for '%s' (%d attempts left)", group, remaining)
            return False, f"Invalid code. {remaining} attempt(s) left."

        self._failures[group] = 0
        timeout = self.cfg.groups[group].timeout
        self.state.unlock(group, timeout_seconds=timeout)
        logger.info("Gate: '%s' unlocked (timeout=%ds)", group, timeout)
        return True, f"Group '{group}' unlocked. Auto-lock after {timeout // 60}m inactivity."

    def lock(self, group: str | None = None) -> str:
        if group:
            self.state.lock(group)
            logger.info("Gate: '%s' locked", group)
            return f"Group '{group}' locked."
        self.state.lock_all()
        logger.info("Gate: all groups locked")
        return "All groups locked."

    def check_or_raise(self, group: str) -> None:
        if not self.state.is_unlocked(group):
            if self.cfg.audit.log_blocked:
                logger.warning("Gate: blocked call to locked group '%s'", group)
            raise GateLocked(group)

    def touch(self, group: str) -> None:
        self.state.touch(group)

    def status(self) -> dict:
        return self.state.status()

    # ------------------------------------------------------------------
    # Decorator
    # ------------------------------------------------------------------

    def protect(self, group: str) -> Callable:
        """Decorator: gate-protect a tool function."""
        def decorator(fn: Callable) -> Callable:
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                self.check_or_raise(group)
                self.touch(group)
                return fn(*args, **kwargs)
            return wrapper
        return decorator

    # ------------------------------------------------------------------
    # MCP tool registration
    # ------------------------------------------------------------------

    def register_tools(self, mcp: Any) -> None:
        """Register gate_unlock, gate_lock, gate_status as MCP tools."""
        gate = self

        @mcp.tool()
        def gate_unlock(group: str, code: str) -> str:
            """Unlock a tool group with TOTP code from your authenticator app.

            Args:
                group: Group name (e.g. 'shell', 'vault', 'db')
                code:  6-digit TOTP code
            """
            ok, msg = gate.unlock(group, code)
            return msg

        @mcp.tool()
        def gate_lock(group: str = "") -> str:
            """Manually lock a group, or all groups if group is empty."""
            return gate.lock(group or None)

        @mcp.tool()
        def gate_status() -> str:
            """Show lock/unlock status and remaining inactivity time per group."""
            s = gate.status()
            if not s:
                return "No groups configured."
            lines = []
            for grp, info in sorted(s.items()):
                if info["unlocked"]:
                    m, sec = divmod(info["remaining_seconds"], 60)
                    lines.append(f"✓ {grp}: UNLOCKED — auto-lock in {m}m {sec}s")
                else:
                    lines.append(f"✗ {grp}: LOCKED")
            return "\n".join(lines)
