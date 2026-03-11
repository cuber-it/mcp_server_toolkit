"""Tests for ToolTracker — prefix, logging, pre-call validation."""

import pytest
from mcp.server.fastmcp import FastMCP

from mcp_server_framework.plugins.tracker import (
    ToolTracker,
    set_pre_call_validator,
    set_log_callback,
)


@pytest.fixture(autouse=True)
def cleanup():
    yield
    set_pre_call_validator(None)
    set_log_callback(None)


class TestPreCallValidator:
    def test_validator_rejects(self):
        mcp = FastMCP("test-validator")
        tracker = ToolTracker(mcp)

        @tracker.tool()
        def my_tool(x: str) -> str:
            return f"ok: {x}"

        set_pre_call_validator(lambda name, params: "blocked" if params.get("x") == "bad" else None)

        # Call through FastMCP's internal tool manager
        tool_mgr = mcp._tool_manager
        tool = tool_mgr._tools["my_tool"]
        # Invoke the wrapped function directly
        result = tool.fn(x="bad")
        assert "Rejected" in result

    def test_validator_allows(self):
        mcp = FastMCP("test-validator-ok")
        tracker = ToolTracker(mcp)

        @tracker.tool()
        def my_tool(x: str) -> str:
            return f"ok: {x}"

        set_pre_call_validator(lambda name, params: None)

        tool_mgr = mcp._tool_manager
        tool = tool_mgr._tools["my_tool"]
        result = tool.fn(x="good")
        assert result == "ok: good"

    def test_no_validator_passes(self):
        mcp = FastMCP("test-no-validator")
        tracker = ToolTracker(mcp)

        @tracker.tool()
        def my_tool(x: str) -> str:
            return f"ok: {x}"

        tool_mgr = mcp._tool_manager
        tool = tool_mgr._tools["my_tool"]
        result = tool.fn(x="anything")
        assert result == "ok: anything"


class TestLogCallback:
    def test_log_callback_called(self):
        mcp = FastMCP("test-log")
        tracker = ToolTracker(mcp)
        logs = []

        @tracker.tool()
        def logged_tool(x: str) -> str:
            return f"result: {x}"

        set_log_callback(lambda name, params, result, ok: logs.append((name, ok)))

        tool_mgr = mcp._tool_manager
        tool = tool_mgr._tools["logged_tool"]
        tool.fn(x="test")
        assert len(logs) == 1
        assert logs[0] == ("logged_tool", True)
