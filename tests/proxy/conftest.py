"""Proxy test fixtures."""

from pathlib import Path
from mcp_server_framework.plugins.loader import add_plugin_dir

_fixtures_dir = Path(__file__).parent.parent / "fixtures"
add_plugin_dir(_fixtures_dir)
