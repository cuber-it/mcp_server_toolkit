"""Git operations."""

from __future__ import annotations

from ._state import run


def git(command: str) -> str:
    """Run git command in working directory."""
    if command.strip().startswith("push"):
        return "Error: git push blocked. Use shell_exec if intended."
    return run(["git"] + command.split(), timeout=30)


def git_status() -> str:
    """Short git status with branch."""
    return git("status --short --branch")


def git_log(count: int = 10) -> str:
    """Recent commits (oneline + graph)."""
    return git(f"log --oneline --graph -n {count}")


def git_diff(staged: bool = False, file: str = "") -> str:
    """Git diff. staged=True for cached changes."""
    cmd = "diff --cached" if staged else "diff"
    if file:
        cmd += f" -- {file}"
    result = git(cmd)
    if len(result) > 15000:
        return result[:15000] + "\n[... truncated]"
    return result
