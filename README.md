# MCP Server Toolkit

A Python toolkit for building MCP (Model Context Protocol) servers.

Three packages, one ecosystem:

| Package | Role | Status |
|---------|------|--------|
| **mcp_server_framework** | Shared library: config, transport, health | Working |
| **mcp_server_factory** | Static plugin loading at startup (CLI) | Working |
| **mcp_server_proxy** | Dynamic plugin loading at runtime (daemon) | Planned |

## Quick Start

```bash
pip install -e ".[dev]"
```

### Factory — Build a server from plugins

```bash
mcp-factory --plugins echo --http 12201
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

Every tool module implements one function:

```python
def register(mcp, config: dict) -> None:
    @mcp.tool()
    def my_tool(param: str) -> str:
        """Tool description for the LLM."""
        return result
```

Works with Factory and Proxy without changes.

## Tests

```bash
pytest
```

## License

MIT
