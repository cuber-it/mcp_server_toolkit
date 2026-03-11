"""Plugin infrastructure — shared by Factory and Proxy."""

from .models import LoadedPlugin
from .loader import load_module, find_register
from .tracker import ToolTracker

__all__ = [
    "LoadedPlugin",
    "load_module",
    "find_register",
    "ToolTracker",
]
