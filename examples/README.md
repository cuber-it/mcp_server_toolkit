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

### 3. Proxy + Demo Plugins (HTTP)
Proxy with echo + greet, auto-prefix enabled to avoid tool name collisions.

```bash
# Terminal 1
./examples/run_proxy_full.sh

# Terminal 2
./examples/connect_proxy_http.sh
```

### 4. Proxy with authentication

```bash
# Terminal 1: Start with token
MCP_MGMT_TOKEN=secret mcp-proxy serve --autoload echo --http 12200 --plugin-dir ./plugins

# Terminal 2: Management with token
mcp-proxy status --token secret
mcp-proxy load greet --token secret
```

### 5. Interactive Client (manual)
Connect to any running MCP server:

```bash
# stdio (spawns server as subprocess)
python examples/mcp_client.py stdio -- mcp-factory --config examples/configs/factory_echo.yaml

# HTTP (connect to running server)
python examples/mcp_client.py http http://localhost:12200/mcp

# Verbose mode (shows protocol messages)
python examples/mcp_client.py -v http http://localhost:12200/mcp
```

## Client REPL Commands

Once connected:

```
tools              List all available tools
echo hello         Call a tool directly (shorthand)
echo_upper world   Single-arg shorthand
proxy__status      No-arg tools work too
call echo          Interactive mode (prompts for arguments)
resources          List available resources
prompts            List available prompts
info               Show server info
help               All commands
quit               Disconnect
```

## Configuration Files

| File | Description |
|------|-------------|
| `configs/factory_echo.yaml` | Factory + Echo (stdio) |
| `configs/proxy_echo.yaml` | Proxy + Echo (HTTP) |
| `configs/proxy_full.yaml` | Proxy + Echo + Greet (HTTP, auto-prefix) |

More examples in `config/` at the project root.

## Production Plugins

Production tool plugins (shell, wekan, mattermost) are available as separate
PyPI packages. See [mcp_tools](https://github.com/cuber-it/mcp_tools).
