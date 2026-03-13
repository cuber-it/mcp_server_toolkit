# MCP Server Framework

A Python framework for building MCP (Model Context Protocol) servers.
Implements MCP 1.26 core protocol (tools, resources, prompts, notifications).
Optional features (completion, subscriptions, progress, cancellation) are not yet exposed through the plugin API.

> **PyPI:** `pip install mcp-server-framework` — repo name is `mcp_server_toolkit` for historical reasons.

Three packages, one ecosystem:

| Package | Role |
|---------|------|
| **mcp_server_framework** | Shared library: config, transport, health, plugin infrastructure |
| **mcp_server_factory** | Static plugin loading at startup (CLI tool) |
| **mcp_server_proxy** | Dynamic plugin loading at runtime (daemon with management API) |

## Installation

```bash
pip install mcp-server-framework
```

For development:
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

# Manage plugins at runtime via CLI
mcp-proxy status
mcp-proxy load greet
mcp-proxy unload echo
mcp-proxy reload greet
```

Plugins can also be managed via MCP tools (`proxy__load`, `proxy__unload`, `proxy__reload`)
or the REST management API — from any connected client.

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

    @mcp.resource("myns://status")
    def my_resource() -> str:
        return "OK"

    @mcp.prompt()
    def my_prompt(text: str) -> str:
        return f"Analyze: {text}"
```

Tools, resources, and prompts are all tracked and checked for collisions.
Works with Factory and Proxy without changes.
See `plugins/demo_full.py` for a complete example.

### Plugin Loading

The framework supports two plugin sources:

**Local plugins** — files or directories in `--plugin-dir`:
```bash
mcp-proxy serve --autoload echo --plugin-dir ./plugins
```

**Installed packages** — dotted Python imports:
```yaml
autoload:
  - echo                        # local plugin from --plugin-dir
  - mcp_shell_tools.shell       # installed PyPI package
  - mcp_wekan_tools.wekan       # installed PyPI package
```

Dotted names are imported directly via `importlib`. Simple names go through the plugin directory search.

### Create a New Plugin

```bash
./scripts/new-plugin.sh myservice          # creates plugins/myservice/
./scripts/new-plugin.sh myservice ./src    # custom target directory
```

Generates `__init__.py` (MCP wiring) and `tools.py` (pure logic) with annotated
examples — start editing `tools.py`, restart the proxy, done.

### Recommended Plugin Structure

```
plugins/myservice/
├── __init__.py     # register(mcp, config) — thin MCP wrapper
├── client.py       # HTTP client (pure Python, no MCP)
└── tools.py        # Tool logic (pure Python, no MCP)
```

This separation keeps your business logic testable and reusable
without MCP dependencies.

## Demo Plugins

| Plugin | Tools | Description |
|--------|-------|-------------|
| `echo` | 2 | Minimal example — echo and echo_upper |
| `greet` | 1 | Minimal example — greet by name |
| `demo_full` | 1 | Reference: tool + resource + prompt registration |

Production tool plugins (shell, wekan, mattermost) are available as separate
PyPI packages. See [mcp_tools](https://github.com/cuber-it/mcp_tools).

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

### MCP Management Tools

The proxy registers management tools that any connected MCP client can call:

| Tool | Description |
|------|-------------|
| `proxy__load` | Load a plugin at runtime |
| `proxy__unload` | Unload a plugin |
| `proxy__reload` | Reload a plugin (picks up code changes) |
| `proxy__status` | Show loaded plugins, tools, resources, prompts |
| `proxy__list` | List available (not yet loaded) plugins |
| `proxy__tools` | List all loaded tools (supports `dynamic_only` filter) |
| `proxy__run` | Call a dynamically loaded tool by name (requires `dynamic_dispatch: true`) |

The server sends `tools/list_changed`, `resources/list_changed`, and `prompts/list_changed`
notifications when plugins are loaded or unloaded.

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
mcp-proxy load greet --token "my-secret"

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
  my_plugin:
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

### Dynamic Dispatch

MCP clients cache the tool list and most don't handle `tools/list_changed` notifications.
This means tools loaded at runtime are invisible to the client. Dynamic dispatch solves this
with a single gateway tool `proxy__run` that can call any dynamically loaded tool by name.

```yaml
# proxy.yaml
dynamic_dispatch: true    # default: false
autoload:
  - echo                  # static — visible in tools/list, callable directly
```

```
# At runtime: load a plugin dynamically
proxy__load greet         → "Loaded 'greet': 1 tool. Call them via proxy__run(...)"

# Call dynamic tools via the gateway
proxy__run(tool="greet", arguments={"name": "Claude"})

# List only dynamic tools
proxy__tools(dynamic_only=true)
```

**Security rule:** Tools loaded at startup (autoload) are **not** callable via `proxy__run` —
they are visible in `tools/list` and the client can set permissions on them directly.
`proxy__run` only dispatches to tools loaded after startup.

> **Note:** Dynamic dispatch is a workaround for the current MCP client ecosystem.
> Most clients (Claude.ai, VS Code, LibreChat) do not handle `tools/list_changed`
> notifications, so runtime-loaded tools remain invisible to them. If clients start
> supporting dynamic tool discovery natively, this feature may be deprecated.

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
Uses RFC 7662 Token Introspection — no extra dependencies needed (uses httpx from MCP SDK).
Valid tokens are cached for 8 hours (configurable via `oauth_cache_ttl`) to reduce introspection load.

Configure via YAML or environment variables:

```yaml
# config.yaml
oauth_enabled: true                              # default: true
oauth_server_url: "https://auth.example.com"     # OAuth introspection endpoint
oauth_public_url: "https://mcp.example.com"      # Public URL of this server
oauth_cache_ttl: 28800                           # token cache in seconds (default: 8h)
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

### Tool Call Logging (Proxy)

The proxy automatically logs every tool call to `~/.mcp_proxy/logs/tool_calls.jsonl`:

```json
{"ts": "2026-03-11T14:30:00", "tool": "echo", "params": {"text": "hello"}, "result": "hello", "ok": true}
```

- Daily rotation with gzip compression (`YYYY-MM-DD.jsonl.gz`)
- 90-day retention with automatic cleanup
- Safe — never raises, never blocks tool execution

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
./examples/run_proxy_full.sh         # Proxy + Echo + Greet (HTTP)
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
dynamic_dispatch: false    # true = enable proxy__run for runtime-loaded tools

# OAuth (enabled by default for HTTP, set false to disable)
oauth_server_url: "https://auth.example.com"
oauth_public_url: "https://mcp.example.com"
oauth_cache_ttl: 28800          # token cache seconds (default: 8h, 0 = disabled)

# Management API auth (separate from OAuth, optional)
management_token: "${MCP_MGMT_TOKEN}"

autoload:
  - echo                              # local plugin
  - mcp_shell_tools.shell             # installed PyPI package

plugins:
  echo:
    enabled: true
```

### Plugin-Specific Configuration

Credentials and plugin-specific settings go into a separate config file
per plugin, **not** into the proxy config:

```
~/mcp_plugins/{plugin_name}/config.yaml
```

The proxy loads these automatically. If no plugin config file exists, it falls
back to the `plugins:` section in the proxy config.

Example configs in `config/`:

| Config | Use case |
|--------|----------|
| `proxy.example.yaml` | HTTP proxy with all options documented |
| `config-stdio.yaml` | stdio for Claude Code / Claude Desktop |
| `framework.example.yaml` | Standalone framework server |
| `factory.example.yaml` | Factory with static plugins |

### Claude Code / Claude Desktop

Use the proxy as a stdio MCP server — no OAuth, no ports:

```json
{
  "mcpServers": {
    "proxy": {
      "command": "/path/to/mcp_server_toolkit/.venv/bin/mcp-proxy",
      "args": ["serve", "--config", "config/config-stdio.yaml",
               "--plugin-dir", "./plugins"]
    }
  }
}
```

## Tests

```bash
pytest           # all tests
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
└── demo_full.py              # Reference: tool + resource + prompt
examples/
├── mcp_client.py             # Interactive test client
├── configs/                  # Ready-to-use YAML configs
└── *.sh                      # Launch scripts
scripts/
└── new-plugin.sh             # Plugin scaffold generator
tests/                        # Tests (framework, factory, proxy)
config/                       # Example configs + systemd service
```

Production tool plugins are maintained in a separate repository:
[mcp_tools](https://github.com/cuber-it/mcp_tools) — shell, wekan, mattermost, and more.

## License

MIT
