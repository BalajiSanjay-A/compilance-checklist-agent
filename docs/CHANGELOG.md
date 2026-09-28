# CHANGELOG: Compliance Checklist Automation Agent

All notable engineering changes to this project will be documented in this file.
This changelog serves as the persistent engineering memory layer alongside git commits.

## [Unreleased] - 2026-09-28

### Added - Module 9: Aggregated Compliance Status Dashboard
- Implemented `DashboardService` in `src/services/dashboard_service.py` with `get_system_overview` (cross-framework totals, compliance percentage, open gaps, evidence stats), `get_all_frameworks_summary` (per-framework compliance scorecard), `get_framework_detail` (requirement-level breakdown with per-requirement gap counts), `get_gap_summary` (counts by status/type/priority), and `get_evidence_summary` (counts by validity/processing status).
- Built Pydantic schemas in `src/schemas/dashboard.py` (`SystemOverview`, `FrameworkSummaryItem`, `RequirementStatusItem`, `FrameworkDetailResponse`, `GapSummary`, `EvidenceSummary`).
- Created 5 REST API endpoints in `src/api/v1/dashboard.py`: `GET /dashboard/overview`, `GET /dashboard/frameworks`, `GET /dashboard/frameworks/{id}`, `GET /dashboard/gaps`, `GET /dashboard/evidence`.
- All dashboard endpoints require auditor role (read-only).
- Added 13 unit tests in `tests/unit/test_dashboard_service.py` covering system overview (empty/populated/gaps/evidence), all-frameworks summary, framework detail (requirements/not-found/gaps), gap summary, and evidence summary.
- Added 12 API integration tests in `tests/api/test_dashboard.py` covering all 5 endpoints with auth enforcement.

### Added - Module 8: Full JWT Authentication & RBAC
- Implemented `AuthService` in `src/services/auth_service.py` with `authenticate_user` (constant-time rejection for nonexistent users), `create_user` (duplicate detection, password length validation), `get_user`, `list_users` (paginated, active filter), `update_user` (role/email/active with duplicate email check), and `change_password` (current password verification).
- Built Pydantic schemas in `src/schemas/auth.py` (`LoginRequest`, `LoginResponse`, `UserCreateRequest`, `UserResponse`, `UserUpdateRequest`, `ChangePasswordRequest`, `PaginatedUsersResponse`).
- Created 8 REST API endpoints in `src/api/v1/auth.py`:
  - `POST /auth/login`: Public login returning JWT with user_id, role, and configurable expiry.
  - `GET /auth/me`: Returns authenticated user identity (from JWT or dev headers, no DB required).
  - `PATCH /auth/me/password`: Authenticated user changes own password (verifies current password first).
  - `POST /auth/users`: Admin creates new user (201).
  - `GET /auth/users`: Admin lists users with pagination and active filter.
  - `GET /auth/users/{id}`: Admin retrieves user by UUID.
  - `PATCH /auth/users/{id}`: Admin updates user role, email, or active status.
- Wired auth router into `api_v1_router`, moved `/auth/me` from router.py to dedicated auth module.
- Added `AuthenticationException` → HTTP 401 mapping in global exception handler.
- Preserved existing X-Dev-Role/X-Dev-User header bypass for test/dev mode — all 274 existing tests unaffected.
- Added 24 unit tests in `tests/unit/test_auth_service.py` covering authentication (valid/wrong/nonexistent/deactivated), user creation (success/duplicate username/duplicate email/short password), get/list/update/change-password with all error paths.
- Added 25 API integration tests in `tests/api/test_auth.py` covering login flow (success/wrong password/nonexistent/deactivated/JWT round-trip), me (dev headers/auth required), password change (success/wrong current/auth), user CRUD (create/duplicate/admin required/auth required), list (filter/admin required), get (found/not found/admin required), update (role/deactivate/not found/admin/auth).

### Added - Module 7: Gap Reporting Lifecycle
- Implemented `GapService` in `src/services/gap_service.py` with `get_gap_report`, `list_gap_reports` (filterable by status, requirement, gap type, priority; paginated), and `update_gap_status` with validated state machine transitions.
- Gap status transitions: `OPEN` → {`IN_REVIEW`, `WAIVED`}, `IN_REVIEW` → {`RESOLVED`, `OPEN`, `WAIVED`}, `WAIVED` → {`OPEN`}, `RESOLVED` → terminal (no transitions).
- Built Pydantic schemas in `src/schemas/gap_report.py` (`GapReportResponse`, `GapReportListItem`, `PaginatedGapReportsResponse`, `GapStatusUpdateRequest`).
- Created 3 REST API endpoints in `src/api/v1/gap_reports.py`: `GET /gap-reports` (paginated with filters), `GET /gap-reports/{id}`, `PATCH /gap-reports/{id}` (status transition).
- Role-based auth: `AuditorDep` for reads, `ComplianceOfficerDep` for status updates.
- Added 17 unit tests in `tests/unit/test_gap_service.py` covering get/not-found, list with all filter combinations, pagination, all valid transitions, terminal state enforcement, and invalid transitions.
- Added 15 API integration tests in `tests/api/test_gap_reports.py` covering list/filter/pagination/auth, get/not-found/auth, and PATCH transitions including invalid/auth enforcement.

### Added - Module 6: Compliance Evaluation Engine
- Implemented `ComplianceEvaluationService` in `src/services/compliance_service.py` with deterministic compliance evaluation pipeline.
- Citation verification: normalized-whitespace exact substring matching (case-insensitive) against raw evidence text. Requires at least 1 verified quote and 0 failures.
- Evidence validity computation: `VALID` / `EXPIRING_SOON` (within 30 days) / `EXPIRED` based on `expires_at` date.
- Deterministic status resolution: expired → GAP, LLM gap → GAP, LLM partial → PARTIAL, failed citations → PARTIAL, missing evidence → PARTIAL, all clear → SATISFIED.
- Full evaluation pipeline (`evaluate_match`): loads entities, verifies citations, checks validity, resolves status, updates `ComplianceStatusRecord`, logs `ComplianceStatusHistory`, auto-generates `GapReport` for non-satisfied results.
- Gap report auto-generation with type classification: `MISSING_EVIDENCE`, `AMBIGUOUS_EVIDENCE`, `PARTIAL_COVERAGE`.
- Expiration refresh scan (`refresh_expiration_status`): batch updates validity status for all evidence with expiration dates.
- Framework compliance summary: aggregated counts and compliance percentage per framework.
- Built Pydantic schemas in `src/schemas/compliance.py` (`ComplianceStatusResponse`, `ComplianceHistoryItem`, `PaginatedHistoryResponse`, `FrameworkComplianceSummary`, `EvaluateAndResolveRequest`).
- Created 5 REST API endpoints in `src/api/v1/compliance.py`: `POST /compliance/evaluate-and-resolve` (full pipeline), `GET /compliance/{framework_id}/status` (scorecard), `GET /compliance/requirements/{id}/status`, `GET /compliance/requirements/{id}/history` (paginated), `POST /compliance/refresh-expiration`.
- Added 34 unit tests in `tests/unit/test_compliance_service.py` covering whitespace normalization, citation verification, validity computation, status resolution, full pipeline, refresh expiration, and framework summary.
- Added 16 API integration tests in `tests/api/test_compliance.py` covering evaluate-and-resolve (success/history/auth/not-found/expired), framework status, requirement status/history, and refresh expiration.

### Added - Module 5: AI Evidence Matching Agent
- Implemented `BaseLLMService` abstract interface, `GrokLLMService` (production xAI/OpenAI-compatible), and `MockLLMService` (deterministic keyword-based) in `src/ai/matching_service.py`.
- Implemented `EvidenceMatchingAgent` with `match_evidence_to_requirement()` that evaluates evidence against requirements using the LLM and persists `EvidenceMatch` records.
- Built structured Pydantic output schema `EvidenceMatchResult` in `src/ai/schemas.py` with status, confidence, reasoning, supporting/missing/requested evidence, and expiration risk.
- Implemented anti-prompt-injection boundaries in `src/ai/prompts.py` using `<UNTRUSTED_EVIDENCE_PAYLOAD>` tags with strict security instructions.
- Created `get_llm_service()` factory: returns `MockLLMService` when `ai_mock_mode=True`, `GrokLLMService` otherwise.
- Built API request/response schemas in `src/schemas/matching.py` (`EvaluateEvidenceRequest`, `EvidenceMatchResponse`, `EvidenceMatchListItem`, `PaginatedMatchesResponse`).
- Created 3 REST API endpoints in `src/api/v1/matching.py`: `POST /compliance/evaluate` (trigger evaluation), `GET /compliance/matches/{id}` (get match details), `GET /compliance/requirements/{id}/matches` (paginated match history).
- Wired matching router into `api_v1_router`.
- Added `AIProviderException` → HTTP 502 mapping in exception handler.
- Role-based auth: `ComplianceOfficerDep` for evaluate, `AuditorDep` for reads.
- Added 24 unit tests in `tests/unit/test_matching_service.py` covering MockLLMService (satisfied/partial/gap/empty), schema validation, factory, agent CRUD, error handling, persistence, and prompt injection boundary.
- Added 15 API integration tests in `tests/api/test_matching.py` covering evaluate, auth enforcement (401/403), not-found (404), no-content (502), invalid input (422), match retrieval, and pagination.

### Added - Module 4: Durable DB-Backed Job Queue & Background Worker
- Implemented `JobQueueService` in `src/services/job_queue_service.py` with enqueue (idempotent), claim (lease-based locking with `SELECT FOR UPDATE SKIP LOCKED` for PostgreSQL, fallback for SQLite), complete, fail (exponential backoff retry), get, and queue stats methods.
- Implemented `DocumentWorker` in `src/workers/document_worker.py` with configurable poll-process loop, signal handling (SIGTERM/SIGINT), extensible job handler registry, and text extraction handler.
- Worker reclaims stale leases from crashed workers based on `worker_lease_timeout_seconds`.
- Exponential backoff: `60 * 2^(attempt-1)` seconds, capped at 3600s.
- Added 20 service unit tests and 6 worker unit tests covering enqueue, claim, retry, failure, backoff, stale lease recovery, and text extraction processing.

### Added - Module 3: Evidence Ingestion & Secure Storage
- Built Pydantic schemas for evidence upload/retrieval in `src/schemas/evidence.py` (`EvidenceUploadResponse`, `EvidenceResponse`, `EvidenceListItem`, `PaginatedEvidenceResponse`).
- Implemented `EvidenceService` in `src/services/evidence_service.py` with secure upload pipeline: filename sanitization, MIME allowlist validation, SHA-256 hashing, hash-based sharded file storage with `0600` permissions, text extraction from PDF/TXT/MD/CSV, evidence validity computation, and automatic job creation for deferred extraction.
- Created 3 REST API endpoints in `src/api/v1/evidence.py`: `POST /evidence/upload` (multipart), `GET /evidence/{id}`, `GET /evidence` (paginated with filters).
- Wired evidence router into `api_v1_router`.
- Seeded deterministic dev user in `async_client_db` test fixture for FK integrity with `uploaded_by`.
- Added 13 API integration tests in `tests/api/test_evidence.py` covering upload, retrieval, listing, pagination, auth enforcement, validity dates, and MIME rejection.
- Added 34 service unit tests in `tests/unit/test_evidence_service.py` covering sanitization, validation, hashing, storage, text extraction, validity computation, and integration with database session.

### Added - Module 2: Framework & Requirement Management APIs
- Built Pydantic request/response schemas for frameworks and requirements in `src/schemas/framework.py` with proper validation constraints and `from_attributes` config.
- Implemented `FrameworkService` in `src/services/framework_service.py` with static methods for full CRUD on frameworks and requirements, including paginated requirement listing, duplicate detection, and automatic baseline GAP status initialization.
- Created 8 REST API endpoints in `src/api/v1/frameworks.py`: `GET/POST /frameworks`, `GET/PATCH /frameworks/{id}`, `GET/POST /frameworks/{id}/requirements`, `GET/PATCH /requirements/{id}`.
- Wired frameworks router into `api_v1_router` in `src/api/v1/router.py`.
- Fixed global exception handler in `src/main.py` to map `EntityNotFoundException` → HTTP 404, `DuplicateEntityException` → HTTP 409, `ValidationException` → HTTP 422 (previously all mapped to 400).
- Enforced role-based access: `ComplianceOfficerDep` for write operations, `AuditorDep` for reads.
- Added `async_client_db` test fixture in `tests/conftest.py` providing transaction-isolated API testing with nested savepoints.
- Added 28 API integration tests in `tests/api/test_frameworks.py` covering all endpoints, auth enforcement (401/403), not-found (404), duplicates (409), validation (422), pagination, and severity filtering.
- Added 19 service unit tests in `tests/unit/test_framework_service.py` covering all CRUD operations, error paths, pagination, filtering, and GAP status auto-creation.

## [Previous] - 2026-09-27

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
