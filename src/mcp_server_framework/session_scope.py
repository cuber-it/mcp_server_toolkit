"""Per-session state scoping for MCP servers.

streamable-http serves many client sessions in one process. Tool code that
holds mutable state — a browser, an auth gate, counters — must key that state
by the calling MCP session, or the state leaks across clients (cross-session
auth bypass, shared browser tabs, ...).

SessionScope provides that keying: a factory-backed store keyed by the active
MCP ServerSession, with lazy creation, optional idle eviction and shutdown
cleanup. Outside a request (stdio, unit tests) all access falls back to a
single shared slot, so single-session servers behave exactly as before.
"""
from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, Generic, Optional, TypeVar

T = TypeVar("T")

# key used when there is no active request (stdio, tests): one shared slot
_NO_SESSION_KEY = 0


def current_session() -> Optional[object]:
    """Return the active MCP ServerSession, or None outside a request."""
    try:
        from mcp.server.lowlevel.server import request_ctx
        return request_ctx.get().session
    except Exception:
        return None


def current_session_key() -> int:
    """Stable per-session key (id of the ServerSession), or 0 outside a request."""
    session = current_session()
    return id(session) if session is not None else _NO_SESSION_KEY


class SessionScope(Generic[T]):
    """Factory-backed per-session value store.

    Args:
        factory:       called with no args to build a value for a new session.
        on_evict:      optional async callback run when a value is evicted
                       (idle timeout) or on close_all — e.g. browser cleanup.
        idle_timeout:  seconds of inactivity after which a session's value is
                       evicted. 0 disables the reaper (values live until
                       close_all). A strong ref to the session is kept while an
                       entry lives, so its id() cannot be reused by a new
                       session in the meantime.
        reap_interval: how often the reaper checks for idle entries.
    """

    def __init__(
        self,
        factory: Callable[[], T],
        *,
        on_evict: Optional[Callable[[T], Awaitable[None]]] = None,
        idle_timeout: float = 0.0,
        reap_interval: float = 60.0,
    ) -> None:
        self._factory = factory
        self._on_evict = on_evict
        self._idle_timeout = float(idle_timeout)
        self._reap_interval = float(reap_interval)
        # key -> {"value": T, "session": object|None, "last": float}
        self._entries: dict[int, dict] = {}
        self._reaper: Optional[asyncio.Task] = None

    def current(self) -> T:
        """Return the value for the active session, creating it lazily."""
        key = current_session_key()
        entry = self._entries.get(key)
        if entry is None:
            entry = {
                "value": self._factory(),
                # strong ref so the id() key cannot be reused while alive
                "session": current_session(),
                "last": time.monotonic(),
            }
            self._entries[key] = entry
            if self._idle_timeout > 0:
                self._ensure_reaper()
        else:
            entry["last"] = time.monotonic()
        return entry["value"]

    def active_count(self) -> int:
        """Number of live per-session values (for diagnostics/tests)."""
        return len(self._entries)

    def _ensure_reaper(self) -> None:
        if self._reaper is not None and not self._reaper.done():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._reaper = loop.create_task(self._reap_loop())

    async def _reap_loop(self) -> None:
        while True:
            await asyncio.sleep(self._reap_interval)
            await self.reap_once()

    async def reap_once(self) -> int:
        """Evict entries idle longer than idle_timeout. Returns count evicted."""
        if self._idle_timeout <= 0:
            return 0
        now = time.monotonic()
        stale = [k for k, e in self._entries.items()
                 if now - e["last"] > self._idle_timeout]
        for key in stale:
            entry = self._entries.pop(key, None)
            if entry is not None and self._on_evict is not None:
                try:
                    await self._on_evict(entry["value"])
                except Exception:
                    pass
        return len(stale)

    async def close_all(self) -> None:
        """Evict every session's value — for server shutdown."""
        entries = list(self._entries.values())
        self._entries.clear()
        if self._on_evict is None:
            return
        for entry in entries:
            try:
                await self._on_evict(entry["value"])
            except Exception:
                pass
