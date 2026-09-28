"""Pytest configuration and shared test fixtures."""

from typing import AsyncGenerator, Generator
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.config import Settings, get_settings
from src.core.security import Role, create_access_token
from src.database.base import Base
from src.database.session import get_db
import src.database.models  # noqa: F401
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


@pytest.fixture(scope="session")
def db_engine() -> Generator[Engine, None, None]:
    """In-memory SQLite engine with StaticPool and foreign key enforcement."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    """Database session providing clean table isolation per test function."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def override_settings(test_settings: Settings):
    """Override application get_settings dependency with test_settings."""
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


@pytest.fixture
async def async_client_db(db_engine: Engine) -> AsyncGenerator[tuple[AsyncClient, Session], None]:
    """Async HTTP client with database dependency override using nested transaction isolation."""
    app = create_application()
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)

    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        nonlocal nested
        if not connection.closed and trans.nested and not connection.in_nested_transaction():
            nested = connection.begin_nested()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, session

    session.close()
    transaction.rollback()
    connection.close()
    app.dependency_overrides.clear()
