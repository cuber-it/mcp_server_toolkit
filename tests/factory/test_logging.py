"""Tests for logging plugin."""
from mcp_server_factory.plugins.logging import LogSettings


def test_log_on_off():
    settings = LogSettings()
    assert "ON" in settings.set_logging(True)
    assert settings.log_enabled is True
    assert "OFF" in settings.set_logging(False)
    assert settings.log_enabled is False

def test_transcript_on_off(tmp_path, monkeypatch):
    import mcp_server_factory.plugins.logging as log_mod
    monkeypatch.setattr(log_mod, "TRANSCRIPT_DIR", tmp_path)
    settings = LogSettings()
    assert "ON" in settings.start_transcript()
    assert settings.transcript_enabled is True
    assert settings.transcript_file.exists()
    assert "OFF" in settings.stop_transcript()
    assert settings.transcript_enabled is False

def test_log_call_writes_to_file(tmp_path):
    settings = LogSettings()
    settings.log_file = tmp_path / "test.log"
    settings.log_enabled = True
    settings.log_call("my_tool", {"param": "value"}, "result", True)
    content = settings.log_file.read_text()
    assert "OK" in content and "my_tool" in content

def test_log_call_noop_when_disabled():
    settings = LogSettings()
    settings.log_call("my_tool", {}, "result", True)  # should not raise

def test_transcript_writes_markdown(tmp_path, monkeypatch):
    import mcp_server_factory.plugins.logging as log_mod
    monkeypatch.setattr(log_mod, "TRANSCRIPT_DIR", tmp_path)
    settings = LogSettings()
    settings.start_transcript()
    settings.log_call("my_tool", {"x": "1"}, "done", True)
    content = settings.transcript_file.read_text()
    assert "my_tool" in content and "✓" in content

def test_logging_tools_registered():
    from mcp.server.fastmcp import FastMCP
    from mcp_server_factory.factory import Factory
    mcp = FastMCP("Test")
    config = {}
    factory = Factory(mcp, config)
    config["_factory"] = factory
    factory.load_internals()
    plugin = factory.plugins["factory_logging"]
    assert "factory__log" in plugin.tools
    assert "factory__transcript" in plugin.tools
    assert len(plugin.tools) == 2
