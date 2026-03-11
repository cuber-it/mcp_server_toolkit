#!/usr/bin/env bash
# Start Factory with echo plugin and connect the interactive client via stdio.
# Everything in one terminal — client spawns the server as subprocess.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV="$ROOT/.venv/bin"
PLUGINS="$ROOT/plugins"

echo "=== MCP Factory + Echo (stdio) ==="
echo "Client spawns server, connects via stdio."
echo ""

exec "$VENV/python" "$SCRIPT_DIR/mcp_client.py" -v stdio -- \
    "$VENV/mcp-factory" \
    --config "$SCRIPT_DIR/configs/factory_echo.yaml" \
    --plugin-dir "$PLUGINS"
