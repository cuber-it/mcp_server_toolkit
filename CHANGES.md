# Changelog

## 0.9.0 (2026-03-11)

Feature-complete release.

### Framework
- YAML config with environment variable expansion (`${VAR}`)
- Dual transport: stdio and streamable HTTP
- Health server with readiness checks (FastAPI, separate port)
- Plugin infrastructure: `register(mcp, config)` interface
- ToolTracker with auto-prefix and logging callback
- Pre-call validation hook (`set_pre_call_validator`)
- Configurable logging: text or JSON format (`setup_logging`)

### Factory
- Static plugin loading at startup
- CLI: `mcp-factory --plugins echo shell --http 12201`

### Proxy
- Dynamic plugin loading/unloading/reloading at runtime
- FastAPI management API on separate port (load, unload, reload, status)
- Bearer token authentication for management API (optional)
- Auto-prefix for tool names (global + per-plugin override)
- Tool collision detection
- Management command extensions (`register_command`)
- Auto-detection of running proxy instance
- Graceful shutdown (SIGTERM/SIGINT)
- Health endpoint with plugin status and readiness check
- CLI: `mcp-proxy serve`, `status`, `load`, `unload`, `reload`
- systemd user service template

### Plugins
- **echo** — Minimal example (2 tools)
- **greet** — Minimal example (1 tool)
- **mattermost** — REST adapter: send, channels, posts, search, user (5 tools)
- **wekan** — REST adapter: boards, lists, cards, labels, checklists, custom fields (18 tools)
- **shell** — Filesystem, search, shell execution, navigation (12 tools)
  - Security boundaries: `allowed_paths`, `blocked_commands`

### Examples
- Interactive MCP test client (stdio + HTTP, REPL with tool discovery)
- Launch scripts for Factory and Proxy scenarios
- Ready-to-use YAML configs

### Tests
- 141 tests covering framework, factory, proxy, plugins, security

## 0.1.0 (2026-03-10)

- Initial monorepo setup
- Framework: config, transport, health (from mcp_server_framework v0.3.0)
- Factory: plugin loading, tool tracking, CLI (from mcp_server_factory v1.0.0)
- Proxy: package skeleton
