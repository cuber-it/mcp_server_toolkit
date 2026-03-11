"""Logging configuration — human-readable or JSON output.

Usage:
    from mcp_server_framework.logging import setup_logging

    setup_logging(level="INFO", json_format=True)

Config key ``log_format``: ``"text"`` (default) or ``"json"``.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            entry["error"] = str(record.exc_info[1])
        return json.dumps(entry, ensure_ascii=False)


TEXT_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"


def setup_logging(
    level: str = "INFO",
    json_format: bool = False,
) -> None:
    """Configure root logger.

    Args:
        level: Log level name (DEBUG, INFO, WARNING, ERROR).
        json_format: If True, output JSON lines. Otherwise human-readable text.
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stderr)
    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(TEXT_FORMAT))

    root.addHandler(handler)
