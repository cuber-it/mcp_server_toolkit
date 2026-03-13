"""ToolLogger — Pluggable tool call logging.

Unified logging extracted from Factory (text/transcript) and Proxy (JSONL).
All loggers share the same interface: log_call(tool, params, result, success).
"""

from __future__ import annotations

import gzip
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_LOG_DIR = Path.home() / ".mcp_server"


class ToolLogger:
    """Base class for tool call loggers."""

    def log_call(self, tool: str, params: dict, result: str, success: bool) -> None:
        """Log a single tool call. Must not raise."""
        raise NotImplementedError

    def close(self) -> None:
        """Clean up resources."""
        pass


class JsonlToolLogger(ToolLogger):
    """Daily JSONL logger with gzip archival.

    Writes to ``{log_dir}/tool_calls.jsonl``. On day change, archives
    yesterday's file as ``YYYY-MM-DD.jsonl.gz``. Deletes files older
    than ``retention_days``.
    """

    def __init__(
        self,
        log_dir: Path | None = None,
        retention_days: int = 90,
    ):
        self.log_dir = log_dir or DEFAULT_LOG_DIR / "logs"
        self.retention_days = retention_days
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._current_date: date | None = None
        self._rotate_on_startup()

    @property
    def path(self) -> Path:
        return self.log_dir / "tool_calls.jsonl"

    def log_call(self, tool: str, params: dict, result: str, success: bool) -> None:
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
        if not self.path.exists():
            return
        try:
            file_date = date.fromtimestamp(self.path.stat().st_mtime)
            if file_date < date.today():
                self._rotate(file_date)
        except Exception:
            pass

    def _rotate(self, log_date: date) -> None:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return
        archive = self.log_dir / f"{log_date.isoformat()}.jsonl.gz"
        try:
            with open(self.path, "rb") as f_in, gzip.open(archive, "wb") as f_out:
                f_out.write(f_in.read())
            self.path.unlink()
            logger.info("Tool log archived: %s", archive.name)
        except Exception as e:
            logger.warning("Tool log rotation failed: %s", e)
        self._cleanup()

    def _cleanup(self) -> None:
        cutoff = date.today() - timedelta(days=self.retention_days)
        for f in self.log_dir.glob("*.jsonl.gz"):
            try:
                file_date = date.fromisoformat(f.stem.replace(".jsonl", ""))
                if file_date < cutoff:
                    f.unlink()
                    logger.info("Tool log expired: %s", f.name)
            except (ValueError, OSError):
                pass


class TextToolLogger(ToolLogger):
    """Simple text log with size-based rotation.

    Writes one-line entries to a log file. Rotates when file exceeds
    ``max_size`` bytes, keeping ``backup_count`` old files.
    """

    def __init__(
        self,
        log_file: Path | None = None,
        max_size: int = 5 * 1024 * 1024,
        backup_count: int = 3,
    ):
        self.log_file = log_file or DEFAULT_LOG_DIR / "tool_calls.log"
        self.max_size = max_size
        self.backup_count = backup_count
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log_call(self, tool: str, params: dict, result: str, success: bool) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "OK" if success else "FAIL"
        params_str = str(params)[:100] + ("..." if len(str(params)) > 100 else "")
        try:
            self._rotate_if_needed()
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {status} {tool} {params_str}\n")
        except Exception:
            pass

    def _rotate_if_needed(self) -> None:
        if not self.log_file.exists():
            return
        if self.log_file.stat().st_size < self.max_size:
            return
        for i in range(self.backup_count, 0, -1):
            old = self.log_file.with_suffix(f".log.{i}")
            if old.exists():
                if i == self.backup_count:
                    old.unlink()
                else:
                    old.rename(self.log_file.with_suffix(f".log.{i + 1}"))
        self.log_file.rename(self.log_file.with_suffix(".log.1"))


class TranscriptLogger(ToolLogger):
    """Markdown transcript logger.

    Writes tool calls as formatted Markdown sections. Useful for
    human-readable session transcripts.
    """

    def __init__(
        self,
        transcript_dir: Path | None = None,
        max_size: int = 10 * 1024 * 1024,
    ):
        self.transcript_dir = transcript_dir or DEFAULT_LOG_DIR / "transcripts"
        self.max_size = max_size
        self.transcript_dir.mkdir(parents=True, exist_ok=True)
        self.transcript_file: Path | None = None

    def start(self) -> str:
        """Start a new transcript. Returns file path."""
        filename = datetime.now().strftime("%Y-%m-%d-%H-%M-%S.md")
        self.transcript_file = self.transcript_dir / filename
        header = (
            f"# MCP Transcript\n"
            f"**Started:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n"
        )
        self.transcript_file.write_text(header, encoding="utf-8")
        return str(self.transcript_file)

    def stop(self) -> str:
        """Stop current transcript. Returns file path."""
        if not self.transcript_file:
            return "(no active transcript)"
        if self.transcript_file.exists():
            with open(self.transcript_file, "a", encoding="utf-8") as f:
                f.write(f"\n---\n**Ended:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        path = str(self.transcript_file)
        self.transcript_file = None
        return path

    @property
    def active(self) -> bool:
        return self.transcript_file is not None

    def log_call(self, tool: str, params: dict, result: str, success: bool) -> None:
        if not self.transcript_file:
            return
        if self.transcript_file.exists() and self.transcript_file.stat().st_size > self.max_size:
            self.stop()
            self.start()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "✓" if success else "✗"
        params_fmt = "\n".join(f"  {k}: {v}" for k, v in params.items()) if params else "  (none)"
        result_text = result[:50000]
        if len(result) > 50000:
            result_text += f"\n\n... (truncated, {len(result)} chars)"
        entry = (
            f"\n## [{timestamp}] {status} `{tool}`\n\n"
            f"**Parameters:**\n{params_fmt}\n\n"
            f"**Result:**\n```\n{result_text}\n```\n\n---\n"
        )
        try:
            with open(self.transcript_file, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass


class CompositeToolLogger(ToolLogger):
    """Combines multiple loggers. Calls all of them for each log_call."""

    def __init__(self, *loggers: ToolLogger):
        self.loggers = list(loggers)

    def log_call(self, tool: str, params: dict, result: str, success: bool) -> None:
        for lg in self.loggers:
            lg.log_call(tool, params, result, success)

    def close(self) -> None:
        for lg in self.loggers:
            lg.close()


def _truncate_dict(d: dict, max_len: int) -> dict:
    """Truncate string values in a dict."""
    return {
        k: (v[:max_len] + "..." if isinstance(v, str) and len(v) > max_len else v)
        for k, v in d.items()
    }
