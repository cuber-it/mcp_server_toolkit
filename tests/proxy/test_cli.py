"""Tests for proxy CLI argument parsing and auto-detection."""

from unittest.mock import patch, MagicMock

import pytest

from mcp_server_proxy.cli import parse_args, DEFAULT_MGMT_PORT
from mcp_server_proxy.client import is_proxy_running


class TestParseArgs:
    def test_no_args_is_serve(self):
        with patch("sys.argv", ["mcp-proxy"]):
            args = parse_args()
            assert args.command is None

    def test_serve_explicit(self):
        with patch("sys.argv", ["mcp-proxy", "serve"]):
            args = parse_args()
            assert args.command == "serve"

    def test_serve_with_autoload(self):
        with patch("sys.argv", ["mcp-proxy", "serve", "--autoload", "echo", "greet"]):
            args = parse_args()
            assert args.command == "serve"
            assert args.autoload == ["echo", "greet"]

    def test_serve_with_http(self):
        with patch("sys.argv", ["mcp-proxy", "serve", "--http", "12200"]):
            args = parse_args()
            assert args.http == 12200

    def test_serve_with_mgmt_port(self):
        with patch("sys.argv", ["mcp-proxy", "serve", "--mgmt-port", "9999"]):
            args = parse_args()
            assert args.mgmt_port == 9999

    def test_load_subcommand(self):
        with patch("sys.argv", ["mcp-proxy", "load", "echo"]):
            args = parse_args()
            assert args.command == "load"
            assert args.plugin == "echo"

    def test_unload_subcommand(self):
        with patch("sys.argv", ["mcp-proxy", "unload", "echo"]):
            args = parse_args()
            assert args.command == "unload"
            assert args.plugin == "echo"

    def test_reload_subcommand(self):
        with patch("sys.argv", ["mcp-proxy", "reload", "echo"]):
            args = parse_args()
            assert args.command == "reload"
            assert args.plugin == "echo"

    def test_status_subcommand(self):
        with patch("sys.argv", ["mcp-proxy", "status"]):
            args = parse_args()
            assert args.command == "status"

    def test_status_with_custom_port(self):
        with patch("sys.argv", ["mcp-proxy", "status", "--mgmt-port", "8888"]):
            args = parse_args()
            assert args.command == "status"
            assert args.mgmt_port == 8888

    def test_default_mgmt_port(self):
        with patch("sys.argv", ["mcp-proxy", "load", "echo"]):
            args = parse_args()
            assert args.mgmt_port == DEFAULT_MGMT_PORT

    def test_top_level_autoload(self):
        with patch("sys.argv", ["mcp-proxy", "--autoload", "echo"]):
            args = parse_args()
            assert args.command is None
            assert args.autoload == ["echo"]

    def test_plugin_dir(self):
        with patch("sys.argv", ["mcp-proxy", "serve", "--plugin-dir", "/tmp/plugins"]):
            args = parse_args()
            assert len(args.plugin_dir) == 1


class TestAutoDetection:
    def test_not_running(self):
        assert not is_proxy_running(19999)

    @patch("mcp_server_proxy.client.httpx.get")
    def test_running(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp
        assert is_proxy_running(12299)

    @patch("mcp_server_proxy.client.httpx.get", side_effect=Exception("fail"))
    def test_error_means_not_running(self, mock_get):
        assert not is_proxy_running(12299)
