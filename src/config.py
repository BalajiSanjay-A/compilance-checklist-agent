"""Application configuration management using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global system configuration loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application settings
    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "Compliance Checklist Automation Agent"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000

    # Database settings (PostgreSQL is production source of truth)
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/compliance_db",
        description="PostgreSQL connection string for production.",
    )
    use_sqlite_fallback: bool = Field(
        default=False,
        description="Enable SQLite fallback for lightweight local dev without PostgreSQL.",
    )
    sqlite_db_path: str = Field(
        default="./compliance.db",
        description="Local SQLite database file path when fallback is active.",
    )

    # Document storage
    storage_dir: Path = Field(
        default=Path("./storage/evidence"),
        description="Local root directory for isolated document storage.",
    )
    max_upload_size_mb: int = Field(
        default=25,
        description="Maximum allowed upload file size in megabytes.",
    )

    # AI / LLM Configuration (Grok via xAI API)
    xai_api_key: str = Field(
        default="",
        description="xAI API key for Grok application model.",
    )
    xai_base_url: str = Field(
        default="https://api.x.ai/v1",
        description="Base URL for xAI Grok API endpoint.",
    )
    xai_model: str = Field(
        default="grok-beta",
        description="Model identifier for Grok evaluations.",
    )
    ai_mock_mode: bool = Field(
        default=True,
        description="Use deterministic mock LLM for tests and offline development.",
    )

    # Evidence expiration & risk thresholds
    expiration_warning_days: int = Field(
        default=30,
        description="Days prior to expiration when evidence validity is marked EXPIRING_SOON.",
    )

    # Security & JWT Authentication
    secret_key: str = Field(
        default="insecure-dev-secret-key-change-in-production-min-32-chars",
        description="Cryptographic secret key for signing JWT tokens.",
    )
    algorithm: str = Field(
        default="HS256",
        description="JWT cryptographic signing algorithm.",
    )
    access_token_expire_minutes: int = Field(
        default=60,
        description="Access token lifespan in minutes.",
    )
    default_admin_username: str = Field(
        default="compliance_admin",
        description="Initial seeded compliance officer username.",
    )
    default_admin_email: str = Field(
        default="admin@compliance.local",
        description="Initial seeded compliance officer email.",
    )
    default_admin_password: str = Field(
        default="change_this_password_immediately",
        description="Initial seeded compliance officer password.",
    )
    cors_allowed_origins: str = Field(
        default="",
        description="Comma-separated allowed CORS origins for production.",
    )

    # Background worker settings
    worker_poll_interval_seconds: int = Field(
        default=5,
        description="Worker polling frequency for queued jobs.",
    )
    worker_batch_size: int = Field(
        default=5,
        description="Number of jobs retrieved per worker polling cycle.",
    )
    worker_lease_timeout_seconds: int = Field(
        default=600,
        description="Timeout in seconds before an abandoned job lease is reclaimed.",
    )

    @property
    def effective_database_url(self) -> str:
        """Resolve database URL based on environment or SQLite fallback toggle."""
        if self.use_sqlite_fallback or self.app_env == "test":
            # SQLite connection URL
            return f"sqlite:///{self.sqlite_db_path}"
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    """Return cached singleton instance of application settings."""
    return Settings()
