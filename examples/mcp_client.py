#!/usr/bin/env python3
"""mcp-client — Interactive MCP test client for debugging and exploration.

Connects to any MCP server via stdio or HTTP and provides an interactive
REPL to list tools, call them, and observe the raw protocol exchange.

Usage:
    # Connect via stdio (spawn server process)
    python mcp_client.py stdio -- python -m mcp_server_factory --config factory.yaml

    # Connect via HTTP (streamable-http)
    python mcp_client.py http http://localhost:12200/mcp

    # With verbose protocol logging
    python mcp_client.py -v stdio -- mcp-proxy --autoload echo

REPL Commands:
    tools           List all available tools
    call <name>     Call a tool (prompts for JSON arguments)
    resources       List available resources
    prompts         List available prompts
    info            Show server info and capabilities
    raw <json>      Send raw JSON-RPC message
    help            Show this help
    quit / exit     Disconnect and exit
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import TextContent


# --- Logging / Verbose Output ---

class ProtocolLogger:
    """Logs protocol messages when verbose mode is on."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._start = time.monotonic()

    def log(self, direction: str, msg: str) -> None:
        if not self.verbose:
            return
        elapsed = time.monotonic() - self._start
        prefix = ">>>" if direction == "send" else "<<<"
        print(f"\033[90m[{elapsed:7.3f}s] {prefix} {msg}\033[0m", file=sys.stderr)

    def info(self, msg: str) -> None:
        if self.verbose:
            elapsed = time.monotonic() - self._start
            print(f"\033[90m[{elapsed:7.3f}s] --- {msg}\033[0m", file=sys.stderr)


# --- REPL ---

async def repl(session: ClientSession, proto: ProtocolLogger) -> None:
    """Interactive REPL loop."""
    print("\nConnected. Type 'help' for commands, 'quit' to exit.\n")

    while True:
        try:
            line = await asyncio.get_event_loop().run_in_executor(
                None, lambda: input("mcp> ")
            )
        except (EOFError, KeyboardInterrupt):
            print()
            break

        line = line.strip()
        if not line:
            continue

        parts = line.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        try:
            if cmd in ("quit", "exit", "q"):
                break
            elif cmd == "help":
                _print_help()
            elif cmd == "tools":
                await _cmd_tools(session, proto)
            elif cmd == "call":
                await _cmd_call(session, arg, proto)
            elif cmd == "resources":
                await _cmd_resources(session, proto)
            elif cmd == "prompts":
                await _cmd_prompts(session, proto)
            elif cmd == "info":
                await _cmd_info(session)
            else:
                print(f"Unknown command: {cmd}. Type 'help' for available commands.")
        except Exception as e:
            print(f"Error: {e}")


def _print_help() -> None:
    print("""
Commands:
  tools              List all available tools with descriptions
  call <name>        Call a tool (prompts for JSON arguments)
  resources          List available resources
  prompts            List available prompts
  info               Show server info and capabilities
  help               Show this help
  quit / exit        Disconnect and exit
""")


async def _cmd_tools(session: ClientSession, proto: ProtocolLogger) -> None:
    proto.log("send", "tools/list")
    result = await session.list_tools()
    proto.log("recv", f"{len(result.tools)} tools")

    if not result.tools:
        print("(no tools available)")
        return

    for tool in sorted(result.tools, key=lambda t: t.name):
        desc = (tool.description or "").split("\n")[0][:80]
        print(f"  {tool.name:30s}  {desc}")

        if proto.verbose and tool.inputSchema:
            props = tool.inputSchema.get("properties", {})
            required = set(tool.inputSchema.get("required", []))
            for pname, pinfo in props.items():
                req = "*" if pname in required else " "
                ptype = pinfo.get("type", "?")
                pdesc = pinfo.get("description", "")[:50]
                print(f"    {req} {pname}: {ptype}  {pdesc}")

    print(f"\n  Total: {len(result.tools)} tools")


async def _cmd_call(session: ClientSession, tool_name: str, proto: ProtocolLogger) -> None:
    if not tool_name:
        print("Usage: call <tool_name>")
        return

    # Get tool schema for argument prompting
    tools_result = await session.list_tools()
    tool = next((t for t in tools_result.tools if t.name == tool_name), None)

    if tool is None:
        print(f"Tool '{tool_name}' not found. Use 'tools' to list available tools.")
        return

    # Prompt for arguments
    arguments = {}
    schema = tool.inputSchema or {}
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    if properties:
        print(f"Arguments for '{tool_name}':")
        for pname, pinfo in properties.items():
            ptype = pinfo.get("type", "string")
            req = "(required)" if pname in required else "(optional)"
            default = pinfo.get("default")
            prompt_str = f"  {pname} [{ptype}] {req}"
            if default is not None:
                prompt_str += f" default={default}"
            prompt_str += ": "

            value = await asyncio.get_event_loop().run_in_executor(
                None, lambda p=prompt_str: input(p)
            )

            if value == "" and pname not in required:
                if default is not None:
                    arguments[pname] = default
                continue

            # Type coercion
            if ptype == "integer":
                arguments[pname] = int(value)
            elif ptype == "number":
                arguments[pname] = float(value)
            elif ptype == "boolean":
                arguments[pname] = value.lower() in ("true", "1", "yes")
            elif ptype == "object" or ptype == "array":
                arguments[pname] = json.loads(value)
            else:
                arguments[pname] = value

    # Call
    proto.log("send", f"tools/call {tool_name} {json.dumps(arguments)}")
    t0 = time.monotonic()
    result = await session.call_tool(tool_name, arguments)
    elapsed = time.monotonic() - t0
    proto.log("recv", f"result ({elapsed:.3f}s, isError={result.isError})")

    # Display result
    if result.isError:
        print(f"ERROR ({elapsed:.3f}s):")
    else:
        print(f"Result ({elapsed:.3f}s):")

    for content in result.content:
        if isinstance(content, TextContent):
            print(content.text)
        else:
            print(f"[{content.type}]: {content}")


async def _cmd_resources(session: ClientSession, proto: ProtocolLogger) -> None:
    proto.log("send", "resources/list")
    result = await session.list_resources()
    proto.log("recv", f"{len(result.resources)} resources")

    if not result.resources:
        print("(no resources available)")
        return

    for res in result.resources:
        print(f"  {res.uri}  {res.name or ''}")


async def _cmd_prompts(session: ClientSession, proto: ProtocolLogger) -> None:
    proto.log("send", "prompts/list")
    result = await session.list_prompts()
    proto.log("recv", f"{len(result.prompts)} prompts")

    if not result.prompts:
        print("(no prompts available)")
        return

    for prompt in result.prompts:
        desc = (prompt.description or "")[:60]
        print(f"  {prompt.name:30s}  {desc}")


async def _cmd_info(session: ClientSession) -> None:
    print(f"  Server: {session.server_info}")
    print(f"  Capabilities: {session.server_capabilities}")


# --- Transport Connection ---

async def connect_stdio(args: argparse.Namespace, proto: ProtocolLogger) -> None:
    """Connect via stdio transport (spawn subprocess)."""
    command = args.server_cmd[0]
    cmd_args = args.server_cmd[1:]

    proto.info(f"Connecting via stdio: {command} {' '.join(cmd_args)}")

    params = StdioServerParameters(command=command, args=cmd_args)

    async with stdio_client(params) as (read_stream, write_stream):
        session = ClientSession(read_stream, write_stream)
        proto.log("send", "initialize")
        init = await session.initialize()
        proto.log("recv", f"initialized: {init.serverInfo}")
        print(f"Server: {init.serverInfo.name} v{init.serverInfo.version}")
        await repl(session, proto)


async def connect_http(args: argparse.Namespace, proto: ProtocolLogger) -> None:
    """Connect via streamable HTTP transport."""
    url = args.url

    proto.info(f"Connecting via HTTP: {url}")

    async with streamable_http_client(url) as (read_stream, write_stream, get_session_id):
        session = ClientSession(read_stream, write_stream)
        proto.log("send", "initialize")
        init = await session.initialize()
        session_id = get_session_id()
        proto.log("recv", f"initialized: {init.serverInfo}, session={session_id}")
        print(f"Server: {init.serverInfo.name} v{init.serverInfo.version}")
        if session_id:
            print(f"Session: {session_id}")
        await repl(session, proto)


# --- Main ---

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mcp-client",
        description="Interactive MCP test client for debugging and exploration.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s stdio -- python -m mcp_server_factory --config config.yaml
  %(prog)s stdio -- mcp-proxy --autoload echo
  %(prog)s http http://localhost:12200/mcp
  %(prog)s -v stdio -- mcp-factory
""",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Show protocol messages")
    sub = parser.add_subparsers(dest="transport", required=True)

    # stdio
    stdio_p = sub.add_parser("stdio", help="Connect via stdio (spawn server process)")
    stdio_p.add_argument("server_cmd", nargs="+", metavar="CMD", help="Server command (after --)")

    # http
    http_p = sub.add_parser("http", help="Connect via streamable HTTP")
    http_p.add_argument("url", help="Server URL (e.g. http://localhost:12200/mcp)")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    proto = ProtocolLogger(verbose=args.verbose)

    print("MCP Client — Interactive Test & Debug Tool")
    print("=" * 45)

    try:
        if args.transport == "stdio":
            asyncio.run(connect_stdio(args, proto))
        elif args.transport == "http":
            asyncio.run(connect_http(args, proto))
    except KeyboardInterrupt:
        print("\nDisconnected.")


if __name__ == "__main__":
    main()
