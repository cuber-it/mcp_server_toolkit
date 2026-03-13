"""Persistent tool call logging — delegates to JsonlToolLogger from framework.

Kept as thin wrapper for backwards compatibility (serve.py imports ToolLog).
"""

from __future__ import annotations

from pathlib import Path

from mcp_server_framework.plugins import JsonlToolLogger

DEFAULT_LOG_DIR = Path.home() / ".mcp_proxy" / "logs"


class ToolLog(JsonlToolLogger):
    """Proxy-specific JSONL logger with proxy defaults."""

    def __init__(
        self,
        log_dir: Path = DEFAULT_LOG_DIR,
        retention_days: int = 90,
    ):
        super().__init__(log_dir=log_dir, retention_days=retention_days)
