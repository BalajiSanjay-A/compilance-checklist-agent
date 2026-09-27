"""Unit tests for configuration and environment settings."""

from src.config import Settings


def test_default_settings():
    """Verify default settings reflect design decisions."""
    settings = Settings()
    assert settings.app_name == "Compliance Checklist Automation Agent"
    assert settings.expiration_warning_days == 30
    assert settings.max_upload_size_mb == 25
    assert settings.xai_model == "grok-beta"


def test_effective_database_url_sqlite_fallback():
    """Verify effective_database_url switches to SQLite when fallback is enabled."""
    settings = Settings(use_sqlite_fallback=True, sqlite_db_path="./test.db")
    assert settings.effective_database_url == "sqlite:///./test.db"


def test_effective_database_url_postgresql():
    """Verify effective_database_url preserves PostgreSQL in production/dev."""
    pg_url = "postgresql://user:pass@localhost:5432/proddb"
    settings = Settings(app_env="production", use_sqlite_fallback=False, database_url=pg_url)
    assert settings.effective_database_url == pg_url
