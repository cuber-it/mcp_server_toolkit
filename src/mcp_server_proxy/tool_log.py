"""Persistent tool call logging — daily JSONL files with gzip archival."""

from __future__ import annotations

import gzip
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_LOG_DIR = Path.home() / ".mcp_proxy" / "logs"
RETENTION_DAYS = 90


class ToolLog:
    """Daily JSONL logger for tool calls.

    Writes to ``{log_dir}/tool_calls.jsonl`` for the current day.
    On day change: renames yesterday's file to ``YYYY-MM-DD.jsonl.gz``
    and compresses it. Deletes files older than ``retention_days``.
    """

    def __init__(
        self,
        log_dir: Path = DEFAULT_LOG_DIR,
        retention_days: int = RETENTION_DAYS,
    ):
        self.log_dir = log_dir
        self.retention_days = retention_days
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._current_date: date | None = None
        self._rotate_on_startup()

    @property
    def path(self) -> Path:
        return self.log_dir / "tool_calls.jsonl"

    def log_call(self, tool: str, params: dict, result: str, success: bool) -> None:
        """Log a single tool call. Safe — never raises."""
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "tool": tool,
            "params": _truncate_dict(params, 500),
            "result": result[:2000],
            "ok": success,
        }
        try:
            today = date.today()
            if self._current_date and today != self._current_date:
                self._rotate(self._current_date)
            self._current_date = today
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _rotate_on_startup(self) -> None:
        """Archive leftover log from previous run if it's from a past day."""
        if not self.path.exists():
            return
        try:
            stat = self.path.stat()
            file_date = date.fromtimestamp(stat.st_mtime)
            if file_date < date.today():
                self._rotate(file_date)
        except Exception:
            pass

    def _rotate(self, log_date: date) -> None:
        """Compress day's log to YYYY-MM-DD.jsonl.gz and clean old files."""
        if not self.path.exists() or self.path.stat().st_size == 0:
            return
        archive = self.log_dir / f"{log_date.isoformat()}.jsonl.gz"
        try:
            with open(self.path, "rb") as f_in:
                with gzip.open(archive, "wb") as f_out:
                    f_out.write(f_in.read())
            self.path.unlink()
            logger.info("Tool log archived: %s", archive.name)
        except Exception as e:
            logger.warning("Tool log rotation failed: %s", e)
        self._cleanup()

    def _cleanup(self) -> None:
        """Delete archives older than retention_days."""
        cutoff = date.today() - timedelta(days=self.retention_days)
        for f in self.log_dir.glob("*.jsonl.gz"):
            try:
                file_date = date.fromisoformat(f.stem.replace(".jsonl", ""))
                if file_date < cutoff:
                    f.unlink()
                    logger.info("Tool log expired: %s", f.name)
            except (ValueError, OSError):
                pass


def _truncate_dict(d: dict, max_len: int) -> dict:
    """Truncate string values in a dict."""
    return {
        k: (v[:max_len] + "..." if isinstance(v, str) and len(v) > max_len else v)
        for k, v in d.items()
    }
