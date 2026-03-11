"""Shell execution: exec, cd, cwd, which, env."""

from __future__ import annotations

import asyncio
import os
import shutil
import signal

from ._state import check_command, check_path, get_custom_env, get_working_dir, resolve_path, set_working_dir


async def shell_exec(command: str, timeout: int = 120, working_dir: str | None = None) -> str:
    """Execute a shell command. Returns stdout, stderr, exit code."""
    if err := check_command(command):
        return err
    cwd = resolve_path(working_dir) if working_dir else get_working_dir()
    if err := check_path(cwd):
        return err
    if not cwd.is_dir():
        return f"Error: directory not found: {cwd}"
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
            return f"$ {command}\n\nTimeout after {timeout}s"
        parts = [f"$ {command}"]
        if stdout:
            parts.append(stdout.decode("utf-8", errors="replace"))
        if stderr:
            parts.append(f"[STDERR]\n{stderr.decode('utf-8', errors='replace')}")
        if proc.returncode:
            parts.append(f"[Exit {proc.returncode}]")
        if not stdout and not stderr:
            parts.append("(no output)")
        return "\n".join(parts)
    except Exception as e:
        return f"$ {command}\n\nError: {e}"


def cd(path: str) -> str:
    """Change working directory."""
    resolved = resolve_path(path)
    if err := check_path(resolved):
        return err
    if not resolved.is_dir():
        return f"Error: not a directory: {resolved}"
    set_working_dir(resolved)
    return str(resolved)


def cwd() -> str:
    """Current working directory."""
    return str(get_working_dir())


def which(command: str) -> str:
    """Full path of a command."""
    return shutil.which(command) or f"'{command}' not found in PATH"


def env(name: str = "") -> str:
    """Show environment variables. Without name: custom vars only."""
    custom = get_custom_env()
    if name:
        if name in custom:
            return f"{name}={custom[name]} (custom)"
        val = os.environ.get(name)
        return f"{name}={val}" if val else f"'{name}' not set"
    if not custom:
        return "No custom variables set."
    return "\n".join(f"  {k}={v}" for k, v in sorted(custom.items()))


def set_env(name: str, value: str = "") -> str:
    """Set or delete (value='') an environment variable."""
    custom = get_custom_env()
    if not value:
        removed = custom.pop(name, None)
        return f"Deleted '{name}'" if removed else f"'{name}' was not set"
    custom[name] = value
    os.environ[name] = value
    return f"{name}={value}"
