"""Loader — Re-export from framework for backwards compatibility."""

from mcp_server_framework.plugins.loader import (
    load_module,
    find_register,
    set_plugin_dirs,
    add_plugin_dir,
)

__all__ = ["load_module", "find_register", "set_plugin_dirs", "add_plugin_dir"]
