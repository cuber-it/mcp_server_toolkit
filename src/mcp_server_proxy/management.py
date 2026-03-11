"""Management API — FastAPI server for runtime proxy control.

Runs on a separate port as daemon thread. Provides REST endpoints
to load/unload/reload plugins and check status.
"""

from __future__ import annotations

import sys
import threading
import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

from .proxy import PluginManager

logger = logging.getLogger(__name__)


class PluginRequest(BaseModel):
    plugin: str


def create_management_app(proxy: PluginManager) -> FastAPI:
    """Create FastAPI app with proxy management endpoints."""
    app = FastAPI(title="MCP Proxy Management", docs_url=None)

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
) -> threading.Thread:
    """Start management API as daemon thread.

    Args:
        proxy: PluginManager instance to control.
        port: Port for the management API.

    Returns:
        The started thread.
    """
    app = create_management_app(proxy)

    def _run():
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

    t = threading.Thread(target=_run, daemon=True, name="management-api")
    t.start()
    print(f"Management API on port {port}", file=sys.stderr)
    return t
