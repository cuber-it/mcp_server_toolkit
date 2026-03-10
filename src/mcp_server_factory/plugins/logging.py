"""Logging plugin — factory__log, factory__transcript."""

from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

LOG_DIR = Path.home() / ".mcp_factory"
DEFAULT_LOG_FILE = LOG_DIR / "factory.log"
TRANSCRIPT_DIR = LOG_DIR / "transcripts"
MAX_LOG_SIZE = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 3
MAX_TRANSCRIPT_SIZE = 10 * 1024 * 1024


class LogSettings:
    def __init__(self):
        self.log_enabled: bool = False
        self.log_file: Optional[Path] = None
        self.transcript_enabled: bool = False
        self.transcript_file: Optional[Path] = None

    def set_logging(self, enabled: bool) -> str:
        if enabled:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            self.log_file = DEFAULT_LOG_FILE
            self.log_enabled = True
            return f"Log ON → {self.log_file}"
        self.log_enabled = False
        self.log_file = None
        return "Log OFF"

    def start_transcript(self) -> str:
        TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        filename = now.strftime("%Y-%m-%d-%H-%M-%S.md")
        self.transcript_file = TRANSCRIPT_DIR / filename
        self.transcript_enabled = True
        header = f"# MCP Factory Transcript\n**Started:** {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n"
        self.transcript_file.write_text(header, encoding="utf-8")
        return f"Transcript ON → {self.transcript_file}"

    def stop_transcript(self) -> str:
        if not self.transcript_enabled:
            return "No active transcript"
        if self.transcript_file and self.transcript_file.exists():
            with open(self.transcript_file, "a", encoding="utf-8") as f:
                f.write(f"\n---\n**Ended:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        result = f"Transcript OFF (saved: {self.transcript_file})"
        self.transcript_enabled = False
        self.transcript_file = None
        return result

    def log_call(self, tool: str, params: dict, result: str, success: bool) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "OK" if success else "FAIL"
        if self.log_enabled and self.log_file:
            params_str = str(params)[:100] + ("..." if len(str(params)) > 100 else "")
            try:
                self._rotate_if_needed()
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(f"[{timestamp}] {status} {tool} {params_str}\n")
            except Exception:
                pass
        if self.transcript_enabled and self.transcript_file:
            self._write_transcript(timestamp, tool, params, result, success)

    def _rotate_if_needed(self) -> None:
        if not self.log_file or not self.log_file.exists():
            return
        if self.log_file.stat().st_size < MAX_LOG_SIZE:
            return
        for i in range(LOG_BACKUP_COUNT, 0, -1):
            old = self.log_file.with_suffix(f".log.{i}")
            if old.exists():
                if i == LOG_BACKUP_COUNT:
                    old.unlink()
                else:
                    old.rename(self.log_file.with_suffix(f".log.{i + 1}"))
        self.log_file.rename(self.log_file.with_suffix(".log.1"))

    def _write_transcript(self, timestamp, tool, params, result, success) -> None:
        if not self.transcript_file:
            return
        if self.transcript_file.exists() and self.transcript_file.stat().st_size > MAX_TRANSCRIPT_SIZE:
            self.stop_transcript()
            self.start_transcript()
        status_emoji = "✓" if success else "✗"
        params_fmt = "\n".join(f"  {k}: {v}" for k, v in params.items()) if params else "  (none)"
        result_text = result[:50000] + f"\n\n... (truncated, {len(result)} chars)" if len(result) > 50000 else result
        entry = f"\n## [{timestamp}] {status_emoji} `{tool}`\n\n**Parameters:**\n{params_fmt}\n\n**Result:**\n```\n{result_text}\n```\n\n---\n"
        try:
            with open(self.transcript_file, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass


log_settings = LogSettings()


def register(mcp, config: dict[str, Any]) -> None:
    @mcp.tool()
    def factory__log(mode: str = "status") -> str:
        """Control tool call logging. Args: mode: 'on', 'off', or 'status'"""
        if mode == "on":
            return log_settings.set_logging(True)
        elif mode == "off":
            return log_settings.set_logging(False)
        return f"Log {'ON → ' + str(log_settings.log_file) if log_settings.log_enabled else 'OFF'}"

    @mcp.tool()
    def factory__transcript(mode: str = "status") -> str:
        """Control full transcript recording. Args: mode: 'on', 'off', or 'status'"""
        if mode == "on":
            if log_settings.transcript_enabled:
                return f"Transcript already active: {log_settings.transcript_file}"
            return log_settings.start_transcript()
        elif mode == "off":
            return log_settings.stop_transcript()
        return f"Transcript {'ON → ' + str(log_settings.transcript_file) if log_settings.transcript_enabled else 'OFF'}"
