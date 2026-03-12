"""Demo plugin — shows tools, resources and prompts registration.

This plugin demonstrates the full MCP plugin interface supported by the
Framework, Factory and Proxy. All three capability types (tools, resources,
prompts) are tracked by ToolTracker for collision detection and management.
"""

import datetime


def register(mcp, config: dict) -> None:
    # --- Tool ---
    @mcp.tool()
    def demo_time() -> str:
        """Return the current server time."""
        return datetime.datetime.now().isoformat()

    # --- Resource ---
    @mcp.resource("demo://status")
    def demo_status() -> str:
        """Server status as a resource."""
        return "ok"

    # --- Prompt ---
    @mcp.prompt()
    def demo_summarize(text: str) -> str:
        """Summarize the given text."""
        return f"Please summarize the following text concisely:\n\n{text}"
