"""Shell tools — MCP plugin for filesystem, search, and shell operations.

Provides file read/write/list/delete/move/copy, str_replace, grep, glob,
shell execution, and working directory navigation. 15 tools total.

Config keys:
    working_dir: Initial working directory (optional, defaults to cwd)
    timeout: Default shell timeout in seconds (optional, default 120)
"""

from __future__ import annotations

import asyncio

from . import tools


def register(mcp, config: dict) -> None:
    """Register shell tools as MCP tools."""
    if config.get("working_dir"):
        from pathlib import Path
        tools.set_working_dir(Path(config["working_dir"]))

    default_timeout = config.get("timeout", 120)

    @mcp.tool()
    def shell_file_read(path: str, start_line: int = 0, end_line: int = 0) -> str:
        """Read a file with optional line range (1-based). Returns content with line numbers."""
        return tools.file_read(path, start_line or None, end_line or None)

    @mcp.tool()
    def shell_file_write(path: str, content: str) -> str:
        """Write content to a file. Creates directories if needed."""
        return tools.file_write(path, content)

    @mcp.tool()
    def shell_file_list(path: str = ".", recursive: bool = False, show_hidden: bool = False) -> str:
        """List files and directories."""
        return tools.file_list(path, recursive, show_hidden)

    @mcp.tool()
    def shell_file_delete(path: str, recursive: bool = False) -> str:
        """Delete a file or directory. Use recursive=True for directories."""
        return tools.file_delete(path, recursive)

    @mcp.tool()
    def shell_file_move(source: str, destination: str) -> str:
        """Move or rename a file/directory."""
        return tools.file_move(source, destination)

    @mcp.tool()
    def shell_file_copy(source: str, destination: str) -> str:
        """Copy a file or directory."""
        return tools.file_copy(source, destination)

    @mcp.tool()
    def shell_str_replace(path: str, old_string: str, new_string: str) -> str:
        """Replace an exact, unique string in a file."""
        return tools.str_replace(path, old_string, new_string)

    @mcp.tool()
    def shell_grep(
        pattern: str, path: str = ".", recursive: bool = True,
        ignore_case: bool = False, file_pattern: str = "*", max_results: int = 50,
    ) -> str:
        """Search for a pattern (text or regex) in files."""
        return tools.grep(pattern, path, recursive, ignore_case, file_pattern, max_results)

    @mcp.tool()
    def shell_glob(pattern: str, path: str = ".") -> str:
        """Search files by glob pattern (e.g. '**/*.py')."""
        return tools.glob_search(pattern, path)

    @mcp.tool()
    def shell_exec(command: str, timeout: int = default_timeout, working_dir: str = "") -> str:
        """Execute a shell command (bash). Returns stdout, stderr, exit code."""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, tools.shell_exec(command, timeout, working_dir or None))
                return future.result()
        return asyncio.run(tools.shell_exec(command, timeout, working_dir or None))

    @mcp.tool()
    def shell_cd(path: str) -> str:
        """Change working directory."""
        return tools.cd(path)

    @mcp.tool()
    def shell_cwd() -> str:
        """Show current working directory."""
        return tools.cwd()
