#!/usr/bin/env bash
# Create a new MCP plugin scaffold.
# Usage: ./scripts/new-plugin.sh <name> [plugin-dir]

set -e

NAME="${1:?Usage: $0 <plugin-name> [plugin-dir]}"
DIR="${2:-plugins}"
TARGET="$DIR/$NAME"

if [ -d "$TARGET" ]; then
    echo "Error: $TARGET already exists." >&2
    exit 1
fi

mkdir -p "$TARGET"

cat > "$TARGET/__init__.py" << 'PYEOF'
"""__NAME__ — MCP plugin.

This file wires your tool functions to the MCP server.
Keep it thin — all logic belongs in tools.py.

How it works:
  1. The proxy calls register(mcp, config) when loading your plugin
  2. @mcp.tool() makes a function available to the LLM
  3. The docstring becomes the tool description the LLM sees
  4. Parameter types and names become the tool's input schema
"""

from __future__ import annotations
from .tools import hello, add


def register(mcp, config: dict) -> None:
    """Register __NAME__ tools."""

    # Simple tool — one parameter, returns a string
    @mcp.tool()
    def __NAME___hello(who: str = "World") -> str:
        """Say hello. The LLM sees this docstring as tool description."""
        return hello(who)

    # Tool with multiple parameters and config access
    @mcp.tool()
    def __NAME___add(a: int, b: int) -> str:
        """Add two numbers. Parameters become the JSON schema for the LLM."""
        return add(a, b)

    # -- Add your tools here. Pattern:
    #
    # @mcp.tool()
    # def __NAME___my_tool(param: str, count: int = 10) -> str:
    #     """What this tool does — the LLM reads this to decide when to use it."""
    #     return my_function(param, count)
    #
    # Supported types: str, int, float, bool, list[str], ...
    # Always return str. The LLM reads the return value.
PYEOF

cat > "$TARGET/tools.py" << 'PYEOF'
"""__NAME__ tool logic — pure Python, no MCP dependency.

All your actual logic goes here. These are normal functions,
testable without MCP, importable from anywhere.

Rules of thumb:
  - Always return str (the LLM reads it)
  - On error, return "Error: ..." (don't raise)
  - Keep functions focused — one tool, one job
"""

from __future__ import annotations


def hello(who: str) -> str:
    """Minimal example."""
    return f"Hello from __NAME__, {who}!"


def add(a: int, b: int) -> str:
    """Example with multiple params."""
    return f"{a} + {b} = {a + b}"


# -- Add your functions here. Example patterns:
#
# def fetch_data(query: str, limit: int = 10) -> str:
#     """Fetch something, format as readable text."""
#     results = do_something(query, limit)
#     lines = [f"- {r['name']}: {r['value']}" for r in results]
#     return "\n".join(lines) or "No results."
#
# def write_something(path: str, content: str) -> str:
#     """Write and confirm."""
#     Path(path).write_text(content)
#     return f"Written: {path}"
PYEOF

# Replace placeholder with actual name
sed -i "s/__NAME__/$NAME/g" "$TARGET/__init__.py" "$TARGET/tools.py"

echo "Created $TARGET/"
echo "  __init__.py    register() + MCP wiring"
echo "  tools.py       pure logic, edit this"
echo ""
echo "Next: edit $TARGET/tools.py, then restart proxy."
