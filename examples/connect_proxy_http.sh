#!/usr/bin/env bash
# Connect the interactive client to a running proxy on HTTP.
# Start the proxy first: ./run_proxy_http.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV="$ROOT/.venv/bin"

PORT="${1:-12200}"
URL="http://127.0.0.1:${PORT}/mcp"

echo "=== MCP Client → $URL ==="
echo ""

exec "$VENV/python" "$SCRIPT_DIR/mcp_client.py" -v http "$URL"
