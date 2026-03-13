"""Logging plugin — factory__log, factory__transcript.

Uses TextToolLogger and TranscriptLogger from framework.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp_server_framework.plugins import TextToolLogger, TranscriptLogger, CompositeToolLogger

LOG_DIR = Path.home() / ".mcp_factory"


class LogSettings:
    """Manages text log + transcript via framework loggers."""

    def __init__(self):
        self._text: TextToolLogger | None = None
        self._transcript: TranscriptLogger = TranscriptLogger(transcript_dir=LOG_DIR / "transcripts")
        self._composite: CompositeToolLogger = CompositeToolLogger()

    @property
    def log_enabled(self) -> bool:
        return self._text is not None

    @property
    def log_file(self) -> Path | None:
        return self._text.log_file if self._text else None

    @property
    def transcript_enabled(self) -> bool:
        return self._transcript.active

    @property
    def transcript_file(self) -> Path | None:
        return self._transcript.transcript_file

    def set_logging(self, enabled: bool) -> str:
        if enabled:
            self._text = TextToolLogger(log_file=LOG_DIR / "factory.log")
            self._rebuild_composite()
            return f"Log ON → {self._text.log_file}"
        self._text = None
        self._rebuild_composite()
        return "Log OFF"

    def start_transcript(self) -> str:
        path = self._transcript.start()
        self._rebuild_composite()
        return f"Transcript ON → {path}"

    def stop_transcript(self) -> str:
        path = self._transcript.stop()
        self._rebuild_composite()
        return f"Transcript OFF (saved: {path})"

    def log_call(self, tool: str, params: dict, result: str, success: bool) -> None:
        self._composite.log_call(tool, params, result, success)

    def _rebuild_composite(self) -> None:
        loggers = []
        if self._text:
            loggers.append(self._text)
        if self._transcript.active:
            loggers.append(self._transcript)
        self._composite = CompositeToolLogger(*loggers)


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
