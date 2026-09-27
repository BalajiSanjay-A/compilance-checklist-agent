"""Pytest configuration and shared test fixtures."""

from typing import AsyncGenerator
import pytest
from httpx import ASGITransport, AsyncClient

from src.config import Settings, get_settings
from src.core.security import Role, create_access_token
from src.main import create_application


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Fixture providing test environment configuration."""
    return Settings(
        app_env="test",
        debug=True,
        use_sqlite_fallback=True,
        sqlite_db_path=":memory:",
        ai_mock_mode=True,
        expiration_warning_days=30,
        secret_key="test-secret-key-for-unit-and-integration-tests",
    )


@pytest.fixture
def override_settings(test_settings: Settings):
    """Override application get_settings dependency with test_settings."""
    from src.config import get_settings
    get_settings.cache_clear()
    return test_settings


@pytest.fixture
async def async_client(test_settings: Settings) -> AsyncGenerator[AsyncClient, None]:
    """Asynchronous HTTP test client for testing FastAPI endpoints."""
    app = create_application()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def compliance_officer_token() -> str:
    """Generate valid JWT token for a compliance-officer."""
    return create_access_token({
        "sub": "test_officer",
        "role": Role.COMPLIANCE_OFFICER.value,
        "user_id": "11111111-1111-1111-1111-111111111111",
    })


@pytest.fixture
def auditor_token() -> str:
    """Generate valid JWT token for an auditor."""
    return create_access_token({
        "sub": "test_auditor",
        "role": Role.AUDITOR.value,
        "user_id": "22222222-2222-2222-2222-222222222222",
    })
