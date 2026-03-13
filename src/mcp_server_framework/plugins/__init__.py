"""Plugin infrastructure — shared by Factory and Proxy."""

from .models import LoadedPlugin
from .loader import load_module, load_plugin_config, list_available_plugins, find_register
from .tracker import ToolTracker, set_log_callback, set_pre_call_validator
from .registry import PluginRegistry, LoadResult, UnloadResult
from .tool_logger import (
    ToolLogger, JsonlToolLogger, TextToolLogger, TranscriptLogger, CompositeToolLogger,
)
from .introspection import plugin_status, plugin_list, tool_list

__all__ = [
    # Models
    "LoadedPlugin",
    # Loader
    "load_module",
    "load_plugin_config",
    "list_available_plugins",
    "find_register",
    # Tracker
    "ToolTracker",
    "set_log_callback",
    "set_pre_call_validator",
    # Registry (v1.4)
    "PluginRegistry",
    "LoadResult",
    "UnloadResult",
    # Logging (v1.4)
    "ToolLogger",
    "JsonlToolLogger",
    "TextToolLogger",
    "TranscriptLogger",
    "CompositeToolLogger",
    # Introspection (v1.4)
    "plugin_status",
    "plugin_list",
    "tool_list",
]
