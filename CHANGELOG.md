# Changelog

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
