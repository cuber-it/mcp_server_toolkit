"""Configuration — YAML + environment variables.

Three-tier merge: Defaults → YAML → ENV (last wins).
"""

from __future__ import annotations

import os
import copy
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _parse_bool(value: str) -> bool:
    """Parse bool from ENV string."""
    return value.lower() in ("true", "1", "yes", "on")


# Immutable defaults — mutable values (tools) are
# deep-copied in load_config() for each call.
_DEFAULTS: dict[str, Any] = {
    "server_name": "MCP Server",
    "version": "0.1.0",
    "instructions": "",
    "service_type": "generic",
    "log_level": "INFO",
    # Transport
    "host": "0.0.0.0",
    "port": 12201,
    "transport": "stdio",
    # Health
    "health_port": None,  # Default: port + 1
    # OAuth
    "oauth_enabled": False,
    "oauth_public_url": None,
    # Tool names (for registry/monitoring)
    "tools": [],
}

# ENV key → (config key, type cast)
_ENV_MAPPING: dict[str, tuple[str, type]] = {
    "MCP_SERVER_NAME": ("server_name", str),
    "MCP_LOG_LEVEL": ("log_level", str),
    "MCP_HOST": ("host", str),
    "MCP_PORT": ("port", int),
    "MCP_HEALTH_PORT": ("health_port", int),
    "MCP_TRANSPORT": ("transport", str),
    "MCP_OAUTH_ENABLED": ("oauth_enabled", _parse_bool),
    "MCP_PUBLIC_URL": ("oauth_public_url", str),
}


def load_config(
    config_path: Path | None = None,
) -> dict[str, Any]:
    """Load configuration: Defaults → YAML → ENV.

    Args:
        config_path: Optional path to YAML file.

    Returns:
        Merged config dict (own copy, safe to mutate).
    """
    config = copy.deepcopy(_DEFAULTS)

    if config_path and config_path.exists():
        _load_yaml(config, config_path)

    _apply_env(config)

    # Computed defaults
    if config["health_port"] is None:
        config["health_port"] = config["port"] + 1

    return config


def _load_yaml(
    config: dict[str, Any],
    path: Path,
) -> None:
    """Load YAML file into config dict."""
    try:
        import yaml
    except ImportError:
        logger.warning("PyYAML not installed, YAML config ignored")
        return

    with open(path) as f:
        yaml_config = yaml.safe_load(f) or {}
    config.update(yaml_config)
    logger.info("Config loaded: %s", path)


def _apply_env(config: dict[str, Any]) -> None:
    """Apply ENV overrides to config."""
    for env_key, (config_key, cast) in _ENV_MAPPING.items():
        value = os.getenv(env_key)
        if value is None:
            continue
        try:
            config[config_key] = cast(value)
        except (ValueError, TypeError):
            logger.warning("ENV %s=%r: invalid value", env_key, value)
