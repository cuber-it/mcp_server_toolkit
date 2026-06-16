"""Tests for the SessionScope per-session primitive."""
import asyncio

import mcp_server_framework.session_scope as ss
from mcp_server_framework import SessionScope


def _run(coro):
    """Run a coroutine on a throwaway loop, then leave a fresh open loop in
    place so later tests using the (deprecated) get_event_loop() keep working."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(asyncio.new_event_loop())


def test_single_shared_slot_without_request(monkeypatch):
    # No active request → one shared slot.
    monkeypatch.setattr(ss, "current_session", lambda: None)
    scope = SessionScope(lambda: object())
    a = scope.current()
    b = scope.current()
    assert a is b
    assert scope.active_count() == 1


def test_distinct_value_per_session(monkeypatch):
    session_a, session_b = object(), object()
    scope = SessionScope(lambda: object())

    monkeypatch.setattr(ss, "current_session", lambda: session_a)
    va = scope.current()
    monkeypatch.setattr(ss, "current_session", lambda: session_b)
    vb = scope.current()
    monkeypatch.setattr(ss, "current_session", lambda: session_a)
    va_again = scope.current()

    assert va is va_again        # same session → same value
    assert va is not vb          # different session → different value
    assert scope.active_count() == 2


def test_reap_evicts_idle_and_runs_on_evict(monkeypatch):
    evicted = []

    async def on_evict(value):
        evicted.append(value)

    monkeypatch.setattr(ss, "current_session", lambda: object())
    scope = SessionScope(lambda: object(), on_evict=on_evict, idle_timeout=0.01)
    value = scope.current()
    # force the entry into the past
    for entry in scope._entries.values():
        entry["last"] -= 1.0

    evicted_count = _run(scope.reap_once())

    assert evicted_count == 1
    assert evicted == [value]
    assert scope.active_count() == 0


def test_close_all_evicts_everything(monkeypatch):
    evicted = []

    async def on_evict(value):
        evicted.append(value)

    sessions = [object(), object()]
    scope = SessionScope(lambda: object(), on_evict=on_evict)
    monkeypatch.setattr(ss, "current_session", lambda: sessions[0])
    a = scope.current()
    monkeypatch.setattr(ss, "current_session", lambda: sessions[1])
    b = scope.current()
    assert scope.active_count() == 2

    _run(scope.close_all())

    assert {id(x) for x in evicted} == {id(a), id(b)}
    assert scope.active_count() == 0
