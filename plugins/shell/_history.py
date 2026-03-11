"""Tool call history tracking."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

# ── History ──────────────────────────────────────────────────────────

@dataclass
class HistoryEntry:
    seq: int
    timestamp: str
    tool: str
    args: str
    result: str


_history: list[HistoryEntry] = []
_session_id: str = uuid.uuid4().hex[:8]
_seq: int = 0


def record(tool: str, args: str, result: str) -> None:
    global _seq
    _seq += 1
    _history.append(HistoryEntry(
        seq=_seq,
        timestamp=datetime.now().strftime("%H:%M:%S"),
        tool=tool,
        args=args[:500],
        result=result[:5000],
    ))
    if len(_history) > 1000:
        _history.pop(0)


def history(count: int = 20, filter: str = "", full: bool = False) -> str:
    """Show tool call history."""
    if not _history:
        return "No history yet."
    entries = _history
    if filter:
        f = filter.lower()
        entries = [e for e in entries if f in e.tool or f in e.args.lower()]
    selected = entries[-count:]
    lines = [f"Session {_session_id} ({_seq} calls)\n"]
    for e in selected:
        lines.append(f"#{e.seq} [{e.timestamp}] {e.tool}({e.args})")
        preview = e.result if full else e.result[:200].replace("\n", " ")
        lines.append(f"  -> {preview}")
    return "\n".join(lines)
