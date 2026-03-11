#!/usr/bin/env bash
# Start Proxy with echo plugin on HTTP.
# Connect with: ./connect_proxy_http.sh (in another terminal)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV="$ROOT/.venv/bin"
PLUGINS="$ROOT/plugins"

echo "=== MCP Proxy + Echo (HTTP on :12200) ==="
echo "Management API on :12299"
echo ""
echo "Connect with:  ./examples/connect_proxy_http.sh"
echo "Management:    mcp-proxy status"
echo "               mcp-proxy load greet"
echo "               mcp-proxy unload echo"
echo ""

exec "$VENV/mcp-proxy" serve \
    --config "$SCRIPT_DIR/configs/proxy_echo.yaml" \
    --plugin-dir "$PLUGINS"
