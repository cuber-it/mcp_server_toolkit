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

### Management API Authentication

Optionally protect the management API with a Bearer token:

```yaml
# proxy.yaml
management_token: "${MCP_MGMT_TOKEN}"
```

```bash
# Or via CLI
mcp-proxy serve --mgmt-token "my-secret" --autoload echo

# Client commands with token
mcp-proxy status --token "my-secret"
mcp-proxy load shell --token "my-secret"

# Or via environment variable (works for both server and client)
export MCP_MGMT_TOKEN="my-secret"
mcp-proxy serve --autoload echo
mcp-proxy status
```

Without a token configured, no authentication is required (development default).

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

## OAuth Authentication

OAuth is **enabled by default** for HTTP transport (ignored for stdio).
Install the optional dependency:

```bash
pip install mcp-server-toolkit[oauth]
```

Configure via YAML or environment variables:

```yaml
# config.yaml
oauth_enabled: true                              # default: true
oauth_server_url: "https://auth.example.com"     # OAuth introspection endpoint
oauth_public_url: "https://mcp.example.com"      # Public URL of this server
```

```bash
# Or via environment
export MCP_OAUTH_ENABLED=true
export MCP_OAUTH_SERVER_URL=https://auth.example.com
export MCP_PUBLIC_URL=https://mcp.example.com
```

**Behavior:**
- HTTP + OAuth configured → full token verification via introspection
- HTTP + OAuth enabled but URLs missing → **warning**, runs without auth
- HTTP + `oauth_enabled: false` → no auth, no warning
- stdio → OAuth ignored regardless of config

To explicitly disable:
```yaml
oauth_enabled: false
```

## Security

### Shell Plugin Boundaries

The shell plugin supports configurable security boundaries:

```yaml
plugins:
  shell:
    enabled: true
    allowed_paths:              # restrict filesystem access
      - "/home/user/projects"
      - "/tmp"
    blocked_commands:            # block dangerous commands
      - "sudo"
      - "rm -rf /"
      - "chmod"
```

Without boundaries configured, the shell plugin has unrestricted access
(suitable for local development). For shared or production deployments,
configure `allowed_paths` and `blocked_commands`.

### Pre-Call Validation

Register a custom validator that runs before every tool invocation:

```python
from mcp_server_framework.plugins import set_pre_call_validator

def my_validator(tool_name: str, params: dict) -> str | None:
    """Return error string to reject, None to allow."""
    if len(str(params)) > 100_000:
        return "Input too large"
    return None

set_pre_call_validator(my_validator)
```

## Logging

Configure log format via config or environment:

```yaml
log_level: INFO
log_format: json    # "json" for machine-readable, "text" (default) for humans
```

JSON output example:
```json
{"ts": "2026-03-11T10:30:00+00:00", "level": "INFO", "logger": "mcp_server_proxy.proxy", "msg": "Plugin 'echo' loaded: 2 tools ['echo', 'echo_upper']"}
```

## Interactive Test Client

Debug and explore any MCP server from the terminal:

```bash
# Connect via stdio
python examples/mcp_client.py -v stdio -- mcp-proxy --autoload echo

# Connect via HTTP
python examples/mcp_client.py http http://localhost:12200/mcp
```

REPL commands: `tools`, `call <name>`, `resources`, `prompts`, `info`, `quit`

Tool shorthand — call tools directly by name:

```
mcp> echo hello              # single-arg shorthand
mcp> echo_upper world
mcp> greet Claude
mcp> proxy__status           # no-arg tools work too
mcp> call echo               # interactive mode (prompts for args)
```

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
log_format: text           # text | json
auto_prefix: true

# OAuth (enabled by default for HTTP, set false to disable)
oauth_server_url: "https://auth.example.com"
oauth_public_url: "https://mcp.example.com"

# Management API auth (separate from OAuth, optional)
management_token: "${MCP_MGMT_TOKEN}"

autoload:
  - echo
  - shell

plugins:
  echo:
    enabled: true
  shell:
    enabled: true
    timeout: 60
    allowed_paths:
      - "/home/user/projects"
    blocked_commands:
      - "sudo"
  mattermost:
    enabled: true
    url: "https://mm.example.com"
    token: "${MM_TOKEN}"
```

Example configs in `config/` and `examples/configs/`.

## Tests

```bash
pytest           # 147 tests
pytest -v        # verbose
pytest tests/proxy/   # proxy only
```

## Project Structure

```
src/
├── mcp_server_framework/     # Shared: config, server, health, logging, plugins
├── mcp_server_factory/       # Static loader + CLI
└── mcp_server_proxy/         # Dynamic loader + management API + CLI
plugins/
├── echo.py                   # Minimal example
├── greet.py                  # Minimal example
├── mattermost/               # REST adapter (Mattermost)
├── wekan/                    # REST adapter (Wekan Kanban)
└── shell/                    # Workstation tools (filesystem, search, exec)
examples/
├── mcp_client.py             # Interactive test client
├── configs/                  # Ready-to-use YAML configs
└── *.sh                      # Launch scripts
tests/                        # 147 tests (framework, factory, proxy, plugins)
config/                       # Example configs + systemd service
```

## License

MIT
