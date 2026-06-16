"""Gate — Core: unlock, lock, check, protect, register_tools."""

from __future__ import annotations
import functools
import logging
from typing import Any, Callable

from .backends import SecretBackend
from .config import GateConfig
from .state import GateState
from .totp import verify_totp
from ..session_scope import SessionScope

logger = logging.getLogger(__name__)

MAX_FAILURES = 5  # lockout after N consecutive failed unlock attempts


class GateLocked(Exception):
    """Raised when a gated tool is called while the group is locked."""
    def __init__(self, group: str):
        self.group = group
        super().__init__(
            f"Group '{group}' is locked. "
            f"Call gate_unlock(group='{group}', code='<totp>') first."
        )


class Gate:
    """Session-based TOTP gate for MCP tool groups.

    All groups start locked on every proxy restart. A valid TOTP code unlocks
    a group for a configurable inactivity timeout (default: 2h). Any tool call
    within the group resets the timer. After MAX_FAILURES consecutive wrong
    codes, the group is locked out until proxy restart.

    Args:
        config: dict from plugin config.yaml under the 'gate' key.

    Minimal usage::

        gate = Gate(config.get("gate", {}))
        gate.register_tools(mcp)   # adds gate_unlock, gate_lock, gate_status

        @mcp.tool()
        @gate.protect("shell")     # NOTE: protect must be INNER, mcp.tool OUTER
        def shell_exec(command: str) -> str:
            return subprocess.check_output(command, shell=True, text=True)

    If gate is disabled in config (enabled: false), protect() is a no-op and
    register_tools() skips registration. Tools work without authentication.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.cfg = GateConfig.from_dict(config)
        self.enabled = self.cfg.enabled
        # per-session gate state: each MCP session gets its own GateState, so an
        # unlock by one client never leaks to another over streamable-http.
        idle = float(config.get("session_idle_timeout", 10800))
        self._scope: SessionScope[GateState] = SessionScope(
            GateState, idle_timeout=idle,
        )
        self._backend: SecretBackend | None = (
            SecretBackend.from_config(config) if self.enabled else None
        )

    def _state(self) -> GateState:
        """GateState for the active MCP session (lazy, per session)."""
        return self._scope.current()

    @property
    def state(self) -> GateState:
        """GateState of the active MCP session. Kept for compatibility; in an
        HTTP context this resolves to the calling client's own state."""
        return self._state()

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------

    def unlock(self, group: str, code: str) -> tuple[bool, str]:
        """Verify TOTP and unlock a group. Returns (success, message)."""
        if not self.enabled:
            return True, "Gate is disabled."

        if group not in self.cfg.groups:
            return False, f"Unknown group '{group}'."

        st = self._state()
        if st.failure_count(group) >= MAX_FAILURES:
            return False, (
                f"Group '{group}' locked out after {MAX_FAILURES} failed attempts. "
                f"Restart proxy to reset."
            )

        assert self._backend is not None  # guaranteed: enabled=True implies backend is set
        try:
            secret = self._backend.get(self.cfg.groups[group].secret_ref)
        except RuntimeError as e:
            return False, str(e)

        if not verify_totp(secret, code):
            count = st.record_failure(group)
            remaining = MAX_FAILURES - count
            logger.warning("Gate: failed unlock for '%s' (%d attempts left)", group, remaining)
            return False, f"Invalid code. {remaining} attempt(s) left."

        st.reset_failure(group)
        timeout = self.cfg.groups[group].timeout
        st.unlock(group, timeout_seconds=timeout)
        logger.info("Gate: '%s' unlocked (timeout=%ds)", group, timeout)
        return True, f"Group '{group}' unlocked. Auto-lock after {timeout // 60}m inactivity."

    def lock(self, group: str | None = None) -> str:
        """Manually lock a group, or all groups if group is None."""
        st = self._state()
        if group:
            st.lock(group)
            logger.info("Gate: '%s' locked", group)
            return f"Group '{group}' locked."
        st.lock_all()
        logger.info("Gate: all groups locked")
        return "All groups locked."

    def check_or_raise(self, group: str) -> None:
        """Raise GateLocked if group is locked. No-op if gate is disabled."""
        if not self.enabled:
            return
        if not self._state().is_unlocked(group):
            if self.cfg.audit.log_blocked:
                logger.warning("Gate: blocked call to locked group '%s'", group)
            raise GateLocked(group)

    def touch(self, group: str) -> None:
        """Reset inactivity timer for group."""
        if self.enabled:
            self._state().touch(group)

    def status(self) -> dict:
        """Return status dict for all known groups."""
        if not self.enabled:
            return {}
        return self._state().status()

    # ------------------------------------------------------------------
    # Decorator
    # ------------------------------------------------------------------

    def protect(self, group: str) -> Callable:
        """Decorator factory: gate-protect a function.

        IMPORTANT — decorator order with FastMCP::

            @mcp.tool()          # outer: registers the tool
            @gate.protect("shell")  # inner: wraps the actual function
            def shell_exec(command: str) -> str:
                ...

        This ensures FastMCP sees the original function signature for
        schema generation, while gate protection runs on every call.
        """
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
        """Register gate_unlock, gate_lock, gate_status as MCP tools.

        No-op if gate is disabled (enabled: false in config).
        """
        if not self.enabled:
            logger.debug("Gate: disabled, skipping tool registration")
            return

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
            """Manually lock a group, or all groups if group is empty.

            Args:
                group: Group name, or empty to lock all groups (kill switch).
            """
            return gate.lock(group or None)

        @mcp.tool()
        def gate_status() -> str:
            """Show lock/unlock status and remaining inactivity time per group."""
            s = gate.status()
            if not s:
                return "No active groups."
            lines = []
            for grp, info in sorted(s.items()):
                if info["unlocked"]:
                    m, sec = divmod(info["remaining_seconds"], 60)
                    lines.append(f"✓ {grp}: UNLOCKED — auto-lock in {m}m {sec}s")
                else:
                    lines.append(f"✗ {grp}: LOCKED")
            return "\n".join(lines)
