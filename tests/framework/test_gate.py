"""Tests für mcp_server_framework.gate."""
import os, stat, time, tempfile
import pytest
from mcp_server_framework.gate import Gate, GateLocked
from mcp_server_framework.gate.totp import generate_secret, verify_totp
from mcp_server_framework.gate.state import GateState
from mcp_server_framework.gate.config import GateConfig
from mcp_server_framework.gate.backends.file import FileBackend


# ---------------------------------------------------------------------------
# TOTP
# ---------------------------------------------------------------------------

def test_totp_stdlib_valid():
    try:
        import pyotp
        secret = generate_secret()
        code = pyotp.TOTP(secret).now()
        assert verify_totp(secret, code)
    except ImportError:
        pytest.skip("pyotp not installed")

def test_totp_invalid_code():
    assert not verify_totp(generate_secret(), "000000")

def test_totp_bad_input():
    assert not verify_totp("NOT-VALID!!!", "abc")


# ---------------------------------------------------------------------------
# GateState
# ---------------------------------------------------------------------------

def test_state_initially_locked():
    assert not GateState().is_unlocked("shell")

def test_state_unlock_lock():
    s = GateState()
    s.unlock("shell", timeout_seconds=60)
    assert s.is_unlocked("shell")
    s.lock("shell")
    assert not s.is_unlocked("shell")

def test_state_lock_all():
    s = GateState()
    s.unlock("shell", timeout_seconds=60)
    s.unlock("vault", timeout_seconds=60)
    s.lock_all()
    assert not s.is_unlocked("shell")
    assert not s.is_unlocked("vault")

def test_state_timeout():
    s = GateState()
    s.unlock("shell", timeout_seconds=1)
    assert s.is_unlocked("shell")
    time.sleep(2)
    assert not s.is_unlocked("shell")

def test_state_touch_resets_timer():
    s = GateState()
    s.unlock("shell", timeout_seconds=2)
    time.sleep(1)
    s.touch("shell")
    time.sleep(1)
    assert s.is_unlocked("shell")


# ---------------------------------------------------------------------------
# GateConfig
# ---------------------------------------------------------------------------

def test_config_enabled_default():
    cfg = GateConfig.from_dict({})
    assert cfg.enabled is True

def test_config_disabled():
    cfg = GateConfig.from_dict({"enabled": False})
    assert cfg.enabled is False

def test_config_group_defaults():
    cfg = GateConfig.from_dict({"groups": {"shell": {}}})
    assert cfg.groups["shell"].timeout == 7200
    assert cfg.groups["shell"].secret_ref == "shell"  # defaults to group name

def test_config_group_for_tool():
    cfg = GateConfig.from_dict({
        "groups": {"shell": {"tools": ["shell_exec", "shell_file_read"]}}
    })
    assert cfg.group_for_tool("shell_exec") == "shell"
    assert cfg.group_for_tool("vault_read") is None


# ---------------------------------------------------------------------------
# FileBackend
# ---------------------------------------------------------------------------

def test_file_backend_read(tmp_path):
    f = tmp_path / "secrets"
    f.write_text("shell=JBSWY3DPEHPK3PXP\n# comment\nvault=JBSWY3DPEHPK3PXQ\n")
    backend = FileBackend(str(f))
    assert backend.get("shell") == "JBSWY3DPEHPK3PXP"
    assert backend.get("vault") == "JBSWY3DPEHPK3PXQ"

def test_file_backend_missing_key(tmp_path):
    f = tmp_path / "secrets"
    f.write_text("shell=ABC\n")
    backend = FileBackend(str(f))
    with pytest.raises(RuntimeError, match="not found"):
        backend.get("vault")

def test_file_backend_missing_file():
    backend = FileBackend("/nonexistent/path")
    with pytest.raises(RuntimeError, match="not found"):
        backend.get("shell")


# ---------------------------------------------------------------------------
# Gate — env backend fixture
# ---------------------------------------------------------------------------

SECRET = generate_secret()

def _cfg(timeout=3600, enabled=True):
    return {
        "enabled": enabled,
        "secret_backend": "env",
        "groups": {
            "shell": {"timeout": timeout, "secret_ref": "TEST_GATE_SECRET"},
            "vault": {"timeout": 1800,   "secret_ref": "TEST_GATE_SECRET"},
        },
    }

@pytest.fixture(autouse=True)
def set_env():
    os.environ["TEST_GATE_SECRET"] = SECRET
    yield
    os.environ.pop("TEST_GATE_SECRET", None)


# ---------------------------------------------------------------------------
# Gate — disabled mode
# ---------------------------------------------------------------------------

def test_gate_disabled_no_raise():
    gate = Gate(_cfg(enabled=False))
    gate.check_or_raise("shell")   # must not raise

def test_gate_disabled_protect_noop():
    gate = Gate(_cfg(enabled=False))
    log = []

    @gate.protect("shell")
    def my_tool():
        log.append(1)

    my_tool()
    assert log == [1]

def test_gate_disabled_status_empty():
    gate = Gate(_cfg(enabled=False))
    assert gate.status() == {}


# ---------------------------------------------------------------------------
# Gate — enabled mode
# ---------------------------------------------------------------------------

def test_gate_locked_raises():
    gate = Gate(_cfg())
    with pytest.raises(GateLocked) as exc:
        gate.check_or_raise("shell")
    assert "shell" in str(exc.value)

def test_gate_unlock_wrong_code():
    gate = Gate(_cfg())
    ok, msg = gate.unlock("shell", "000000")
    assert not ok
    assert "Invalid" in msg
    assert not gate.state.is_unlocked("shell")

def test_gate_unlock_unknown_group():
    gate = Gate(_cfg())
    ok, _ = gate.unlock("nonexistent", "123456")
    assert not ok

def test_gate_lockout_after_max_failures():
    from mcp_server_framework.gate.gate import MAX_FAILURES
    gate = Gate(_cfg())
    for _ in range(MAX_FAILURES):
        gate.unlock("shell", "000000")
    ok, msg = gate.unlock("shell", "000000")
    assert not ok
    assert "locked out" in msg.lower()

def test_gate_manual_lock():
    gate = Gate(_cfg())
    gate.state.unlock("shell", timeout_seconds=3600)
    msg = gate.lock("shell")
    assert not gate.state.is_unlocked("shell")
    assert "locked" in msg.lower()

def test_gate_lock_all():
    gate = Gate(_cfg())
    gate.state.unlock("shell", timeout_seconds=3600)
    gate.state.unlock("vault", timeout_seconds=3600)
    gate.lock()
    assert not gate.state.is_unlocked("shell")
    assert not gate.state.is_unlocked("vault")

def test_gate_protect_decorator():
    gate = Gate(_cfg())
    log = []

    @gate.protect("shell")
    def my_tool(x):
        log.append(x)
        return x * 2

    with pytest.raises(GateLocked):
        my_tool(1)

    gate.state.unlock("shell", timeout_seconds=3600)
    assert my_tool(3) == 6
    assert log == [3]

def test_gate_touch_resets_timer():
    gate = Gate(_cfg(timeout=2))
    gate.state.unlock("shell", timeout_seconds=2)
    time.sleep(1)
    gate.touch("shell")
    time.sleep(1)
    assert gate.state.is_unlocked("shell")

def test_gate_status_unlocked():
    gate = Gate(_cfg())
    gate.state.unlock("shell", timeout_seconds=3600)
    s = gate.status()
    assert s["shell"]["unlocked"] is True
    assert s["shell"]["remaining_seconds"] > 0

def test_gate_status_locked():
    gate = Gate(_cfg())
    s = gate.status()
    # vault not yet in state (never touched) — that's fine
    assert not s.get("shell", {}).get("unlocked", False)
