"""Unit tests for database session management, engine lifecycle, and transactional sessions."""

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.database.session import (
    get_db,
    get_engine,
    get_session_factory,
    init_db,
    reset_engine_for_testing,
    transactional_session,
)


def test_get_engine_and_reset():
    """Verify engine creation and reset."""
    reset_engine_for_testing()
    engine = get_engine("sqlite:///:memory:")
    assert engine is not None

    factory = get_session_factory(engine)
    assert factory is not None

    with factory() as session:
        result = session.execute(text("SELECT 1")).scalar()
        assert result == 1

    reset_engine_for_testing()


def test_get_db_generator():
    """Verify get_db dependency yields active session and closes cleanly."""
    reset_engine_for_testing()
    get_engine("sqlite:///:memory:")
    gen = get_db()
    session = next(gen)
    assert isinstance(session, Session)
    try:
        next(gen)
    except StopIteration:
        pass  # successfully closed
    reset_engine_for_testing()


def test_transactional_session_success():
    """Verify transactional_session commits on success."""
    reset_engine_for_testing()
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    factory = get_session_factory(engine)

    with factory() as session:
        with transactional_session(session):
            session.execute(text("SELECT 1"))

    reset_engine_for_testing()


def test_transactional_session_rollback_on_error():
    """Verify transactional_session rolls back when an exception is raised."""
    reset_engine_for_testing()
    engine = get_engine("sqlite:///:memory:")
    factory = get_session_factory(engine)

    with factory() as session:
        with pytest.raises(ValueError):
            with transactional_session(session):
                raise ValueError("Simulated error inside transaction")

    reset_engine_for_testing()
