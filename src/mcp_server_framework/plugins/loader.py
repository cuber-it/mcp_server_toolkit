"""Loader — Plugin resolution and import.

Search order for plugin name "wekan":
1. Local plugin directories (configurable)
2. plugins/wekan/register.py (local package)
3. mcp_wekan_tools (installed package)
4. Path from config
5. Fully qualified import
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

import yaml

logger = logging.getLogger(__name__)

# Default local plugin dirs — can be extended via set_plugin_dirs()
_plugin_dirs: list[Path] = []


def set_plugin_dirs(dirs: list[Path]) -> None:
    """Set local plugin directories for file-based plugin discovery."""
    global _plugin_dirs
    _plugin_dirs = list(dirs)


def add_plugin_dir(path: Path) -> None:
    """Add a local plugin directory."""
    if path not in _plugin_dirs:
        _plugin_dirs.append(path)


def load_plugin_config(name: str) -> dict[str, Any]:
    """Load config.yaml from the plugin's directory in any registered plugin_dir.

    Returns empty dict if no config found.
    """
    for plugin_dir in _plugin_dirs:
        config_file = plugin_dir / name / "config.yaml"
        if config_file.exists():
            try:
                with open(config_file) as f:
                    data = yaml.safe_load(f) or {}
                logger.info("Plugin '%s' config loaded from %s", name, config_file)
                return data
            except Exception as e:
                logger.warning("Error reading plugin config '%s': %s", config_file, e)
    return {}


def list_available_plugins() -> list[dict[str, str]]:
    """Scan all plugin_dirs for available plugins.

    Returns list of dicts with 'name' and 'description'.
    A directory counts as a plugin if it contains register.py, __init__.py, or {name}.py.
    """
    seen = set()
    result = []
    for plugin_dir in _plugin_dirs:
        if not plugin_dir.is_dir():
            continue
        for entry in sorted(plugin_dir.iterdir()):
            if entry.name.startswith(("_", ".")):
                continue
            name = None
            if entry.is_dir() and (
                (entry / "__init__.py").exists()
                or (entry / "register.py").exists()
            ):
                name = entry.name
            elif entry.is_file() and entry.suffix == ".py":
                name = entry.stem
            if name and name not in seen:
                seen.add(name)
                desc = ""
                config_file = entry / "config.yaml" if entry.is_dir() else None
                if config_file and config_file.exists():
                    try:
                        with open(config_file) as f:
                            data = yaml.safe_load(f) or {}
                        desc = data.get("description", "")
                    except Exception:
                        pass
                result.append({"name": name, "description": desc})
    return result


def load_module(name: str, config: dict[str, Any]) -> ModuleType | None:
    """Resolve and import a plugin module by name.

    Search order:
    1. Local file: {plugin_dir}/{name}.py
    2. Local package: {plugin_dir}/{name}/register.py
    3. Pip package: mcp_{name}_tools
    4. Config path: plugins.{name}.path
    5. Qualified import: {name} as module path
    """
    # 1. Local file
    for plugin_dir in _plugin_dirs:
        plugin_file = plugin_dir / f"{name}.py"
        if plugin_file.exists():
            return _import_file(plugin_file, f"plugins.{name}")

    # 2. Local package (__init__.py or register.py)
    for plugin_dir in _plugin_dirs:
        init_file = plugin_dir / name / "__init__.py"
        if init_file.exists():
            return _import_file(init_file, f"plugins.{name}")
        register_file = plugin_dir / name / "register.py"
        if register_file.exists():
            return _import_file(register_file, f"plugins.{name}.register")

    # 3. Pip package
    package_name = f"mcp_{name}_tools"
    module = _try_import(package_name)
    if module and find_register(module):
        return module
    for submodule in ["src.server", "register", "server"]:
        module = _try_import(f"{package_name}.{submodule}")
        if module and find_register(module):
            return module

    # 4. Config path
    plugins_config = config.get("plugins", {})
    plugin_config = plugins_config.get(name, {})
    if isinstance(plugin_config, dict):
        explicit_path = plugin_config.get("path")
        if explicit_path:
            return _load_from_path(Path(explicit_path).expanduser(), name)

    # 5. Qualified import
    module = _try_import(name)
    if module and find_register(module):
        return module

    logger.warning("Plugin '%s' not found in any search path", name)
    return None


def find_register(module: ModuleType) -> Callable | None:
    """Return the register() function from a module, or None."""
    fn = getattr(module, "register", None)
    return fn if callable(fn) else None


def _try_import(module_path: str) -> ModuleType | None:
    try:
        return importlib.import_module(module_path)
    except ImportError:
        return None
    except Exception as e:
        logger.warning("Error importing '%s': %s", module_path, e)
        return None


def _import_file(file_path: Path, module_name: str) -> ModuleType | None:
    try:
        # Ensure parent directory is in sys.path for relative imports
        parent_dir = str(file_path.parent.parent)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)

        # For packages (e.g. plugins.shell), register parent module stub
        if "." in module_name:
            parent_name = module_name.rsplit(".", 1)[0]
            if parent_name not in sys.modules:
                import types
                parent_mod = types.ModuleType(parent_name)
                parent_mod.__path__ = [str(file_path.parent.parent / parent_name)]
                sys.modules[parent_name] = parent_mod

        spec = importlib.util.spec_from_file_location(
            module_name, file_path,
            submodule_search_locations=[str(file_path.parent)] if file_path.name == "__init__.py" else None,
        )
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        logger.warning("Error loading '%s': %s", file_path, e)
        return None


def _load_from_path(plugin_path: Path, name: str) -> ModuleType | None:
    if not plugin_path.is_dir():
        return None
    path_str = str(plugin_path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
    for submodule in ["src.server", "register", "server"]:
        module = _try_import(submodule)
        if module and find_register(module):
            return module
    return None
