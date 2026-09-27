# CHANGELOG: Compliance Checklist Automation Agent

All notable engineering changes to this project will be documented in this file.
This changelog serves as the persistent engineering memory layer alongside git commits.

## [Unreleased] - 2026-09-27

### Added - Module 1: Database Foundation & Schemas
- Implemented SQLAlchemy 2.0 DeclarativeBase, `UUIDPrimaryKeyMixin`, and `TimestampMixin` with timezone awareness in `src/database/base.py`.
- Defined strict domain enums in `src/database/models/enums.py`:
  - `ComplianceStatus`: `SATISFIED`, `PARTIAL`, `GAP`.
  - `EvidenceValidity`: `VALID`, `EXPIRING_SOON`, `EXPIRED`.
  - `ProcessingStatus`, `JobStatus`, `DocumentType`, `Severity`, `GapType`, `GapStatus`.
- Built core entity models:
  - `ComplianceFramework`: Unique constraint `(name, version)`.
  - `Requirement`: Unique constraint `(framework_id, requirement_code)`, index on `(framework_id, is_active)`.
  - `EvidenceDocument`: SHA-256 integrity hash index, expiration date index, and processing status.
  - `DocumentProcessingJob`: Durable job record with lease-based locking columns (`locked_at`, `locked_by`).
  - `EvidenceMatch`: Immutable evaluation ledger with JSON fields for `supporting_evidence`, `missing_evidence`, `requested_evidence`, and `citation_verified` flag.
  - `ComplianceStatusRecord`: Current state snapshot per requirement (`UNIQUE(requirement_id)`).
  - `ComplianceStatusHistory`: Audit transition log.
  - `GapReport`: Priority and actionable requested evidence.
  - `User`: System accounts with role assignment.
- Built database session and engine management in `src/database/session.py` with PostgreSQL connection pooling and SQLite PRAGMA foreign key listeners.
- Initialized Alembic migration suite and generated initial migration `0c0c5ce46f4c_0001_initial_schema.py` supporting both PostgreSQL and SQLite batch alters.
- Created pre-loaded compliance frameworks in `seed/frameworks/` (`soc2_type2.json`, `iso27001_2022.json`).
- Built idempotent database seeder in `src/database/seed.py` initializing frameworks, requirements with baseline `GAP` status, and default compliance officer user.
- Added comprehensive integration tests in `tests/integration/` (`test_db_models.py`, `test_seed.py`, `test_migrations.py`) and `tests/unit/test_session.py`.

### Added - Module 0: Project Foundation & Context Engineering
- Initialized comprehensive Python 3.12 project structure with `pyproject.toml`, `requirements.txt`, and `.gitignore`.
- Created `.env.example` defining configuration for PostgreSQL, Grok xAI API, expiration thresholds, and auth parameters.
- Built centralized settings management in `src/config.py` using `pydantic-settings` with default expiration warning window `EXPIRATION_WARNING_DAYS=30`.
- Implemented structured logging in `src/core/logging.py` featuring automatic secret and API key scrubbing.
- Established domain exception hierarchy in `src/core/exceptions.py`.
- Designed early authentication and authorization boundaries in `src/core/security.py` with roles (`compliance-officer`, `admin`, `auditor`) and `require_role` dependency injection guards.
- Created FastAPI application entrypoint in `src/main.py` with `/health` and `/api/v1/health` endpoints.
- Established canonical engineering context system in `docs/` (`PROJECT_CONTEXT.md`, `CHANGELOG.md`, `ARCHITECTURE.md`, `DATABASE.md`, `API.md`, `AI.md`, `SECURITY.md`, `DECISIONS.md`, `TODO.md`).
- Setup pytest testing harness in `tests/conftest.py` with initial unit and API health tests.
