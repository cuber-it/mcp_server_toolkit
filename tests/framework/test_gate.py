"""Tests für mcp_gate."""
import os, time
import pytest
from mcp_server_framework.gate import Gate, GateLocked
from mcp_server_framework.gate.totp import generate_secret, verify_totp
from mcp_server_framework.gate.state import GateState


# --- TOTP ---

def test_totp_stdlib_valid():
    """stdlib verify_totp against pyotp reference."""
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
    assert not verify_totp("NOTVALID!!!", "abc")


# --- GateState ---

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
    assert s.is_unlocked("shell")  # would have expired without touch


# --- Gate (env backend) ---

SECRET = generate_secret()

def _gate_config(timeout=3600):
    return {
        "secret_backend": "env",
        "groups": {
            "shell": {"timeout": timeout, "secret_ref": "TEST_GATE_SECRET"},
            "vault": {"timeout": 1800, "secret_ref": "TEST_GATE_SECRET"},
        },
    }

@pytest.fixture(autouse=True)
def set_env():
    os.environ["TEST_GATE_SECRET"] = SECRET
    yield
    os.environ.pop("TEST_GATE_SECRET", None)


def test_gate_locked_raises():
    gate = Gate(_gate_config())
    with pytest.raises(GateLocked) as exc:
        gate.check_or_raise("shell")
    assert "shell" in str(exc.value)

def test_gate_unlock_wrong_code():
    gate = Gate(_gate_config())
    ok, msg = gate.unlock("shell", "000000")
    assert not ok
    assert "Invalid" in msg
    assert not gate.state.is_unlocked("shell")

def test_gate_unlock_unknown_group():
    gate = Gate(_gate_config())
    ok, _ = gate.unlock("nonexistent", "123456")
    assert not ok

def test_gate_lockout_after_max_failures():
    from mcp_server_framework.gate.gate import MAX_FAILURES
    gate = Gate(_gate_config())
    for _ in range(MAX_FAILURES):
        gate.unlock("shell", "000000")
    ok, msg = gate.unlock("shell", "000000")
    assert not ok
    assert "locked out" in msg.lower()

def test_gate_manual_lock():
    gate = Gate(_gate_config())
    gate.state.unlock("shell", timeout_seconds=3600)
    msg = gate.lock("shell")
    assert not gate.state.is_unlocked("shell")
    assert "locked" in msg.lower()

def test_gate_lock_all():
    gate = Gate(_gate_config())
    gate.state.unlock("shell", timeout_seconds=3600)
    gate.state.unlock("vault", timeout_seconds=3600)
    gate.lock()
    assert not gate.state.is_unlocked("shell")
    assert not gate.state.is_unlocked("vault")

def test_gate_protect_decorator():
    gate = Gate(_gate_config())
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

def test_gate_status():
    gate = Gate(_gate_config())
    gate.state.unlock("shell", timeout_seconds=3600)
    s = gate.status()
    assert s["shell"]["unlocked"] is True
    assert not s.get("vault", {}).get("unlocked", False)
    assert s["shell"]["remaining_seconds"] > 0
