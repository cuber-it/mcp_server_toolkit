"""Management API — FastAPI server for runtime proxy control.

Runs on a separate port as daemon thread. Provides REST endpoints
to load/unload/reload plugins and check status.

Optional Bearer token auth via config ``management_token`` or
environment variable ``MCP_MGMT_TOKEN``.
"""

from __future__ import annotations

import os
import sys
import threading
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

from .proxy import PluginManager

logger = logging.getLogger(__name__)


class PluginRequest(BaseModel):
    plugin: str


class _TokenAuthMiddleware(BaseHTTPMiddleware):
    """Reject requests without valid Bearer token."""

    def __init__(self, app, token: str):
        super().__init__(app)
        self._token = token

    async def dispatch(self, request: Request, call_next):
        auth = request.headers.get("authorization", "")
        if auth != f"Bearer {self._token}":
            return JSONResponse(status_code=401, content={"error": "unauthorized"})
        return await call_next(request)


def create_management_app(
    proxy: PluginManager,
    token: str | None = None,
) -> FastAPI:
    """Create FastAPI app with proxy management endpoints.

    Args:
        proxy: PluginManager instance to control.
        token: Optional Bearer token. If set, all requests must include
            ``Authorization: Bearer <token>``.
    """
    app = FastAPI(title="MCP Proxy Management", docs_url=None)

    if token:
        app.add_middleware(_TokenAuthMiddleware, token=token)

    @app.get("/proxy/status")
    async def status():
        return proxy.list_plugins()

    @app.get("/proxy/plugins")
    async def plugins():
        info = proxy.list_plugins()
        return {"plugins": list(info["plugins"].keys())}

    @app.post("/proxy/load")
    async def load(req: PluginRequest):
        result = proxy.load(req.plugin)
        if result.ok:
            return {"ok": True, "plugin": req.plugin, "tools": result.tools}
        return JSONResponse(status_code=400, content={"ok": False, "error": result.error})

    @app.post("/proxy/unload")
    async def unload(req: PluginRequest):
        result = proxy.unload(req.plugin)
        if result.ok:
            return {"ok": True, "plugin": req.plugin, "removed": result.removed}
        return JSONResponse(status_code=400, content={"ok": False, "error": result.error})

    @app.post("/proxy/reload")
    async def reload(req: PluginRequest):
        result = proxy.reload(req.plugin)
        if result.ok:
            return {"ok": True, "plugin": req.plugin, "tools": result.tools}
        return JSONResponse(status_code=400, content={"ok": False, "error": result.error})

    @app.get("/proxy/commands")
    async def commands():
        return {"commands": proxy.commands}

    @app.post("/proxy/command/{name}")
    async def run_command(name: str):
        result = proxy.run_command(name)
        return {"command": name, "result": result}

    return app


def start_management_server(
    proxy: PluginManager,
    port: int = 12299,
    token: str | None = None,
) -> threading.Thread:
    """Start management API as daemon thread.

    Args:
        proxy: PluginManager instance to control.
        port: Port for the management API.
        token: Optional Bearer token. Falls back to env ``MCP_MGMT_TOKEN``.

    Returns:
        The started thread.
    """
    token = token or os.environ.get("MCP_MGMT_TOKEN")
    app = create_management_app(proxy, token=token)

    def _run():
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

    t = threading.Thread(target=_run, daemon=True, name="management-api")
    t.start()
    auth_info = " (auth enabled)" if token else " (no auth)"
    print(f"Management API on port {port}{auth_info}", file=sys.stderr)
    return t
