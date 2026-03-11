# Examples

Quick start scripts to try the MCP Server Toolkit.

## Prerequisites

```bash
cd /path/to/mcp_server_toolkit
pip install -e ".[dev]"
```

## Scenarios

### 1. Factory + Echo (stdio)
Simplest setup. Factory loads the echo plugin, client connects via stdio.

```bash
./examples/run_factory_echo.sh
```

### 2. Proxy + Echo (HTTP)
Proxy runs on HTTP, client connects via streamable-http.
You can load/unload plugins at runtime.

```bash
# Terminal 1: Start proxy
./examples/run_proxy_http.sh

# Terminal 2: Connect client
./examples/connect_proxy_http.sh

# Terminal 3: Management (optional)
mcp-proxy status
mcp-proxy load greet
mcp-proxy unload echo
```

### 3. Proxy + Shell (HTTP)
Proxy with the shell plugin — filesystem, search, shell execution.

```bash
# Terminal 1
./examples/run_proxy_shell.sh

# Terminal 2
./examples/connect_proxy_http.sh
```

### 4. Interactive Client (manual)
Connect to any running MCP server:

```bash
# stdio (spawns server as subprocess)
python examples/mcp_client.py stdio -- mcp-factory --config examples/configs/factory_echo.yaml

# HTTP (connect to running server)
python examples/mcp_client.py http http://localhost:12200/mcp

# Verbose mode (shows protocol messages)
python examples/mcp_client.py -v stdio -- mcp-proxy --autoload echo
```

## Client REPL Commands

Once connected, type:
- `tools` — list all available tools
- `call <name>` — call a tool (prompts for arguments)
- `info` — show server info
- `help` — all commands
- `quit` — disconnect
