# Engineering Task Board

## Completed Milestones
- [x] **Module 0: Foundation & Context System**
  - [x] Python environment & dependencies (`pyproject.toml`, `requirements.txt`).
  - [x] Context engineering documentation system in `docs/`.
  - [x] Application configuration in `src/config.py`.
  - [x] Structured logging with secret scrubbing in `src/core/logging.py`.
  - [x] Base domain exceptions in `src/core/exceptions.py`.
  - [x] Early authentication & role boundary scaffolding in `src/core/security.py`.
  - [x] FastAPI entrypoint & health checks in `src/main.py`.
  - [x] Pytest testing harness and initial test suite.
- [x] **Module 1: Database Foundation & Schemas**
  - [x] SQLAlchemy 2.0 DeclarativeBase, UUIDPrimaryKeyMixin, TimestampMixin.
  - [x] Strict domain enums (`ComplianceStatus`, `EvidenceValidity`, etc.).
  - [x] Relational models (`compliance_frameworks`, `requirements`, `evidence_documents`, `evidence_matches`, `compliance_status`, `compliance_status_history`, `gap_reports`, `document_processing_jobs`, `users`).
  - [x] PostgreSQL-first schema with SQLite testing compatibility and foreign key pragma.
  - [x] Alembic migration initialization (`0c0c5ce46f4c_0001_initial_schema.py`).
  - [x] Seed frameworks (`seed/frameworks/soc2_type2.json`, `seed/frameworks/iso27001_2022.json`).
  - [x] Idempotent database seeder (`src/database/seed.py`).
  - [x] Integration tests (`tests/integration/test_db_models.py`, `tests/integration/test_seed.py`, `tests/integration/test_migrations.py`).

## Next (Module 2)
- [ ] Pydantic request and response schemas for frameworks and requirements.
- [ ] `FrameworkService` for business logic, filtering, and CRUD operations.
- [ ] REST API endpoints:
  - `GET /api/v1/frameworks`
  - `POST /api/v1/frameworks`
  - `GET /api/v1/frameworks/{id}/requirements`
  - `POST /api/v1/frameworks/{id}/requirements`
- [ ] Role-based authorization enforcement (`compliance-officer` for writes, `auditor` for reads).
- [ ] API integration tests for status codes 200, 201, 400, 401, 403, 404, 422.

## Later (Modules 3 - 10)
- [ ] Secure evidence ingestion and text extraction (Module 3).
- [ ] Durable database-backed job queue and background worker (Module 4).
- [ ] AI Grok matching agent with anti-injection prompts (Module 5).
- [ ] Deterministic compliance evaluation and expiration engine (Module 6).
- [ ] Gap reporting lifecycle (Module 7).
- [ ] Full JWT auth and RBAC implementation (Module 8).
- [ ] Aggregated compliance dashboard API (Module 9).
- [ ] Hardening, security testing, and end-to-end demo (Module 10).
