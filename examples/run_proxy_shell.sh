#!/usr/bin/env bash
# Start Proxy with shell plugin on HTTP.
# Provides filesystem, search, and shell execution tools.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV="$ROOT/.venv/bin"
PLUGINS="$ROOT/plugins"

echo "=== MCP Proxy + Shell (HTTP on :12200) ==="
echo "Tools: file_read, file_write, grep, glob, shell_exec, cd, ..."
echo ""
echo "Connect with:  ./examples/connect_proxy_http.sh"
echo ""

exec "$VENV/mcp-proxy" serve \
    --config "$SCRIPT_DIR/configs/proxy_shell.yaml" \
    --plugin-dir "$PLUGINS"
