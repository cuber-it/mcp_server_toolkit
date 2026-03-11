"""Server factory — creates a configured FastMCP instance.

Minimal: Creates the server, registers no tools.
Tools are registered by the calling code.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


def create_server(config: dict[str, Any]) -> FastMCP:
    """Create a configured FastMCP instance.

    Args:
        config: Server configuration (from load_config()).

    Returns:
        FastMCP instance, ready for tool registration.
    """
    name = config.get("server_name", "MCP Server")
    instructions = config.get("instructions", "")

    host = config.get("host", "127.0.0.1")
    port = config.get("port", 8000)

    mcp = FastMCP(
        name, instructions=instructions,
        host=host, port=port,
    )
    logger.info("MCP Server '%s' created", name)
    return mcp


def run_server(
    mcp: FastMCP,
    config: dict[str, Any],
) -> None:
    """Start the MCP server according to config.

    Args:
        mcp: FastMCP instance with registered tools.
        config: Server configuration.

    Raises:
        KeyError: If transport/host/port are missing and
            config does not come from load_config().
    """
    transport = config["transport"]

    if transport == "stdio":
        logger.info("Starting %s (stdio)...", mcp.name)
        mcp.run(transport="stdio")
    else:
        host = config["host"]
        port = config["port"]
        logger.info(
            "Starting %s (HTTP on %s:%d)...",
            mcp.name, host, port,
        )
        mcp.run(transport="streamable-http")
