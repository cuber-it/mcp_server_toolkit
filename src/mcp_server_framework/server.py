"""Server factory — creates a configured FastMCP instance.

Minimal: Creates the server, registers no tools.
Tools are registered by the calling code.

OAuth support via mcp-oauth (optional dependency).
Enabled by default for HTTP transport — set oauth_enabled: false to disable.
Requires oauth_server_url and oauth_public_url when enabled.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


def _build_oauth(config: dict[str, Any]) -> tuple[Any, Any]:
    """Build token_verifier and auth_settings from config.

    Returns (token_verifier, auth_settings) or (None, None) if OAuth
    is disabled or not configured.
    """
    if not config.get("oauth_enabled", True):
        return None, None

    oauth_server_url = config.get("oauth_server_url")
    public_url = config.get("oauth_public_url")

    if not oauth_server_url or not public_url:
        # OAuth enabled but not configured — skip silently for stdio,
        # warn for HTTP since it means no auth protection.
        if config.get("transport", "stdio") != "stdio":
            logger.warning(
                "OAuth enabled but oauth_server_url/oauth_public_url not set. "
                "Running WITHOUT authentication. Set oauth_enabled: false "
                "to silence this warning, or configure OAuth URLs."
            )
        return None, None

    from mcp.server.auth.settings import AuthSettings
    from pydantic import AnyHttpUrl
    from .oauth import IntrospectionTokenVerifier

    token_verifier = IntrospectionTokenVerifier(
        introspection_endpoint=f"{oauth_server_url}/introspect",
        server_url=public_url,
        validate_resource=False,
    )
    auth_settings = AuthSettings(
        issuer_url=AnyHttpUrl(oauth_server_url),
        required_scopes=["user"],
        resource_server_url=AnyHttpUrl(public_url),
    )
    return token_verifier, auth_settings


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

    token_verifier, auth_settings = _build_oauth(config)

    mcp = FastMCP(
        name, instructions=instructions,
        host=host, port=port,
        token_verifier=token_verifier,
        auth=auth_settings,
    )

    auth_status = "OAuth" if token_verifier else "no auth"
    logger.info("MCP Server '%s' created (%s)", name, auth_status)
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
            "Starting %s (streamable-http on %s:%d)...",
            mcp.name, host, port,
        )
        mcp.run(transport="streamable-http")
