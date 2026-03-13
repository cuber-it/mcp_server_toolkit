#!/usr/bin/env bash
# Start Proxy with echo + greet, more plugins available at runtime.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV="$ROOT/.venv/bin"
PLUGINS="$ROOT/plugins"

echo "=== MCP Proxy — Full Setup (HTTP on :12200) ==="
echo "Autoload: echo, greet"
echo "Available: mcp-proxy load demo_full | ..."
echo ""
echo "Connect with:  ./examples/connect_proxy_http.sh"
echo ""

exec "$VENV/mcp-proxy" serve \
    --config "$SCRIPT_DIR/configs/proxy_full.yaml" \
    --plugin-dir "$PLUGINS"
