# Changelog

## 1.4.0 (2026-03-13)

### Framework
- **PluginRegistry**: Shared plugin tracking with collision detection, extracted from Factory and Proxy.
  Both now use `PluginRegistry` internally instead of duplicating tracking logic.
- **ToolLogger**: Pluggable tool call logging with three implementations:
  - `JsonlToolLogger` — daily JSONL files with gzip archival and retention (from Proxy)
  - `TextToolLogger` — one-line text log with size-based rotation (from Factory)
  - `TranscriptLogger` — Markdown session transcripts (from Factory)
  - `CompositeToolLogger` — combines multiple loggers
- **Introspection helpers**: `plugin_status()`, `plugin_list()`, `tool_list()` — pure functions
  for formatted output, used by Factory and Proxy management tools.

### Factory
- Refactored to use `PluginRegistry` from framework.
- Logging plugin now uses `TextToolLogger` + `TranscriptLogger` + `CompositeToolLogger` from framework.
- Management plugin uses `plugin_status()` and `plugin_list()` introspection helpers.

### Proxy
- Refactored to use `PluginRegistry` from framework.
- `tool_log.py` now wraps `JsonlToolLogger` from framework (thin subclass with proxy defaults).
- Management tools use `plugin_status()` and `tool_list()` introspection helpers.

### Notes
- Non-breaking: all public APIs unchanged, all 142 tests pass.
- Plugin `register(mcp, config)` interface unchanged.

## 1.3.0 (2026-03-13)

### Framework
- **Dotted import support**: Plugin names with dots (e.g. `mcp_shell_tools.shell`) are imported
  directly via `importlib`, skipping directory scan. Enables loading installed PyPI packages as plugins.

### Plugins
- **Extracted**: shell, wekan, mattermost moved to separate repository
  ([mcp_tools](https://github.com/cuber-it/mcp_tools)) as independent PyPI packages.
  Only demo plugins (echo, greet, demo_full) remain in this repo.

### Docs
- README: updated plugin table, added dotted import documentation, removed shell/wekan/mattermost references
- Example configs and scripts updated for demo plugins only

## 1.2.1 (2026-03-12)

### Config
- stdio config for Claude Code / Claude Desktop integration (`config/config-stdio.yaml`)

## 1.2.0 (2026-03-12)

### Proxy
- **Dynamic Dispatch**: `proxy__run` gateway tool for calling runtime-loaded tools
  - Workaround for MCP clients not handling `tools/list_changed` — may be deprecated when clients catch up
  - Only tools loaded after startup are dispatchable (security: static tools are excluded)
  - Enabled via `dynamic_dispatch: true` in config (default: off)
  - `proxy__load` includes usage hint when dynamic dispatch is active
- `proxy__tools(dynamic_only=true)` filter for listing only dynamically loaded tools
- `LoadedPlugin.startup` flag distinguishes static (autoload) vs dynamic (runtime) plugins
- Startup tracking: `PluginManager.mark_startup_done()` freezes the static tool set

### Docs
- README: PyPI install instructions, plugin-config separation, resources/prompts in plugin interface
- README: dynamic dispatch documentation
- proxy.example.yaml: credentials removed, points to plugin config files
- Clarified MCP 1.26 core protocol conformance scope

### Tests
- 183 tests (was 166), all passing
- 17 new tests for dynamic dispatch (startup tracking, proxy__run, proxy__tools filter, load hints)

## 1.1.0 (2026-03-12)

### Framework
- ToolTracker now tracks resources and prompts in addition to tools
- LoadedPlugin model extended with `resources` and `prompts` fields
- Plugin config loading: `load_plugin_config(name)` reads `{plugin_dir}/{name}/config.yaml`
- Plugin discovery: `list_available_plugins()` scans configured plugin directories

### Factory
- Collision detection for resources and prompts (in addition to tools)
- Plugin summary includes resource and prompt counts

### Proxy
- Spec-conformant notifications: `tools/list_changed`, `resources/list_changed`, `prompts/list_changed`
- Replaced private `ctx._request_context` with public API (try/except pattern)
- Collision detection for resources and prompts
- Unload tracks resource/prompt removal (FastMCP lacks `remove_resource()`/`remove_prompt()`)
- Plugin config separation: credentials in `{plugin_dir}/{name}/config.yaml`, not in proxy config
- New MCP tools: `proxy__list` (available plugins), `proxy__tools` (loaded tools)
- `proxy__status` shows resource and prompt counts

### Examples
- Spec-conformant MCP reference client (`examples/mcp_client.py`)
  - Handles `tools/list_changed` by re-fetching `tools/list`
  - Handles `resources/list_changed` and `prompts/list_changed`
  - Interactive REPL with tool calling, resource listing, prompt listing
  - Supports stdio and streamable-http transports
  - OAuth Bearer token support
- Demo plugin (`plugins/demo_full.py`) showing tool + resource + prompt registration

### Tests
- 166 tests (was 159), all passing
- 7 new tests for notification behavior in management tools

## 1.0.1 (2026-03-11)

### Framework
- OAuth token cache with configurable TTL (default: 8h) — reduces introspection load

### Proxy
- Persistent tool call logging to `~/.mcp_proxy/logs/tool_calls.jsonl`
- Daily log rotation with gzip compression, 90-day retention

### Developer Experience
- Plugin scaffold script: `scripts/new-plugin.sh` generates annotated plugin templates

## 1.0.0 (2026-03-11)

First stable release.

### Framework
- Config loader: YAML + ENV with three-tier merge (Defaults → YAML → ENV)
- Server factory: FastMCP with configurable transport (stdio / streamable-http)
- OAuth 2.0 Token Introspection (RFC 7662), enabled by default for HTTP
- Health server with readiness checks on separate port
- Plugin infrastructure: loader, tracker, pre-call validation
- JSON and text logging

### Factory
- Static plugin loading at startup
- Tool call logging with file rotation
- Transcript recording (Markdown)
- Management tools (status, list)

### Proxy
- Dynamic plugin loading/unloading/reloading at runtime
- Management REST API with optional Bearer token auth
- Auto-prefix for tool name collision avoidance
- CLI for both serve and remote commands
- Health endpoint with plugin status

### Plugins
- **shell**: 33 workstation tools (filesystem, editor, search, shell, git, systemd, HTTP, JSON, packages, diagnostics)
- **wekan**: 18 Kanban tools (Wekan REST API)
- **mattermost**: 5 chat tools (Mattermost REST API)
- **echo/greet**: Minimal examples

### Infrastructure
- 159 tests across 12 test modules
- PEP 561 py.typed markers
- MIT license

## 0.9.2 (2026-03-11)

- Own OAuth implementation replacing external mcp-oauth dependency
- Shell plugin expanded from 12 to 33 tools
- Proxy systemd service for Cirrus7

## 0.9.0 (2026-03-10)

- Initial three-package architecture (Framework, Factory, Proxy)
- Plugin interface: `register(mcp, config)`
- Entry points for mcp-factory and mcp-proxy CLI
