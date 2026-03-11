"""Text editing: str_replace, diff preview, find & replace."""

from __future__ import annotations

import difflib
from pathlib import Path

from ._state import check_path, read_text, resolve_path


def str_replace(path: str, old_string: str, new_string: str) -> str:
    """Replace exact, unique string in a file."""
    resolved = resolve_path(path)
    if err := check_path(resolved):
        return err
    if not resolved.is_file():
        return f"Error: not a file: {resolved}"
    content = resolved.read_text(encoding="utf-8")
    count = content.count(old_string)
    if count == 0:
        return f"Error: string not found in {resolved}"
    if count > 1:
        return f"Error: string appears {count} times, must be unique"
    resolved.write_text(content.replace(old_string, new_string, 1), encoding="utf-8")
    return f"Replaced in {resolved}"


def diff_preview(path: str, old_string: str, new_string: str = "", context_lines: int = 3) -> str:
    """Unified diff preview before applying str_replace."""
    resolved = resolve_path(path)
    if err := check_path(resolved):
        return err
    if not resolved.is_file():
        return f"Error: not a file: {resolved}"
    content = resolved.read_text(encoding="utf-8")
    count = content.count(old_string)
    if count == 0:
        return f"Error: string not found in {resolved}"
    if count > 1:
        return f"Warning: appears {count} times, str_replace would fail"
    new_content = content.replace(old_string, new_string, 1)
    diff = difflib.unified_diff(
        content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"a/{resolved.name}",
        tofile=f"b/{resolved.name}",
        n=context_lines,
    )
    return "".join(diff) or "No changes"


def find_replace(
    pattern: str, replacement: str, path: str = ".",
    file_pattern: str = "*", dry_run: bool = True,
) -> str:
    """Find and replace across files. dry_run=True for preview."""
    resolved = resolve_path(path)
    if not resolved.exists():
        return f"Error: not found: {resolved}"
    if resolved.is_file():
        files = [resolved]
    else:
        files = sorted(
            f for f in resolved.rglob(file_pattern)
            if f.is_file() and not any(p.startswith(".") for p in f.parts)
        )
    results = []
    total = 0
    for f in files:
        if check_path(f):
            continue
        content = read_text(f)
        if not content:
            continue
        count = content.count(pattern)
        if count == 0:
            continue
        rel = f.relative_to(resolved) if resolved.is_dir() else f.name
        if not dry_run:
            f.write_text(content.replace(pattern, replacement), encoding="utf-8")
        results.append(f"  {rel}: {count}x")
        total += count
    if not results:
        return f"No matches for '{pattern}'"
    mode = "PREVIEW" if dry_run else "APPLIED"
    return f"[{mode}] {total} in {len(results)} file(s)\n" + "\n".join(results)
