"""Database engine, session factory, and transaction management."""

from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import get_settings
from src.database.base import Base

_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker[Session]] = None


def get_engine(database_url: Optional[str] = None) -> Engine:
    """Return configured SQLAlchemy engine singleton."""
    global _engine
    if _engine is not None and database_url is None:
        return _engine

    settings = get_settings()
    url = database_url or settings.effective_database_url

    engine_kwargs = {
        "echo": False,
        "future": True,
    }

    if url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}

        engine = create_engine(url, **engine_kwargs)

        # Enforce foreign key constraints on SQLite
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    else:
        # PostgreSQL pool configuration
        engine_kwargs.update({
            "pool_pre_ping": True,
            "pool_size": 10,
            "max_overflow": 20,
        })
        engine = create_engine(url, **engine_kwargs)

    if database_url is None:
        _engine = engine
    return engine


def get_session_factory(engine: Optional[Engine] = None) -> sessionmaker[Session]:
    """Return configured session factory."""
    global _session_factory
    if _session_factory is not None and engine is None:
        return _session_factory

    active_engine = engine or get_engine()
    factory = sessionmaker(
        bind=active_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    if engine is None:
        _session_factory = factory
    return factory


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding database session per request."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def transactional_session(session: Session) -> Generator[Session, None, None]:
    """Context manager ensuring transaction commit or rollback on error."""
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise


def init_db(engine: Optional[Engine] = None) -> None:
    """Create all tables registered with Base metadata (for testing and local dev)."""
    import src.database.models  # ensure models are imported
    active_engine = engine or get_engine()
    Base.metadata.create_all(bind=active_engine)


def reset_engine_for_testing() -> None:
    """Reset cached engine and session factory (for clean test isolation)."""
    global _engine, _session_factory
    if _engine:
        _engine.dispose()
    _engine = None
    _session_factory = None
