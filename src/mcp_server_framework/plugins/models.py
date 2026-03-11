"""Data models for plugin management."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from types import ModuleType


@dataclass
class LoadedPlugin:
    """Record of a loaded plugin."""

    name: str
    module: ModuleType
    tools: list[str]
    loaded_at: datetime
    config: dict
    internal: bool = False
