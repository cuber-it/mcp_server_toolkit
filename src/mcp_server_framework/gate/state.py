"""GateState — Thread-safe in-memory session state per group."""

from __future__ import annotations
import threading
import time
from dataclasses import dataclass


@dataclass
class GroupSession:
    unlocked_at: float = 0.0
    last_activity: float = 0.0
    timeout_seconds: int = 7200

    @property
    def is_unlocked(self) -> bool:
        return self.unlocked_at > 0 and (time.time() - self.last_activity) < self.timeout_seconds

    @property
    def remaining_seconds(self) -> int:
        if not self.is_unlocked:
            return 0
        return max(0, self.timeout_seconds - int(time.time() - self.last_activity))

    def unlock(self, timeout_seconds: int | None = None) -> None:
        now = time.time()
        self.unlocked_at = now
        self.last_activity = now
        if timeout_seconds is not None:
            self.timeout_seconds = timeout_seconds

    def lock(self) -> None:
        self.unlocked_at = 0.0

    def touch(self) -> None:
        self.last_activity = time.time()


class GateState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._groups: dict[str, GroupSession] = {}

    def _get(self, group: str) -> GroupSession:
        if group not in self._groups:
            self._groups[group] = GroupSession()
        return self._groups[group]

    def unlock(self, group: str, timeout_seconds: int | None = None) -> None:
        with self._lock:
            self._get(group).unlock(timeout_seconds)

    def lock(self, group: str) -> None:
        with self._lock:
            self._get(group).lock()

    def lock_all(self) -> None:
        with self._lock:
            for s in self._groups.values():
                s.lock()

    def is_unlocked(self, group: str) -> bool:
        with self._lock:
            return self._get(group).is_unlocked

    def touch(self, group: str) -> None:
        with self._lock:
            self._get(group).touch()

    def status(self) -> dict[str, dict]:
        with self._lock:
            return {
                g: {
                    "unlocked": s.is_unlocked,
                    "remaining_seconds": s.remaining_seconds,
                    "timeout_seconds": s.timeout_seconds,
                }
                for g, s in self._groups.items()
            }
