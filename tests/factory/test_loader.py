"""Tests for plugin loader."""
import types
from mcp_server_factory.loader import find_register, load_module


def test_find_register_present():
    mod = types.ModuleType("fake")
    mod.register = lambda mcp, config: None
    assert find_register(mod) is not None

def test_find_register_missing():
    mod = types.ModuleType("fake")
    assert find_register(mod) is None

def test_find_register_not_callable():
    mod = types.ModuleType("fake")
    mod.register = "not a function"
    assert find_register(mod) is None

def test_load_local_echo_plugin():
    module = load_module("echo", {})
    assert module is not None
    assert find_register(module) is not None

def test_load_unknown_plugin():
    assert load_module("nonexistent_xyz_42", {}) is None
