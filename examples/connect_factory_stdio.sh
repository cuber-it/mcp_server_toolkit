#!/usr/bin/env bash
# Connect to any factory/proxy via stdio (spawns as subprocess).
# Usage: ./connect_factory_stdio.sh [config.yaml]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV="$ROOT/.venv/bin"
PLUGINS="$ROOT/plugins"

CONFIG="${1:-$SCRIPT_DIR/configs/factory_echo.yaml}"

echo "=== MCP Client → stdio (config: $CONFIG) ==="
echo ""

exec "$VENV/python" "$SCRIPT_DIR/mcp_client.py" -v stdio -- \
    "$VENV/mcp-factory" \
    --config "$CONFIG" \
    --plugin-dir "$PLUGINS"
