"""System diagnostics: ps, sysinfo, ports, disk usage."""

from __future__ import annotations

import os
import platform

from ._state import check_path, resolve_path, run


def ps(filter: str = "") -> str:
    """Running processes. Optional filter by name."""
    lines = run(["ps", "aux", "--sort=-pcpu"], timeout=5).splitlines()
    if filter:
        header = lines[0] if lines else ""
        matched = [ln for ln in lines[1:] if filter.lower() in ln.lower()][:50]
        return (header + "\n" + "\n".join(matched)) if matched else f"No processes matching '{filter}'"
    return "\n".join(lines[:31])


def sysinfo() -> str:
    """System overview: OS, CPU, memory, disk, uptime, load."""
    parts = [
        f"Host: {platform.node()}",
        f"OS: {platform.system()} {platform.release()}",
    ]
    try:
        with open("/proc/cpuinfo") as f:
            cpus = [ln for ln in f if ln.startswith("model name")]
        if cpus:
            parts.append(f"CPU: {cpus[0].split(':')[1].strip()} ({len(cpus)} cores)")
    except OSError:
        pass
    try:
        with open("/proc/meminfo") as f:
            mem = {}
            for ln in f:
                k, v = ln.split(":")
                mem[k.strip()] = int(v.strip().split()[0])
        parts.append(f"Memory: {mem.get('MemAvailable', 0) // 1024}M free / {mem.get('MemTotal', 0) // 1024}M")
    except OSError:
        pass
    try:
        st = os.statvfs("/")
        parts.append(f"Disk: {st.f_bavail * st.f_frsize / 1024**3:.1f}G free / {st.f_blocks * st.f_frsize / 1024**3:.1f}G")
    except OSError:
        pass
    try:
        with open("/proc/uptime") as f:
            secs = int(float(f.read().split()[0]))
        d, r = divmod(secs, 86400)
        h, r = divmod(r, 3600)
        parts.append(f"Uptime: {d}d {h}h {r // 60}m")
    except OSError:
        pass
    try:
        l1, l5, l15 = os.getloadavg()
        parts.append(f"Load: {l1:.2f} {l5:.2f} {l15:.2f}")
    except OSError:
        pass
    return "\n".join(parts)


def port_check(port: int = 0) -> str:
    """What's listening on a port (or all ports if port=0)."""
    cmd = ["ss", "-tlnp"]
    if port:
        cmd.append(f"sport = :{port}")
    result = run(cmd, timeout=5)
    if port and len(result.splitlines()) <= 1:
        return f"Nothing on port {port}"
    return result


def disk_usage(path: str = ".") -> str:
    """Disk usage of directory."""
    resolved = resolve_path(path)
    if err := check_path(resolved):
        return err
    if not resolved.is_dir():
        return f"Error: not a directory: {resolved}"
    return run(["du", "-sh", "--max-depth=1", str(resolved)], timeout=30)
