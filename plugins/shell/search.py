"""Search: grep and glob."""

from __future__ import annotations

import re

from ._state import check_path, read_text, resolve_path


def grep(
    pattern: str, path: str = ".", recursive: bool = True,
    ignore_case: bool = False, file_pattern: str = "*", max_results: int = 50,
) -> str:
    """Search for pattern in files."""
    resolved = resolve_path(path)
    if not resolved.exists():
        return f"Error: not found: {resolved}"
    flags = re.IGNORECASE if ignore_case else 0
    try:
        regex = re.compile(pattern, flags)
    except re.error as e:
        return f"Error: invalid regex: {e}"
    if resolved.is_file():
        files = [resolved]
    else:
        files = sorted(resolved.rglob(file_pattern) if recursive else resolved.glob(file_pattern))
        files = [f for f in files if f.is_file() and not any(p.startswith(".") for p in f.parts)]
    results = []
    for f in files:
        content = read_text(f)
        if not content:
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
    return f"{len(results)} matches for '{pattern}':\n" + "\n".join(results)


def glob_search(pattern: str, path: str = ".") -> str:
    """Find files by glob pattern."""
    resolved = resolve_path(path)
    if not resolved.is_dir():
        return f"Error: not a directory: {resolved}"
    matches = sorted(resolved.glob(pattern))[:100]
    if not matches:
        return f"No matches for '{pattern}'"
    lines = [str(m.relative_to(resolved)) for m in matches]
    return f"{len(matches)} matches:\n" + "\n".join(lines)
