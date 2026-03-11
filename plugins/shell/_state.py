"""Shared state, security checks, and helpers."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

# ── Mutable state ────────────────────────────────────────────────────

_working_dir: Path = Path.cwd()
_allowed_paths: list[Path] = []
_blocked_commands: list[str] = []
_custom_env: dict[str, str] = {}


def set_working_dir(path: Path) -> None:
    global _working_dir
    _working_dir = path.resolve()


def get_working_dir() -> Path:
    return _working_dir


def get_custom_env() -> dict[str, str]:
    return _custom_env


def set_security_boundaries(
    allowed_paths: list[str] | None = None,
    blocked_commands: list[str] | None = None,
) -> None:
    """Set path and command restrictions."""
    global _allowed_paths, _blocked_commands
    _allowed_paths = [Path(p).resolve() for p in (allowed_paths or [])]
    _blocked_commands = [c.strip() for c in (blocked_commands or [])]


# ── Checks ───────────────────────────────────────────────────────────

def resolve_path(path: str) -> Path:
    p = Path(path)
    return p.resolve() if p.is_absolute() else (_working_dir / p).resolve()


def check_path(resolved: Path) -> str | None:
    if not _allowed_paths:
        return None
    for allowed in _allowed_paths:
        try:
            resolved.relative_to(allowed)
            return None
        except ValueError:
            continue
    return f"Error: path outside allowed directories: {resolved}"


def check_command(command: str) -> str | None:
    if not _blocked_commands:
        return None
    cmd = command.strip()
    for blocked in _blocked_commands:
        if cmd.startswith(blocked) or f"| {blocked}" in cmd or f"; {blocked}" in cmd:
            return f"Error: '{blocked}' is blocked"
    return None


# ── Helpers ──────────────────────────────────────────────────────────

def read_text(resolved: Path) -> str | None:
    """Read file as UTF-8, return None on binary."""
    try:
        return resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def run(cmd: list[str], timeout: int = 10) -> str:
    """Run a subprocess, return stdout+stderr."""
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    result = out.stdout.strip()
    if out.stderr.strip():
        result += ("\n[STDERR] " if out.returncode else "\n") + out.stderr.strip()
    if out.returncode and not result:
        result = f"[Exit {out.returncode}]"
    return result or "(no output)"


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} bytes"
    if size < 1048576:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1048576:.1f} MB"
