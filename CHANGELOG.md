# Changelog

## 1.5.2 (2026-03-22)

### Framework
- README: fix gate documentation link (absolute GitHub URL)

## 1.5.1 (2026-03-22)

### Framework
- README: added Gate section under Security

## 1.5.0 (2026-03-22)

### Framework
- Added `mcp_server_framework.gate` — session-based TOTP gate for MCP tool groups
  - `Gate` class with `protect()` decorator, `register_tools()`, lockout after 5 failures
  - Pluggable secret backends: `EnvBackend` (default), `FileBackend`, `VaultwardenBackend`
  - Pure stdlib TOTP (RFC 6238), no mandatory dependencies
  - 28 tests in `tests/framework/test_gate.py`

## 1.4.0 (2026-03-13)

### Framework
- **PluginRegistry**: Shared plugin tracking with collision detection, extracted from Factory and Proxy.
- **ToolLogger**: Pluggable tool call logging — `JsonlToolLogger`, `TextToolLogger`, `TranscriptLogger`, `CompositeToolLogger`.
- **Introspection helpers**: `plugin_status()`, `plugin_list()`, `tool_list()`.

### Factory
- Refactored to use `PluginRegistry` from framework.
- Logging plugin uses `TextToolLogger` + `TranscriptLogger` + `CompositeToolLogger`.

### Proxy
- Refactored to use `PluginRegistry` from framework.
- `tool_log.py` wraps `JsonlToolLogger` from framework.

## 1.3.0 (2026-03-13)

### Framework
- Dotted import support: plugin names with dots (e.g. `mcp_shell_tools.shell`) imported directly via importlib.

### Plugins
- shell, wekan, mattermost moved to [mcp_tools](https://github.com/cuber-it/mcp_tools) as independent PyPI packages.

## 1.2.1 (2026-03-12)

### Config
- stdio config for Claude Code / Claude Desktop integration.

## 1.2.0 (2026-03-12)

### Proxy
- **Dynamic Dispatch**: `proxy__run` gateway tool for calling runtime-loaded tools.
- `proxy__tools(dynamic_only=true)` filter.
- Startup tracking: `PluginManager.mark_startup_done()`.

## 1.1.0 (2026-03-12)

### Framework
- ToolTracker tracks resources and prompts in addition to tools.
- Plugin config loading and discovery.

### Proxy
- Spec-conformant notifications: `tools/list_changed`, `resources/list_changed`, `prompts/list_changed`.
- Plugin config separation: credentials in `{plugin_dir}/{name}/config.yaml`.
- New tools: `proxy__list`, `proxy__tools`.

## 1.0.1 (2026-03-11)

### Framework
- OAuth token cache with configurable TTL (default: 8h).

### Proxy
- Persistent tool call logging to `~/.mcp_proxy/logs/tool_calls.jsonl` with daily rotation.

## 1.0.0 (2026-03-11)

First stable release.

### Framework
- Config loader: YAML + ENV three-tier merge.
- FastMCP server factory with stdio / streamable-http transport.
- OAuth 2.0 Token Introspection (RFC 7662).
- Health server with readiness checks.
- Plugin infrastructure: loader, tracker, pre-call validation.

### Factory
- Static plugin loading, tool call logging, transcript recording, management tools.

### Proxy
- Dynamic plugin loading/unloading/reloading, management REST API, auto-prefix, CLI, health endpoint.

## 0.9.2 (2026-03-11)

- Own OAuth implementation replacing external mcp-oauth dependency.
- Shell plugin expanded from 12 to 33 tools.

## 0.9.0 (2026-03-10)

- Initial three-package architecture (Framework, Factory, Proxy).
- Plugin interface: `register(mcp, config)`.

## 0.1.0 (2026-03-10)

- Initial monorepo setup.
