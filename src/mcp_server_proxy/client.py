"""Remote command dispatch — talk to a running proxy via management API."""

from __future__ import annotations

import argparse
import os
import sys

import httpx


def mgmt_url(port: int, path: str) -> str:
    return f"http://127.0.0.1:{port}{path}"


def is_proxy_running(port: int) -> bool:
    """Check if a proxy management API is responding."""
    try:
        resp = httpx.get(mgmt_url(port, "/proxy/status"), timeout=1)
        return resp.status_code == 200
    except Exception:
        return False


def send_command(command: str, args: argparse.Namespace) -> None:
    """Send a command to the running proxy via management API."""
    port = args.mgmt_port
    token = getattr(args, "token", None) or os.environ.get("MCP_MGMT_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    try:
        if command == "status":
            _print_status(port, headers)
        else:
            _send_plugin_command(command, args.plugin, port, headers)
    except httpx.ConnectError:
        print(f"Cannot connect to management API on port {port}. Is the proxy running?", file=sys.stderr)
        sys.exit(1)


def _print_status(port: int, headers: dict) -> None:
    resp = httpx.get(mgmt_url(port, "/proxy/status"), headers=headers, timeout=5)
    if resp.status_code == 401:
        _auth_error()
    data = resp.json()
    print(f"Plugins: {data['total_plugins']}, Tools: {data['total_tools']}")
    for name, info in data.get("plugins", {}).items():
        tools = ", ".join(info["tools"][:5])
        if info["tool_count"] > 5:
            tools += f" (+{info['tool_count'] - 5} more)"
        print(f"  {name}: {tools}")


def _send_plugin_command(command: str, plugin: str, port: int, headers: dict) -> None:
    resp = httpx.post(
        mgmt_url(port, f"/proxy/{command}"),
        json={"plugin": plugin},
        headers=headers,
        timeout=10,
    )
    if resp.status_code == 401:
        _auth_error()
    data = resp.json()
    if data.get("ok"):
        tools = data.get("tools") or data.get("removed") or []
        print(f"{command.capitalize()} '{plugin}': {', '.join(tools)}")
    else:
        print(f"Error: {data.get('error', 'unknown')}", file=sys.stderr)
        sys.exit(1)


def _auth_error() -> None:
    print("Error: unauthorized — provide --token or set MCP_MGMT_TOKEN", file=sys.stderr)
    sys.exit(1)
