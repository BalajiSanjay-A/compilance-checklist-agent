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
- [x] **Module 2: Framework & Requirement Management APIs**
  - [x] Pydantic request/response schemas (`src/schemas/framework.py`).
  - [x] `FrameworkService` with CRUD for frameworks and requirements (`src/services/framework_service.py`).
  - [x] REST API endpoints (8 total): list/create/get/update frameworks, list/create requirements under framework, get/update individual requirements.
  - [x] Router wired into `api_v1_router` (`src/api/v1/router.py`).
  - [x] Exception handler fixed: `EntityNotFoundException` → 404, `DuplicateEntityException` → 409.
  - [x] Role-based auth: `ComplianceOfficerDep` for writes, `AuditorDep` for reads.
  - [x] Auto-initialization of baseline GAP `ComplianceStatusRecord` on requirement creation.
  - [x] API integration tests (`tests/api/test_frameworks.py`, 28 tests).
  - [x] Service unit tests (`tests/unit/test_framework_service.py`, 19 tests).

- [x] **Module 3: Evidence Ingestion & Secure Storage**
  - [x] Pydantic schemas for evidence upload/retrieval (`src/schemas/evidence.py`).
  - [x] `EvidenceService` with secure upload, SHA-256 hashing, text extraction, validation (`src/services/evidence_service.py`).
  - [x] REST API endpoints: `POST /evidence/upload`, `GET /evidence/{id}`, `GET /evidence`.
  - [x] Security: MIME allowlist, 25MB size limit, filename sanitization, hash-based sharded storage, `0600` permissions.
  - [x] Text extraction from PDF (pypdf), TXT, MD, CSV files.
  - [x] Evidence validity computation (VALID/EXPIRING_SOON/EXPIRED) from dates.
  - [x] Automatic `DocumentProcessingJob` creation for unsupported extraction types.
  - [x] Dev user seeded in test fixture for FK integrity.
  - [x] API integration tests (`tests/api/test_evidence.py`, 13 tests).
  - [x] Service unit tests (`tests/unit/test_evidence_service.py`, 34 tests).

## Next (Module 4)
- [ ] Durable database-backed job queue worker.
- [ ] Job claiming with lease-based locking.
- [ ] Retry handling with exponential backoff.
- [ ] Worker recovery and idempotent processing.
- [ ] Job state transitions: QUEUED → PROCESSING → COMPLETED/FAILED.

## Later (Modules 5 - 10)
- [ ] AI Grok matching agent with anti-injection prompts (Module 5).
- [ ] Deterministic compliance evaluation and expiration engine (Module 6).
- [ ] Gap reporting lifecycle (Module 7).
- [ ] Full JWT auth and RBAC implementation (Module 8).
- [ ] Aggregated compliance dashboard API (Module 9).
- [ ] Hardening, security testing, and end-to-end demo (Module 10).
