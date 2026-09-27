"""API tests for health check and auth boundaries."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_health(async_client: AsyncClient):
    """Test /health endpoint."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "Compliance Checklist Automation Agent" in data["service"]


@pytest.mark.asyncio
async def test_v1_health(async_client: AsyncClient):
    """Test /api/v1/health endpoint."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["api_version"] == "v1"


@pytest.mark.asyncio
async def test_auth_me_unauthorized_without_token(async_client: AsyncClient):
    """Test /api/v1/auth/me rejects request without auth header."""
    response = await async_client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert "Missing authentication credentials" in response.json()["detail"]


@pytest.mark.asyncio
async def test_auth_me_with_valid_jwt(async_client: AsyncClient, compliance_officer_token: str):
    """Test /api/v1/auth/me succeeds with valid Bearer token."""
    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {compliance_officer_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "test_officer"
    assert data["role"] == "compliance-officer"


@pytest.mark.asyncio
async def test_auth_me_with_dev_header(async_client: AsyncClient):
    """Test /api/v1/auth/me allows dev header in test mode."""
    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"X-Dev-Role": "compliance-officer", "X-Dev-User": "fast_dev_user"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "fast_dev_user"
    assert data["role"] == "compliance-officer"


@pytest.mark.asyncio
async def test_auth_me_with_invalid_dev_role(async_client: AsyncClient):
    """Test /api/v1/auth/me rejects unsupported role string in dev header."""
    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"X-Dev-Role": "invalid_super_god_role"},
    )
    assert response.status_code == 400
    assert "Invalid development role" in response.json()["detail"]
