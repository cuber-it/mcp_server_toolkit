"""Shell tools — MCP plugin for workstation access.

Provides filesystem, search, shell execution, git, systemd, HTTP,
JSON query, package management, and system diagnostics.

Config keys:
    working_dir: Initial working directory (optional, defaults to cwd)
    timeout: Default shell timeout in seconds (optional, default 120)
    allowed_paths: Restrict filesystem access (optional)
    blocked_commands: Block dangerous commands (optional)
"""

from __future__ import annotations

import asyncio
import functools

from . import tools


def register(mcp, config: dict) -> None:
    """Register shell tools as MCP tools."""
    if config.get("working_dir"):
        from pathlib import Path
        tools.set_working_dir(Path(config["working_dir"]))

    tools.set_security_boundaries(
        allowed_paths=config.get("allowed_paths"),
        blocked_commands=config.get("blocked_commands"),
    )

    default_timeout = config.get("timeout", 120)

    # Auto-record all tool calls in history
    _original_tool = mcp.tool

    def _recording_tool(**kwargs):
        def decorator(fn):
            name = fn.__name__.replace("shell_", "")

            @functools.wraps(fn)
            def wrapper(*args, **kw):
                result = fn(*args, **kw)
                args_str = ", ".join(
                    [repr(a) for a in args] + [f"{k}={v!r}" for k, v in kw.items()]
                )
                tools._record(name, args_str, str(result))
                return result

            return _original_tool(**kwargs)(wrapper)
        return decorator

    tool = _recording_tool

    # --- Filesystem ---

    @tool()
    def shell_file_read(path: str, start_line: int = 0, end_line: int = 0) -> str:
        """Read a file with optional line range (1-based). Returns content with line numbers."""
        return tools.file_read(path, start_line or None, end_line or None)

    @tool()
    def shell_file_write(path: str, content: str) -> str:
        """Write content to a file. Creates directories if needed."""
        return tools.file_write(path, content)

    @tool()
    def shell_file_append(path: str, content: str) -> str:
        """Append content to a file. Creates file and directories if needed."""
        return tools.file_append(path, content)

    @tool()
    def shell_file_list(path: str = ".", recursive: bool = False, show_hidden: bool = False) -> str:
        """List files and directories."""
        return tools.file_list(path, recursive, show_hidden)

    @tool()
    def shell_file_delete(path: str, recursive: bool = False) -> str:
        """Delete a file or directory. Use recursive=True for directories."""
        return tools.file_delete(path, recursive)

    @tool()
    def shell_file_move(source: str, destination: str) -> str:
        """Move or rename a file/directory."""
        return tools.file_move(source, destination)

    @tool()
    def shell_file_copy(source: str, destination: str) -> str:
        """Copy a file or directory."""
        return tools.file_copy(source, destination)

    @tool()
    def shell_file_info(path: str) -> str:
        """Show file metadata: size, permissions, owner, timestamps."""
        return tools.file_info(path)

    @tool()
    def shell_head(path: str, lines: int = 20) -> str:
        """Show first N lines of a file (default 20)."""
        return tools.head(path, lines)

    @tool()
    def shell_tail(path: str, lines: int = 20) -> str:
        """Show last N lines of a file (default 20)."""
        return tools.tail(path, lines)

    @tool()
    def shell_tree(path: str = ".", max_depth: int = 3, show_hidden: bool = False) -> str:
        """Show directory tree as ASCII art."""
        return tools.tree(path, max_depth, show_hidden)

    # --- Editor ---

    @tool()
    def shell_str_replace(path: str, old_string: str, new_string: str) -> str:
        """Replace an exact, unique string in a file."""
        return tools.str_replace(path, old_string, new_string)

    @tool()
    def shell_diff_preview(path: str, old_string: str, new_string: str = "", context_lines: int = 3) -> str:
        """Show unified diff preview before applying str_replace."""
        return tools.diff_preview(path, old_string, new_string, context_lines)

    @tool()
    def shell_find_replace(pattern: str, replacement: str, path: str = ".", file_pattern: str = "*", dry_run: bool = True) -> str:
        """Find and replace text across files. Default: dry_run preview. Set dry_run=False to apply."""
        return tools.find_replace(pattern, replacement, path, file_pattern, dry_run)

    # --- Search ---

    @tool()
    def shell_grep(
        pattern: str, path: str = ".", recursive: bool = True,
        ignore_case: bool = False, file_pattern: str = "*", max_results: int = 50,
    ) -> str:
        """Search for a pattern (text or regex) in files."""
        return tools.grep(pattern, path, recursive, ignore_case, file_pattern, max_results)

    @tool()
    def shell_glob(pattern: str, path: str = ".") -> str:
        """Search files by glob pattern (e.g. '**/*.py')."""
        return tools.glob_search(pattern, path)

    # --- Shell ---

    @tool()
    def shell_exec(command: str, timeout: int = default_timeout, working_dir: str = "") -> str:
        """Execute a shell command (bash). Returns stdout, stderr, exit code."""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, tools.shell_exec(command, timeout, working_dir or None))
                return future.result()
        return asyncio.run(tools.shell_exec(command, timeout, working_dir or None))

    @tool()
    def shell_cd(path: str) -> str:
        """Change working directory."""
        return tools.cd(path)

    @tool()
    def shell_cwd() -> str:
        """Show current working directory."""
        return tools.cwd()

    @tool()
    def shell_which(command: str) -> str:
        """Find the full path of a command (like 'which' in shell)."""
        return tools.which(command)

    @tool()
    def shell_env(name: str = "") -> str:
        """Show environment variables. Without name: show custom vars only."""
        return tools.env(name)

    @tool()
    def shell_set_env(name: str, value: str = "") -> str:
        """Set or delete an environment variable for shell_exec calls."""
        return tools.set_env(name, value)

    # --- System Diagnostics ---

    @tool()
    def shell_ps(filter: str = "") -> str:
        """Show running processes. Optional filter by name or PID."""
        return tools.ps(filter)

    @tool()
    def shell_sysinfo() -> str:
        """System overview: OS, CPU, memory, disk, uptime, load."""
        return tools.sysinfo()

    @tool()
    def shell_port_check(port: int = 0, host: str = "127.0.0.1") -> str:
        """Check what's listening on a port, or list all listening ports."""
        return tools.port_check(port, host)

    @tool()
    def shell_disk_usage(path: str = ".") -> str:
        """Show disk usage of directory and its subdirectories."""
        return tools.disk_usage(path)

    # --- HTTP ---

    @tool()
    def shell_http_request(url: str, method: str = "GET", data: str = "", headers: str = "") -> str:
        """Make HTTP request (like curl). Headers as 'Key: Value' per line."""
        return tools.http_request(url, method, data, headers)

    @tool()
    def shell_json_query(path: str, query: str = "") -> str:
        """Read JSON file and extract data. Query uses dot notation: 'key.subkey.0.name'."""
        return tools.json_query(path, query)

    # --- Git ---

    @tool()
    def shell_git(command: str) -> str:
        """Run a git command. Examples: 'status', 'log --oneline -10', 'diff', 'branch -a'."""
        return tools.git(command)

    @tool()
    def shell_git_status() -> str:
        """Quick git status: branch, staged, modified, untracked."""
        return tools.git_status()

    @tool()
    def shell_git_log(count: int = 10) -> str:
        """Recent git commits (oneline format with graph)."""
        return tools.git_log(count)

    @tool()
    def shell_git_diff(staged: bool = False, file: str = "") -> str:
        """Show git diff. staged=True for cached changes. Optional specific file."""
        return tools.git_diff(staged, file)

    # --- systemd ---

    @tool()
    def shell_systemctl(action: str, service: str = "", user: bool = True) -> str:
        """Manage systemd services. Actions: status, start, stop, restart, enable, disable, list, logs."""
        return tools.systemctl(action, service, user)

    # --- Package Management ---

    @tool()
    def shell_pip_list(filter: str = "") -> str:
        """List installed Python packages. Optional filter by name."""
        return tools.pip_list(filter)

    @tool()
    def shell_pip_install(package: str, upgrade: bool = False) -> str:
        """Install a Python package. Use upgrade=True to upgrade existing."""
        return tools.pip_install(package, upgrade)

    # --- History ---

    @tool()
    def shell_history(count: int = 20, filter: str = "", full: bool = False) -> str:
        """Show tool call history. filter by tool/args. full=True shows complete results."""
        return tools.history(count, filter, full)
