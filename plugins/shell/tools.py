"""Shell tool functions — pure Python, no MCP dependency.

Provides filesystem operations, shell execution, and search.
All path operations are relative to a configurable working directory.

Security boundaries (optional, via config):
    allowed_paths: list of allowed base directories (default: no restriction)
    blocked_commands: list of blocked shell command prefixes (default: none)
"""

from __future__ import annotations

import asyncio
import os
import re
import signal
import shutil
from pathlib import Path
from typing import Any


# --- State ---

_working_dir: Path = Path.cwd()
_allowed_paths: list[Path] = []
_blocked_commands: list[str] = []


def set_working_dir(path: Path) -> None:
    global _working_dir
    _working_dir = path.resolve()


def set_security_boundaries(
    allowed_paths: list[str] | None = None,
    blocked_commands: list[str] | None = None,
) -> None:
    """Configure security boundaries for shell operations."""
    global _allowed_paths, _blocked_commands
    _allowed_paths = [Path(p).resolve() for p in (allowed_paths or [])]
    _blocked_commands = [c.strip() for c in (blocked_commands or [])]


def get_working_dir() -> Path:
    return _working_dir


def _check_path_allowed(resolved: Path) -> str | None:
    """Return error message if path is outside allowed boundaries."""
    if not _allowed_paths:
        return None
    for allowed in _allowed_paths:
        try:
            resolved.relative_to(allowed)
            return None
        except ValueError:
            continue
    return f"Error: Path '{resolved}' is outside allowed directories: {[str(p) for p in _allowed_paths]}"


def _check_command_allowed(command: str) -> str | None:
    """Return error message if command is blocked."""
    if not _blocked_commands:
        return None
    cmd_stripped = command.strip()
    for blocked in _blocked_commands:
        if cmd_stripped.startswith(blocked) or f"| {blocked}" in cmd_stripped or f"; {blocked}" in cmd_stripped:
            return f"Error: Command '{blocked}' is blocked by security policy"
    return None


def resolve_path(path: str) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p.resolve()
    return (_working_dir / p).resolve()


# --- Filesystem ---

def file_read(path: str, start_line: int | None = None, end_line: int | None = None) -> str:
    """Read a file with optional line range. Returns content with line numbers."""
    resolved = resolve_path(path)
    if err := _check_path_allowed(resolved):
        return err
    if not resolved.exists():
        return f"Error: File not found: {resolved}"
    if not resolved.is_file():
        return f"Error: Not a file: {resolved}"
    try:
        content = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"Binary file: {resolved} ({resolved.stat().st_size:,} bytes)"

    lines = content.splitlines()
    total = len(lines)
    start = (start_line or 1) - 1
    end = end_line or min(total, 500)
    selected = lines[start:end]

    numbered = [f"{i + start + 1:>5} | {line}" for i, line in enumerate(selected)]
    result = "\n".join(numbered)
    if not start_line and not end_line and total > 500:
        result += f"\n[File has {total} lines. Use start_line/end_line for more.]"
    return result


def file_write(path: str, content: str) -> str:
    """Write content to a file. Creates parent directories if needed."""
    resolved = resolve_path(path)
    if err := _check_path_allowed(resolved):
        return err
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    return f"Written: {resolved} ({len(content.splitlines())} lines)"


def file_list(path: str = ".", recursive: bool = False, show_hidden: bool = False) -> str:
    """List files and directories."""
    resolved = resolve_path(path)
    if err := _check_path_allowed(resolved):
        return err
    if not resolved.is_dir():
        return f"Error: Not a directory: {resolved}"

    lines = [str(resolved)]
    items = sorted(resolved.rglob("*") if recursive else resolved.iterdir())
    for item in items[:200]:
        if not show_hidden and item.name.startswith("."):
            continue
        rel = item.relative_to(resolved)
        if item.is_dir():
            lines.append(f"  {rel}/")
        else:
            lines.append(f"  {rel}  ({item.stat().st_size:,} bytes)")
    if len(items) > 200:
        lines.append(f"[... {len(items) - 200} more entries]")
    return "\n".join(lines)


def file_delete(path: str, recursive: bool = False) -> str:
    """Delete a file or directory."""
    resolved = resolve_path(path)
    if err := _check_path_allowed(resolved):
        return err
    if not resolved.exists():
        return f"Error: Not found: {resolved}"
    if resolved.is_dir():
        if not recursive:
            return f"Error: {resolved} is a directory. Use recursive=True."
        shutil.rmtree(resolved)
    else:
        resolved.unlink()
    return f"Deleted: {resolved}"


def file_move(source: str, destination: str) -> str:
    """Move or rename a file/directory."""
    src, dst = resolve_path(source), resolve_path(destination)
    if err := _check_path_allowed(src):
        return err
    if err := _check_path_allowed(dst):
        return err
    if not src.exists():
        return f"Error: Not found: {src}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return f"Moved: {src} -> {dst}"


def file_copy(source: str, destination: str) -> str:
    """Copy a file or directory."""
    src, dst = resolve_path(source), resolve_path(destination)
    if err := _check_path_allowed(src):
        return err
    if err := _check_path_allowed(dst):
        return err
    if not src.exists():
        return f"Error: Not found: {src}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(str(src), str(dst))
    else:
        shutil.copy2(str(src), str(dst))
    return f"Copied: {src} -> {dst}"


def str_replace(path: str, old_string: str, new_string: str) -> str:
    """Replace exact string in a file. old_string must be unique."""
    resolved = resolve_path(path)
    if err := _check_path_allowed(resolved):
        return err
    if not resolved.is_file():
        return f"Error: Not a file: {resolved}"
    content = resolved.read_text(encoding="utf-8")
    count = content.count(old_string)
    if count == 0:
        return f"Error: String not found in {resolved}"
    if count > 1:
        return f"Error: String appears {count} times. Must be unique."
    new_content = content.replace(old_string, new_string, 1)
    resolved.write_text(new_content, encoding="utf-8")
    return f"Replaced in {resolved}"


# --- Search ---

def grep(
    pattern: str, path: str = ".", recursive: bool = True,
    ignore_case: bool = False, file_pattern: str = "*", max_results: int = 50,
) -> str:
    """Search for a pattern in files. Returns matching lines with context."""
    resolved = resolve_path(path)
    if not resolved.exists():
        return f"Error: Not found: {resolved}"

    flags = re.IGNORECASE if ignore_case else 0
    try:
        regex = re.compile(pattern, flags)
    except re.error as e:
        return f"Error: Invalid regex: {e}"

    if resolved.is_file():
        files = [resolved]
    else:
        files = sorted(resolved.rglob(file_pattern) if recursive else resolved.glob(file_pattern))
        files = [f for f in files if f.is_file() and not any(p.startswith(".") for p in f.parts)]

    results = []
    for f in files:
        try:
            content = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        for i, line in enumerate(content.splitlines(), 1):
            if regex.search(line):
                rel = f.relative_to(resolved) if resolved.is_dir() else f.name
                results.append(f"{rel}:{i}: {line}")
                if len(results) >= max_results:
                    break
        if len(results) >= max_results:
            break

    if not results:
        return f"No matches for '{pattern}'"
    header = f"Matches for '{pattern}': {len(results)} results\n"
    return header + "\n".join(results)


def glob_search(pattern: str, path: str = ".") -> str:
    """Search files by glob pattern."""
    resolved = resolve_path(path)
    if not resolved.is_dir():
        return f"Error: Not a directory: {resolved}"
    matches = sorted(resolved.glob(pattern))[:100]
    if not matches:
        return f"No matches for '{pattern}'"
    lines = [f"Matches for '{pattern}':"]
    for m in matches:
        lines.append(f"  {m.relative_to(resolved)}")
    return "\n".join(lines)


# --- Shell Execution ---

async def shell_exec(command: str, timeout: int = 120, working_dir: str | None = None) -> str:
    """Execute a shell command. Returns stdout, stderr, and exit code."""
    if err := _check_command_allowed(command):
        return err
    cwd = resolve_path(working_dir) if working_dir else _working_dir
    if err := _check_path_allowed(cwd):
        return err
    if not cwd.is_dir():
        return f"Error: Working directory not found: {cwd}"

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            start_new_session=True,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            os.killpg(proc.pid, signal.SIGTERM)
            await proc.wait()
            return f"$ {command}\n\nError: Timeout after {timeout}s"

        parts = [f"$ {command}"]
        if stdout:
            parts.append(stdout.decode("utf-8", errors="replace"))
        if stderr:
            parts.append(f"[STDERR]\n{stderr.decode('utf-8', errors='replace')}")
        if proc.returncode != 0:
            parts.append(f"[Exit Code: {proc.returncode}]")
        if not stdout and not stderr:
            parts.append("(no output)")
        return "\n".join(parts)
    except Exception as e:
        return f"$ {command}\n\nError: {e}"


# --- Navigation ---

def cd(path: str) -> str:
    """Change working directory."""
    resolved = resolve_path(path)
    if err := _check_path_allowed(resolved):
        return err
    if not resolved.is_dir():
        return f"Error: Not a directory: {resolved}"
    set_working_dir(resolved)
    return str(resolved)


def cwd() -> str:
    """Show current working directory."""
    return str(_working_dir)
