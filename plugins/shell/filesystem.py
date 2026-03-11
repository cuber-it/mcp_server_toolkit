"""Filesystem operations: read, write, copy, move, delete, list, tree."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from ._state import check_path, format_size, read_text, resolve_path


def file_read(path: str, start_line: int | None = None, end_line: int | None = None) -> str:
    """Read file with optional line range (1-based). Returns numbered lines."""
    resolved = resolve_path(path)
    if err := check_path(resolved):
        return err
    if not resolved.exists():
        return f"Error: not found: {resolved}"
    if not resolved.is_file():
        return f"Error: not a file: {resolved}"
    content = read_text(resolved)
    if content is None:
        return f"Binary file: {resolved} ({resolved.stat().st_size:,} bytes)"
    lines = content.splitlines()
    total = len(lines)
    start = (start_line or 1) - 1
    end = end_line or min(total, 500)
    numbered = [f"{i + start + 1:>5} | {ln}" for i, ln in enumerate(lines[start:end])]
    result = "\n".join(numbered)
    if not start_line and not end_line and total > 500:
        result += f"\n[{total} lines total, showing first 500]"
    return result


def file_write(path: str, content: str) -> str:
    """Write content to file. Creates directories if needed."""
    resolved = resolve_path(path)
    if err := check_path(resolved):
        return err
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    return f"Written: {resolved} ({len(content.splitlines())} lines)"


def file_append(path: str, content: str) -> str:
    """Append content to file. Creates file if needed."""
    resolved = resolve_path(path)
    if err := check_path(resolved):
        return err
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with open(resolved, "a", encoding="utf-8") as f:
        f.write(content)
    return f"Appended {len(content.splitlines())} lines to: {resolved}"


def file_list(path: str = ".", recursive: bool = False, show_hidden: bool = False) -> str:
    """List files and directories."""
    resolved = resolve_path(path)
    if err := check_path(resolved):
        return err
    if not resolved.is_dir():
        return f"Error: not a directory: {resolved}"
    lines = [str(resolved)]
    items = sorted(resolved.rglob("*") if recursive else resolved.iterdir())
    for item in items[:200]:
        if not show_hidden and item.name.startswith("."):
            continue
        rel = item.relative_to(resolved)
        suffix = "/" if item.is_dir() else f"  ({item.stat().st_size:,} bytes)"
        lines.append(f"  {rel}{suffix}")
    if len(items) > 200:
        lines.append(f"[... {len(items) - 200} more]")
    return "\n".join(lines)


def file_delete(path: str, recursive: bool = False) -> str:
    """Delete file or directory."""
    resolved = resolve_path(path)
    if err := check_path(resolved):
        return err
    if not resolved.exists():
        return f"Error: not found: {resolved}"
    if resolved.is_dir():
        if not recursive:
            return "Error: is a directory, use recursive=True"
        shutil.rmtree(resolved)
    else:
        resolved.unlink()
    return f"Deleted: {resolved}"


def file_move(source: str, destination: str) -> str:
    """Move or rename file/directory."""
    src, dst = resolve_path(source), resolve_path(destination)
    if err := check_path(src):
        return err
    if err := check_path(dst):
        return err
    if not src.exists():
        return f"Error: not found: {src}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return f"Moved: {src} -> {dst}"


def file_copy(source: str, destination: str) -> str:
    """Copy file or directory."""
    src, dst = resolve_path(source), resolve_path(destination)
    if err := check_path(src):
        return err
    if err := check_path(dst):
        return err
    if not src.exists():
        return f"Error: not found: {src}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(str(src), str(dst))
    else:
        shutil.copy2(str(src), str(dst))
    return f"Copied: {src} -> {dst}"


def file_info(path: str) -> str:
    """File metadata: size, permissions, owner, timestamps."""
    import grp
    import pwd
    import stat as stat_mod

    resolved = resolve_path(path)
    if err := check_path(resolved):
        return err
    if not resolved.exists():
        return f"Error: not found: {resolved}"
    st = resolved.stat()
    try:
        owner = pwd.getpwuid(st.st_uid).pw_name
    except KeyError:
        owner = str(st.st_uid)
    try:
        group = grp.getgrgid(st.st_gid).gr_name
    except KeyError:
        group = str(st.st_gid)
    ftype = "directory" if resolved.is_dir() else "symlink" if resolved.is_symlink() else "file"
    lines = [
        f"Path: {resolved}",
        f"Type: {ftype}",
        f"Size: {format_size(st.st_size)}",
        f"Permissions: {stat_mod.filemode(st.st_mode)}",
        f"Owner: {owner}:{group}",
        f"Modified: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime))}",
    ]
    if resolved.is_symlink():
        lines.append(f"Target: {resolved.resolve()}")
    return "\n".join(lines)


def head(path: str, lines: int = 20) -> str:
    """First N lines of a file."""
    resolved = resolve_path(path)
    if err := check_path(resolved):
        return err
    if not resolved.is_file():
        return f"Error: not a file: {resolved}"
    content = read_text(resolved)
    if content is None:
        return f"Binary file: {resolved}"
    all_lines = content.splitlines()
    numbered = [f"{i + 1:>5} | {ln}" for i, ln in enumerate(all_lines[:lines])]
    result = "\n".join(numbered)
    if len(all_lines) > lines:
        result += f"\n[{len(all_lines)} lines total]"
    return result


def tail(path: str, lines: int = 20) -> str:
    """Last N lines of a file."""
    resolved = resolve_path(path)
    if err := check_path(resolved):
        return err
    if not resolved.is_file():
        return f"Error: not a file: {resolved}"
    content = read_text(resolved)
    if content is None:
        return f"Binary file: {resolved}"
    all_lines = content.splitlines()
    total = len(all_lines)
    start = max(0, total - lines)
    numbered = [f"{start + i + 1:>5} | {ln}" for i, ln in enumerate(all_lines[start:])]
    result = "\n".join(numbered)
    if total > lines:
        result = f"[{total} lines total]\n" + result
    return result


def tree(path: str = ".", max_depth: int = 3, show_hidden: bool = False) -> str:
    """Directory tree as ASCII art."""
    resolved = resolve_path(path)
    if err := check_path(resolved):
        return err
    if not resolved.is_dir():
        return f"Error: not a directory: {resolved}"

    lines = [str(resolved)]

    def walk(dir_path: Path, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError:
            lines.append(f"{prefix}[permission denied]")
            return
        if not show_hidden:
            entries = [e for e in entries if not e.name.startswith(".")]
        for i, entry in enumerate(entries):
            last = i == len(entries) - 1
            connector = "└── " if last else "├── "
            if entry.is_dir():
                lines.append(f"{prefix}{connector}{entry.name}/")
                walk(entry, prefix + ("    " if last else "│   "), depth + 1)
            else:
                sz = entry.stat().st_size
                s = f"{sz}B" if sz < 1024 else f"{sz // 1024}K" if sz < 1048576 else f"{sz // 1048576}M"
                lines.append(f"{prefix}{connector}{entry.name} ({s})")

    walk(resolved, "", 1)
    if len(lines) > 200:
        lines = lines[:200] + ["[... truncated]"]
    return "\n".join(lines)
