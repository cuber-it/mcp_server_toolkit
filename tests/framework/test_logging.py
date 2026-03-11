"""Tests for logging configuration."""

import json
import logging

from mcp_server_framework.logging import setup_logging, JSONFormatter


class TestJSONFormatter:
    def test_format_produces_valid_json(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello %s", args=("world",), exc_info=None,
        )
        line = formatter.format(record)
        data = json.loads(line)
        assert data["level"] == "INFO"
        assert data["msg"] == "hello world"
        assert data["logger"] == "test"
        assert "ts" in data

    def test_format_with_exception(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys
            record = logging.LogRecord(
                name="test", level=logging.ERROR, pathname="", lineno=0,
                msg="failed", args=(), exc_info=sys.exc_info(),
            )
        line = formatter.format(record)
        data = json.loads(line)
        assert data["error"] == "boom"


class TestSetupLogging:
    def test_text_format(self):
        setup_logging(level="DEBUG", json_format=False)
        root = logging.getLogger()
        assert root.level == logging.DEBUG
        assert len(root.handlers) == 1
        assert not isinstance(root.handlers[0].formatter, JSONFormatter)

    def test_json_format(self):
        setup_logging(level="WARNING", json_format=True)
        root = logging.getLogger()
        assert root.level == logging.WARNING
        assert isinstance(root.handlers[0].formatter, JSONFormatter)

    def test_no_duplicate_handlers(self):
        setup_logging()
        setup_logging()
        root = logging.getLogger()
        assert len(root.handlers) == 1
