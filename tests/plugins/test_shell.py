"""Tests for Shell plugin — filesystem, search, execution, proxy integration."""

import sys
from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP

from mcp_server_framework.plugins.loader import add_plugin_dir

_plugins_dir = Path(__file__).parent.parent.parent / "plugins"
add_plugin_dir(_plugins_dir)

if str(_plugins_dir) not in sys.path:
    sys.path.insert(0, str(_plugins_dir))

from shell import tools


class TestFilesystem:
    def test_file_read(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("line1\nline2\nline3\n")
        tools.set_working_dir(tmp_path)
        result = tools.file_read("test.txt")
        assert "line1" in result
        assert "line2" in result

    def test_file_read_not_found(self, tmp_path):
        tools.set_working_dir(tmp_path)
        result = tools.file_read("nope.txt")
        assert "Error" in result

    def test_file_write(self, tmp_path):
        tools.set_working_dir(tmp_path)
        result = tools.file_write("out.txt", "hello\nworld")
        assert "Written" in result
        assert (tmp_path / "out.txt").read_text() == "hello\nworld"

    def test_file_list(self, tmp_path):
        (tmp_path / "a.py").touch()
        (tmp_path / "b.txt").touch()
        tools.set_working_dir(tmp_path)
        result = tools.file_list()
        assert "a.py" in result
        assert "b.txt" in result

    def test_file_delete(self, tmp_path):
        f = tmp_path / "del.txt"
        f.touch()
        tools.set_working_dir(tmp_path)
        result = tools.file_delete("del.txt")
        assert "Deleted" in result
        assert not f.exists()

    def test_str_replace(self, tmp_path):
        f = tmp_path / "rep.txt"
        f.write_text("hello world")
        tools.set_working_dir(tmp_path)
        result = tools.str_replace("rep.txt", "world", "python")
        assert "Replaced" in result
        assert f.read_text() == "hello python"


class TestSearch:
    def test_grep(self, tmp_path):
        (tmp_path / "a.py").write_text("def hello():\n    pass\n")
        (tmp_path / "b.py").write_text("def world():\n    pass\n")
        tools.set_working_dir(tmp_path)
        result = tools.grep("def", ".")
        assert "hello" in result
        assert "world" in result

    def test_glob_search(self, tmp_path):
        (tmp_path / "a.py").touch()
        (tmp_path / "b.txt").touch()
        tools.set_working_dir(tmp_path)
        result = tools.glob_search("*.py")
        assert "a.py" in result
        assert "b.txt" not in result


class TestNavigation:
    def test_cd_and_cwd(self, tmp_path):
        tools.cd(str(tmp_path))
        assert tools.cwd() == str(tmp_path)


class TestSecurityBoundaries:
    def setup_method(self):
        tools.set_security_boundaries()  # reset

    def teardown_method(self):
        tools.set_security_boundaries()  # reset

    def test_allowed_paths_blocks_outside(self, tmp_path):
        allowed = tmp_path / "safe"
        allowed.mkdir()
        tools.set_working_dir(allowed)
        tools.set_security_boundaries(allowed_paths=[str(allowed)])
        result = tools.file_read("/etc/passwd")
        assert "Error" in result
        assert "outside" in result

    def test_allowed_paths_permits_inside(self, tmp_path):
        allowed = tmp_path / "safe"
        allowed.mkdir()
        f = allowed / "ok.txt"
        f.write_text("allowed")
        tools.set_working_dir(allowed)
        tools.set_security_boundaries(allowed_paths=[str(allowed)])
        result = tools.file_read("ok.txt")
        assert "allowed" in result

    def test_blocked_commands(self, tmp_path):
        tools.set_working_dir(tmp_path)
        tools.set_security_boundaries(blocked_commands=["rm", "sudo"])
        result = tools._check_command_allowed("rm -rf /")
        assert "blocked" in result
        result = tools._check_command_allowed("sudo reboot")
        assert "blocked" in result

    def test_blocked_commands_pipe(self, tmp_path):
        tools.set_working_dir(tmp_path)
        tools.set_security_boundaries(blocked_commands=["rm"])
        result = tools._check_command_allowed("ls | rm something")
        assert "blocked" in result

    def test_unblocked_commands_pass(self, tmp_path):
        tools.set_working_dir(tmp_path)
        tools.set_security_boundaries(blocked_commands=["rm"])
        result = tools._check_command_allowed("ls -la")
        assert result is None

    def test_file_delete_respects_boundary(self, tmp_path):
        safe = tmp_path / "safe"
        safe.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret.txt").touch()
        tools.set_working_dir(safe)
        tools.set_security_boundaries(allowed_paths=[str(safe)])
        result = tools.file_delete(str(outside / "secret.txt"))
        assert "Error" in result
        assert (outside / "secret.txt").exists()

    def test_cd_respects_boundary(self, tmp_path):
        safe = tmp_path / "safe"
        safe.mkdir()
        tools.set_working_dir(safe)
        tools.set_security_boundaries(allowed_paths=[str(safe)])
        result = tools.cd("/tmp")
        assert "Error" in result

    def test_no_restrictions_by_default(self, tmp_path):
        tools.set_security_boundaries()
        tools.set_working_dir(tmp_path)
        (tmp_path / "test.txt").write_text("ok")
        result = tools.file_read("test.txt")
        assert "ok" in result


class TestProxyIntegration:
    def test_load_shell_via_proxy(self):
        from mcp_server_proxy.proxy import PluginManager

        mcp = FastMCP("test-shell")
        proxy = PluginManager(mcp, config={})
        result = proxy.load("shell")
        assert result.ok
        assert "shell_file_read" in result.tools
        assert "shell_exec" in result.tools
        assert "shell_grep" in result.tools
        assert "shell_cd" in result.tools
        assert len(result.tools) >= 10

    def test_unload_shell(self):
        from mcp_server_proxy.proxy import PluginManager

        mcp = FastMCP("test-shell-unload")
        proxy = PluginManager(mcp, config={})
        proxy.load("shell")
        result = proxy.unload("shell")
        assert result.ok
