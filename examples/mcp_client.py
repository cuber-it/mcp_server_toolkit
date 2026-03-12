#!/usr/bin/env python3
"""mcp-client — Spec-conformant interactive MCP test client.

Connects to any MCP server via stdio or HTTP and provides an interactive
REPL to list tools, call them, and observe the raw protocol exchange.

Implements the MCP spec correctly:
- Handles notifications/tools/list_changed by re-fetching tools/list
- Handles notifications/resources/list_changed
- Handles notifications/prompts/list_changed
- Maintains persistent session (stateful Streamable HTTP)
- Logs all protocol events in verbose mode

Usage:
    # Connect via stdio (spawn server process)
    python mcp_client.py stdio -- python -m mcp_server_factory --config factory.yaml

    # Connect via HTTP (streamable-http)
    python mcp_client.py http http://localhost:12200/mcp

    # With verbose protocol logging
    python mcp_client.py -v http http://localhost:12201/mcp

REPL Commands:
    tools           List all available tools
    call <name>     Call a tool (prompts for JSON arguments)
    resources       List available resources
    prompts         List available prompts
    info            Show server info and capabilities
    help            Show this help
    quit / exit     Disconnect and exit
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

import anyio

from mcp import ClientSession, types
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.session import RequestResponder


# --- Protocol Logger ---

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
        elapsed = time.monotonic() - self._start
        if self.verbose:
            print(f"\033[90m[{elapsed:7.3f}s] --- {msg}\033[0m", file=sys.stderr)

    def event(self, msg: str) -> None:
        """Always-visible event (e.g. tool list changed)."""
        elapsed = time.monotonic() - self._start
        print(f"\033[33m[{elapsed:7.3f}s] <<< {msg}\033[0m", file=sys.stderr)


# --- Notification Handler ---

class NotificationHandler:
    """Handles server notifications per MCP spec.

    On tools/list_changed: re-fetches tools/list and updates cached tool count.
    On resources/list_changed: re-fetches resources/list.
    On prompts/list_changed: re-fetches prompts/list.
    """

    def __init__(self, session: ClientSession, proto: ProtocolLogger):
        self._session = session
        self._proto = proto
        self.tool_count = 0
        self.tools_changed_count = 0
        self.server_info: Any = None
        self.capabilities: Any = None

    async def handle(
        self,
        message: RequestResponder | types.ServerNotification | Exception,
    ) -> None:
        if isinstance(message, Exception):
            self._proto.event(f"Error: {message}")
            return

        if not isinstance(message, types.ServerNotification):
            return

        match message.root:
            case types.ToolListChangedNotification():
                self.tools_changed_count += 1
                self._proto.event("notifications/tools/list_changed received — re-fetching tools/list")
                result = await self._session.list_tools()
                old_count = self.tool_count
                self.tool_count = len(result.tools)
                self._proto.event(f"Tool list refreshed: {old_count} -> {self.tool_count} tools")

            case types.ResourceListChangedNotification():
                self._proto.event("notifications/resources/list_changed received — re-fetching")
                await self._session.list_resources()

            case types.PromptListChangedNotification():
                self._proto.event("notifications/prompts/list_changed received — re-fetching")
                await self._session.list_prompts()

            case types.LoggingMessageNotification(params=params):
                level = params.level if params else "info"
                data = params.data if params else ""
                self._proto.log("recv", f"log/{level}: {data}")

            case _:
                self._proto.log("recv", f"notification: {message.root}")


# --- REPL ---

async def repl(session: ClientSession, proto: ProtocolLogger, handler: NotificationHandler) -> None:
    """Interactive REPL loop."""
    # Initial tool count
    result = await session.list_tools()
    handler.tool_count = len(result.tools)
    print(f"\nConnected. {handler.tool_count} tools available. Type 'help' for commands.\n")

    while True:
        try:
            line = await anyio.to_thread.run_sync(lambda: input("mcp> "))
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
                await _cmd_info(session, handler)
            else:
                # Try as tool call: "echo_upper hello" → call echo_upper with arg
                await _cmd_call(session, line, proto)
        except Exception as e:
            print(f"Error: {e}")


def _print_help() -> None:
    print("""
Commands:
  tools              List all available tools with descriptions
  call <name>        Call a tool (prompts for arguments)
  <name> <arg>       Shorthand: call tool with single argument
  <name> {"k":"v"}   Shorthand: call tool with JSON arguments
  resources          List available resources
  prompts            List available prompts
  info               Show server info, capabilities, notification stats
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


async def _cmd_call(session: ClientSession, input_str: str, proto: ProtocolLogger) -> None:
    if not input_str:
        print("Usage: call <tool_name> [arg1=val1 arg2=val2 | JSON]")
        return

    # Parse: "tool_name arg" or just "tool_name"
    parts = input_str.split(None, 1)
    tool_name = parts[0].strip('"').strip("'")
    inline_arg = parts[1].strip() if len(parts) > 1 else ""

    # Get tool schema for argument prompting
    tools_result = await session.list_tools()
    tool = next((t for t in tools_result.tools if t.name == tool_name), None)

    if tool is None:
        print(f"Tool '{tool_name}' not found. Use 'tools' to list available tools.")
        return

    # Prompt for arguments
    arguments: dict[str, Any] = {}
    schema = tool.inputSchema or {}
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    if inline_arg and properties:
        # Try JSON first
        try:
            arguments = json.loads(inline_arg)
        except json.JSONDecodeError:
            # Single required param shorthand: "echo hello" → {"message": "hello"}
            req_params = [p for p in properties if p in required]
            if len(req_params) == 1:
                arguments[req_params[0]] = inline_arg.strip('"').strip("'")
            else:
                print(f"Could not parse arguments. Use JSON or interactive mode: call {tool_name}")
                return
    elif properties and not inline_arg:
        print(f"Arguments for '{tool_name}':")
        for pname, pinfo in properties.items():
            ptype = pinfo.get("type", "string")
            req = "(required)" if pname in required else "(optional)"
            default = pinfo.get("default")
            prompt_str = f"  {pname} [{ptype}] {req}"
            if default is not None:
                prompt_str += f" default={default}"
            prompt_str += ": "

            value = await anyio.to_thread.run_sync(lambda p=prompt_str: input(p))

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
            elif ptype in ("object", "array"):
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
        if isinstance(content, types.TextContent):
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


async def _cmd_info(session: ClientSession, handler: NotificationHandler) -> None:
    print(f"  Server:       {handler.server_info or 'N/A'}")
    print(f"  Capabilities: {handler.capabilities or 'N/A'}")
    print(f"  Tools:        {handler.tool_count}")
    print(f"  Refreshes:    {handler.tools_changed_count} (tools/list_changed received)")


# --- Transport Connection ---

async def connect_stdio(args: argparse.Namespace, proto: ProtocolLogger) -> None:
    """Connect via stdio transport (spawn subprocess)."""
    command = args.server_cmd[0]
    cmd_args = args.server_cmd[1:]

    proto.info(f"Connecting via stdio: {command} {' '.join(cmd_args)}")

    params = StdioServerParameters(command=command, args=cmd_args)

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            handler = NotificationHandler(session, proto)
            session._message_handler = handler.handle
            proto.log("send", "initialize")
            init = await session.initialize()
            handler.server_info = init.serverInfo
            handler.capabilities = init.capabilities
            proto.log("recv", f"initialized: {init.serverInfo}")
            print(f"Server: {init.serverInfo.name} v{init.serverInfo.version}")
            await repl(session, proto, handler)


async def connect_http(args: argparse.Namespace, proto: ProtocolLogger) -> None:
    """Connect via streamable HTTP transport."""
    url = args.url
    headers = {}

    # OAuth token from CLI or env
    token = getattr(args, "token", None)
    if token:
        headers["Authorization"] = f"Bearer {token}"

    proto.info(f"Connecting via HTTP: {url}")

    import httpx
    http_client = httpx.AsyncClient(headers=headers) if headers else None

    async with streamable_http_client(url, http_client=http_client) as (read_stream, write_stream, get_session_id):
        async with ClientSession(read_stream, write_stream) as session:
            handler = NotificationHandler(session, proto)
            session._message_handler = handler.handle
            proto.log("send", "initialize")
            init = await session.initialize()
            handler.server_info = init.serverInfo
            handler.capabilities = init.capabilities
            session_id = get_session_id()
            proto.log("recv", f"initialized: {init.serverInfo}, session={session_id}")
            print(f"Server: {init.serverInfo.name} v{init.serverInfo.version}")
            if session_id:
                print(f"Session: {session_id}")
            caps = init.capabilities
            if caps and caps.tools and getattr(caps.tools, "listChanged", False):
                print("Server supports tools/list_changed — dynamic tool updates enabled")
            await repl(session, proto, handler)


# --- Main ---

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mcp-client",
        description="Spec-conformant interactive MCP test client.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s stdio -- python -m mcp_server_factory --config config.yaml
  %(prog)s stdio -- mcp-proxy --autoload echo
  %(prog)s http http://localhost:12201/mcp
  %(prog)s -v http http://localhost:12201/mcp
  %(prog)s http --token mytoken http://localhost:12201/mcp
""",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Show protocol messages")
    sub = parser.add_subparsers(dest="transport", required=True)

    # stdio
    stdio_p = sub.add_parser("stdio", help="Connect via stdio (spawn server process)")
    stdio_p.add_argument("server_cmd", nargs="+", metavar="CMD", help="Server command (after --)")

    # http
    http_p = sub.add_parser("http", help="Connect via streamable HTTP")
    http_p.add_argument("url", help="Server URL (e.g. http://localhost:12201/mcp)")
    http_p.add_argument("--token", "-t", help="Bearer token for OAuth")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    proto = ProtocolLogger(verbose=args.verbose)

    print("MCP Client — Spec-Conformant Test & Debug Tool")
    print("=" * 48)

    try:
        if args.transport == "stdio":
            anyio.run(connect_stdio, args, proto)
        elif args.transport == "http":
            anyio.run(connect_http, args, proto)
    except KeyboardInterrupt:
        print("\nDisconnected.")


if __name__ == "__main__":
    main()
