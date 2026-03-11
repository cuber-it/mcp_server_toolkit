"""Tests for OAuth token introspection verifier."""

import json

import httpx
import pytest

from mcp_server_framework.oauth import IntrospectionTokenVerifier


@pytest.fixture
def verifier():
    return IntrospectionTokenVerifier(
        introspection_endpoint="https://auth.example.com/introspect",
        server_url="https://mcp.example.com",
    )


@pytest.fixture
def localhost_verifier():
    return IntrospectionTokenVerifier(
        introspection_endpoint="http://localhost:8080/introspect",
        server_url="http://localhost:12200",
    )


# --- SSRF Protection ---

@pytest.mark.asyncio
async def test_rejects_unsafe_endpoint():
    """Rejects non-HTTPS, non-localhost endpoints."""
    v = IntrospectionTokenVerifier(
        introspection_endpoint="http://evil.com/introspect",
        server_url="https://mcp.example.com",
    )
    result = await v.verify_token("some-token")
    assert result is None
    await v.close()


@pytest.mark.asyncio
async def test_allows_https(verifier):
    """HTTPS endpoints are allowed."""
    assert verifier._is_safe_endpoint() is True


@pytest.mark.asyncio
async def test_allows_localhost(localhost_verifier):
    """Localhost endpoints are allowed."""
    assert localhost_verifier._is_safe_endpoint() is True


# --- Token Verification ---

@pytest.mark.asyncio
async def test_active_token(verifier, httpx_mock):
    """Active token returns AccessToken."""
    httpx_mock.add_response(
        url="https://auth.example.com/introspect",
        json={"active": True, "client_id": "my-app", "scope": "user admin", "exp": 9999999999},
    )
    result = await verifier.verify_token("valid-token")
    assert result is not None
    assert result.client_id == "my-app"
    assert result.scopes == ["user", "admin"]
    assert result.expires_at == 9999999999


@pytest.mark.asyncio
async def test_inactive_token(verifier, httpx_mock):
    """Inactive token returns None."""
    httpx_mock.add_response(
        url="https://auth.example.com/introspect",
        json={"active": False},
    )
    result = await verifier.verify_token("expired-token")
    assert result is None


@pytest.mark.asyncio
async def test_introspection_error(verifier, httpx_mock):
    """HTTP error returns None."""
    httpx_mock.add_response(
        url="https://auth.example.com/introspect",
        status_code=500,
    )
    result = await verifier.verify_token("some-token")
    assert result is None


@pytest.mark.asyncio
async def test_introspection_timeout(verifier, httpx_mock):
    """Timeout returns None."""
    httpx_mock.add_exception(
        httpx.ReadTimeout("timeout"),
        url="https://auth.example.com/introspect",
    )
    result = await verifier.verify_token("some-token")
    assert result is None


@pytest.mark.asyncio
async def test_no_scope(verifier, httpx_mock):
    """Token without scope returns empty list."""
    httpx_mock.add_response(
        url="https://auth.example.com/introspect",
        json={"active": True, "client_id": "app"},
    )
    result = await verifier.verify_token("no-scope-token")
    assert result is not None
    assert result.scopes == []


# --- Resource Validation ---

@pytest.mark.asyncio
async def test_resource_validation_pass(httpx_mock):
    """Audience matching passes."""
    v = IntrospectionTokenVerifier(
        introspection_endpoint="https://auth.example.com/introspect",
        server_url="https://mcp.example.com",
        validate_resource=True,
    )
    httpx_mock.add_response(
        url="https://auth.example.com/introspect",
        json={"active": True, "client_id": "app", "aud": "https://mcp.example.com"},
    )
    result = await v.verify_token("valid")
    assert result is not None
    await v.close()


@pytest.mark.asyncio
async def test_resource_validation_fail(httpx_mock):
    """Wrong audience is rejected."""
    v = IntrospectionTokenVerifier(
        introspection_endpoint="https://auth.example.com/introspect",
        server_url="https://mcp.example.com",
        validate_resource=True,
    )
    httpx_mock.add_response(
        url="https://auth.example.com/introspect",
        json={"active": True, "client_id": "app", "aud": "https://other.example.com"},
    )
    result = await v.verify_token("wrong-aud")
    assert result is None
    await v.close()


@pytest.mark.asyncio
async def test_resource_validation_list_audience(httpx_mock):
    """Audience as list — one match is enough."""
    v = IntrospectionTokenVerifier(
        introspection_endpoint="https://auth.example.com/introspect",
        server_url="https://mcp.example.com",
        validate_resource=True,
    )
    httpx_mock.add_response(
        url="https://auth.example.com/introspect",
        json={"active": True, "client_id": "app", "aud": ["https://other.com", "https://mcp.example.com"]},
    )
    result = await v.verify_token("multi-aud")
    assert result is not None
    await v.close()


# --- Context Manager ---

@pytest.mark.asyncio
async def test_context_manager():
    """Async context manager closes cleanly."""
    async with IntrospectionTokenVerifier(
        introspection_endpoint="https://auth.example.com/introspect",
        server_url="https://mcp.example.com",
    ) as v:
        assert v._is_safe_endpoint() is True
    assert v._client.is_closed
