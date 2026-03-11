"""HTTP requests and JSON queries."""

from __future__ import annotations

import json as _json

from ._state import check_path, resolve_path


def http_request(url: str, method: str = "GET", data: str = "", headers: str = "") -> str:
    """HTTP request (like curl). Headers as 'Key: Value' per line."""
    import urllib.error
    import urllib.request

    req_headers = {}
    for line in headers.strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            req_headers[k.strip()] = v.strip()
    body = data.encode("utf-8") if data else None
    if body and "Content-Type" not in req_headers:
        req_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_body = resp.read().decode("utf-8", errors="replace")
            h = "\n".join(f"{k}: {v}" for k, v in resp.headers.items())
            if len(resp_body) > 10000:
                resp_body = resp_body[:10000] + f"\n[... {len(resp_body)} bytes total]"
            return f"HTTP {resp.status}\n{h}\n\n{resp_body}"
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code} {e.reason}\n{e.read().decode('utf-8', errors='replace')[:2000]}"
    except Exception as e:
        return f"Error: {e}"


def json_query(path: str, query: str = "") -> str:
    """Read JSON and extract via dot notation: 'key.sub.0.name'."""
    resolved = resolve_path(path)
    if err := check_path(resolved):
        return err
    if not resolved.is_file():
        return f"Error: not a file: {resolved}"
    try:
        data = _json.loads(resolved.read_text(encoding="utf-8"))
    except Exception as e:
        return f"Error: {e}"
    if not query:
        return _json.dumps(data, indent=2, ensure_ascii=False)[:10000]
    current = data
    for key in query.split("."):
        try:
            current = current[int(key)] if isinstance(current, list) else current[key]
        except (KeyError, IndexError, ValueError) as e:
            return f"Error at '{key}': {e}"
    if isinstance(current, (dict, list)):
        return _json.dumps(current, indent=2, ensure_ascii=False)[:10000]
    return str(current)
