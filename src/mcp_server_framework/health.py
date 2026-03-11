"""Health server — FastAPI background thread for monitoring.

Provides three endpoints:
    /health          → Simple status + timestamp
    /health/detailed → Uptime, requests, errors
    /health/ready    → Readiness check

Runs in its own daemon thread, does not block the MCP server.
"""

from __future__ import annotations

import sys
import threading
import logging
from datetime import datetime, timezone
from typing import Callable

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

logger = logging.getLogger(__name__)


def _now() -> datetime:
    """UTC timestamp."""
    return datetime.now(timezone.utc)


def create_health_app(
    title: str = "MCP Server Health",
    readiness_check: Callable | None = None,
) -> FastAPI:
    """Create FastAPI app with health endpoints.

    Stats are kept per app instance (app.state),
    not as module globals — multiple apps don't
    interfere with each other.

    Args:
        title: Name of the health app (for logs/docs).
        readiness_check: Optional callable invoked at
            /health/ready. Must raise Exception if not ready.
    """
    app = FastAPI(title=title, docs_url=None)

    # Stats per instance
    app.state.started_at = _now()
    app.state.connections = 0
    app.state.requests = 0
    app.state.last_request = None
    app.state.errors = 0

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "timestamp": _now().isoformat(),
        }

    @app.get("/health/detailed")
    async def health_detailed():
        s = app.state
        uptime = (_now() - s.started_at).total_seconds()

        return {
            "status": "ok",
            "uptime_seconds": uptime,
            "started_at": s.started_at.isoformat(),
            "connections": s.connections,
            "requests": s.requests,
            "last_request": (
                s.last_request.isoformat()
                if s.last_request else None
            ),
            "errors": s.errors,
        }

    @app.get("/health/ready")
    async def ready():
        try:
            if readiness_check:
                readiness_check()
            return {"ready": True}
        except Exception as e:
            return JSONResponse(
                status_code=503,
                content={
                    "ready": False,
                    "error": str(e),
                },
            )

    return app


def start_health_server(
    port: int,
    title: str = "MCP Server Health",
    readiness_check: Callable | None = None,
    registry_setup: Callable | None = None,
) -> threading.Thread:
    """Start health server as daemon thread.

    Args:
        port: Port for the health endpoint.
        title: Name of the health app.
        readiness_check: Callable for /health/ready.
        registry_setup: Callable(app) for registry hooks.

    Returns:
        The started thread.
    """
    health_app = create_health_app(
        title=title,
        readiness_check=readiness_check,
    )

    if registry_setup:
        registry_setup(health_app)

    def _run():
        import socket
        # Pre-check port availability to avoid noisy uvicorn error logs
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("0.0.0.0", port))
            sock.close()
        except OSError:
            sock.close()
            hint = f"Check with: lsof -i :{port} or ss -tlnp sport = :{port}"
            logger.warning(
                "Health server port %d already in use, skipping. "
                "Use --health-port to choose a different port. %s", port, hint,
            )
            return
        uvicorn.run(
            health_app,
            host="0.0.0.0",
            port=port,
            log_level="warning",
        )

    t = threading.Thread(
        target=_run, daemon=True, name="health-server",
    )
    t.start()
    print(
        f"Health server on port {port}",
        file=sys.stderr,
    )
    return t
