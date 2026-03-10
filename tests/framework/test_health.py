"""Tests for health server."""

from fastapi.testclient import TestClient

from mcp_server_framework.health import create_health_app


def test_health_endpoint():
    """/health returns status ok."""
    app = create_health_app(title="Test Health")
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "timestamp" in data


def test_health_detailed():
    """/health/detailed returns uptime and stats."""
    app = create_health_app()
    client = TestClient(app)
    resp = client.get("/health/detailed")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["uptime_seconds"] >= 0
    assert data["started_at"] is not None
    assert "requests" in data
    assert "errors" in data


def test_health_detailed_isolated():
    """Two apps don't share state."""
    app_a = create_health_app(title="A")
    app_b = create_health_app(title="B")
    assert (
        app_a.state.started_at != app_b.state.started_at
        or app_a.state is not app_b.state
    )


def test_health_ready_default():
    """/health/ready without check → always ready."""
    app = create_health_app()
    client = TestClient(app)
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json()["ready"] is True


def test_health_ready_failing_check():
    """/health/ready with failing check → 503."""
    def failing_check():
        raise RuntimeError("not ready")

    app = create_health_app(readiness_check=failing_check)
    client = TestClient(app)
    resp = client.get("/health/ready")
    assert resp.status_code == 503
    data = resp.json()
    assert data["ready"] is False
    assert "not ready" in data["error"]


def test_health_404():
    """Unknown path → 404."""
    app = create_health_app()
    client = TestClient(app)
    resp = client.get("/unknown")
    assert resp.status_code in (404, 405)
