# MCP Server Toolkit

A Python toolkit for building MCP (Model Context Protocol) servers.

Three packages, one ecosystem:

| Package | Role |
|---------|------|
| **mcp_server_framework** | Shared library: config, transport, health, plugin infrastructure |
| **mcp_server_factory** | Static plugin loading at startup (CLI tool) |
| **mcp_server_proxy** | Dynamic plugin loading at runtime (daemon with management API) |

## Quick Start

```bash
pip install -e ".[dev]"
```

### Factory — Build a static server from plugins

```bash
mcp-factory --plugins echo --http 12201 --plugin-dir ./plugins
```

### Proxy — Dynamic server with runtime plugin management

```bash
# Start proxy with echo plugin on HTTP
mcp-proxy serve --autoload echo --http 12200 --plugin-dir ./plugins

# Manage plugins at runtime (separate terminal)
mcp-proxy status
mcp-proxy load shell
mcp-proxy unload echo
mcp-proxy reload shell
```

### Framework — Build a standalone server

```python
from mcp_server_framework import load_config, create_server, run_server

config = load_config()
mcp = create_server(config)

@mcp.tool()
def hello(name: str) -> str:
    """Says hello."""
    return f"Hello, {name}!"

run_server(mcp, config)
```

## Plugin Interface

Every plugin implements one function:

```python
def register(mcp, config: dict) -> None:
    @mcp.tool()
    def my_tool(param: str) -> str:
        """Tool description for the LLM."""
        return do_something(param)
```

Works with Factory and Proxy without changes.

### Recommended Plugin Structure

```
plugins/myservice/
├── __init__.py     # register(mcp, config) — thin MCP wrapper
├── client.py       # HTTP client (pure Python, no MCP)
└── tools.py        # Tool logic (pure Python, no MCP)
```

This separation keeps your business logic testable and reusable
without MCP dependencies.

## Included Plugins

| Plugin | Tools | Description |
|--------|-------|-------------|
| `echo` | 2 | Minimal example — echo and echo_upper |
| `greet` | 1 | Minimal example — greet by name |
| `mattermost` | 5 | Mattermost REST API (send, channels, posts, search, user) |
| `wekan` | 18 | Wekan Kanban REST API (boards, cards, checklists, labels) |
| `shell` | 12 | Filesystem, search, shell execution, navigation |

## Proxy Features

### Management API

The proxy runs a FastAPI management server on a separate port (default: 12299):

```
GET  /proxy/status          All plugins and tools
GET  /proxy/plugins         Plugin name list
POST /proxy/load            {"plugin": "name"}
POST /proxy/unload          {"plugin": "name"}
POST /proxy/reload          {"plugin": "name"}
GET  /proxy/commands         Registered management extensions
POST /proxy/command/{name}   Run a management extension
```

### Auto-Prefix

Avoid tool name collisions when loading multiple plugins:

```yaml
# proxy.yaml
auto_prefix: true   # tool "send" from plugin "mm" becomes "mm_send"

plugins:
  mattermost:
    prefix: "mm"     # custom prefix (overrides plugin name)
  echo:
    prefix: false     # disable prefix for this plugin
```

Tools that already start with their plugin's prefix are not double-prefixed.

### Health Endpoint

When running on HTTP, the health server includes plugin status:

```
GET /health              Simple status
GET /health/detailed     Uptime, requests, errors
GET /health/ready        Readiness check (verifies plugins loaded)
GET /health/plugins      Current plugin and tool inventory
```

### Management Command Extensions

Extend the proxy with custom management commands:

```python
def register(mcp, config: dict) -> None:
    proxy = config.get("_proxy")
    if proxy:
        proxy.register_command("stats", lambda p: f"{len(p.plugins)} plugins")
```

Commands are available via MCP tools and the REST management API.

## Interactive Test Client

Debug and explore any MCP server from the terminal:

```bash
# Connect via stdio
python examples/mcp_client.py -v stdio -- mcp-proxy --autoload echo

# Connect via HTTP
python examples/mcp_client.py http http://localhost:12200/mcp
```

REPL commands: `tools`, `call <name>`, `resources`, `prompts`, `info`, `quit`

## Examples

Ready-to-run scripts in `examples/`:

```bash
./examples/run_factory_echo.sh       # Factory + Echo (stdio, all-in-one)
./examples/run_proxy_http.sh         # Proxy + Echo (HTTP)
./examples/run_proxy_shell.sh        # Proxy + Shell (HTTP)
./examples/run_proxy_full.sh         # Proxy + Echo + Shell (HTTP)
./examples/connect_proxy_http.sh     # Client → running proxy
```

See [examples/README.md](examples/README.md) for details.

## Configuration

YAML config with environment variable overrides (`MCP_*`):

```yaml
server_name: "My Proxy"
transport: http            # stdio | http
host: "0.0.0.0"
port: 12200
health_port: 12201
management_port: 12299
log_level: INFO
auto_prefix: true

autoload:
  - echo
  - shell

plugins:
  echo:
    enabled: true
  shell:
    enabled: true
    timeout: 60
  mattermost:
    enabled: true
    url: "https://mm.example.com"
    token: "${MM_TOKEN}"
```

Example configs in `config/` and `examples/configs/`.

## Tests

```bash
pytest           # 119 tests
pytest -v        # verbose
pytest tests/proxy/   # proxy only
```

## Project Structure

```
src/
├── mcp_server_framework/     # Shared: config, server, health, plugins
├── mcp_server_factory/       # Static loader + CLI
└── mcp_server_proxy/         # Dynamic loader + management API + CLI
plugins/
├── echo.py                   # Minimal example
├── greet.py                  # Minimal example
├── mattermost/               # REST adapter reference
├── wekan/                    # REST adapter reference
└── shell/                    # Workstation tools reference
examples/
├── mcp_client.py             # Interactive test client
├── configs/                  # Ready-to-use YAML configs
└── *.sh                      # Launch scripts
tests/                        # 119 tests (framework, factory, proxy, plugins)
config/                       # Example configs + systemd service
```

## License

MIT
