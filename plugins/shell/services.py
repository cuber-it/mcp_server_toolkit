"""systemd service management and Python packages."""

from __future__ import annotations

import shutil

from ._state import run


# ── systemd ──────────────────────────────────────────────────────────

def systemctl(action: str, service: str = "", user: bool = True) -> str:
    """Manage systemd services: status, start, stop, restart, enable, disable, list, logs."""
    base = ["systemctl", "--user"] if user else ["systemctl"]
    if action == "list":
        return run(base + ["list-units", "--type=service", "--no-pager"])
    if action == "logs":
        if not service:
            return "Error: service name required"
        flag = "--user-unit" if user else "--unit"
        return run(["journalctl", flag, service, "-n", "50", "--no-pager"])
    if not service:
        return "Error: service name required"
    valid = ("status", "start", "stop", "restart", "enable", "disable")
    if action not in valid:
        return f"Error: unknown action. Use: {', '.join(valid)}, list, logs"
    return run(base + [action, service, "--no-pager"])


# ── Packages ─────────────────────────────────────────────────────────

def _python() -> str:
    return shutil.which("python3") or "python3"


def pip_list(filter: str = "") -> str:
    """Installed Python packages."""
    result = run([_python(), "-m", "pip", "list", "--format=columns"], timeout=30)
    if not filter:
        return result
    lines = result.splitlines()
    header = lines[:2]
    matched = [ln for ln in lines[2:] if filter.lower() in ln.lower()]
    return "\n".join(header + matched) if matched else f"No packages matching '{filter}'"


def pip_install(package: str, upgrade: bool = False) -> str:
    """Install Python package."""
    cmd = [_python(), "-m", "pip", "install"]
    if upgrade:
        cmd.append("--upgrade")
    cmd.append(package)
    return run(cmd, timeout=120)
