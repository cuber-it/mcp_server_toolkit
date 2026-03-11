"""ToolTracker — Re-export from framework for backwards compatibility.

The Factory hooks into the tracker's logging via set_log_callback().
"""

from mcp_server_framework.plugins.tracker import ToolTracker, set_log_callback

__all__ = ["ToolTracker", "set_log_callback"]
