# PROJECT CONTEXT: Compliance Checklist Automation Agent

## 1. System Overview
The **Compliance Checklist Automation Agent** is a production-oriented, AI-assisted regulatory compliance platform designed to track recurring checklist items across frameworks (e.g., SOC 2 Type II, ISO/IEC 27001:2022). It handles evidence document ingestion, secure text extraction, asynchronous evidence matching against compliance requirements using Grok (xAI API), deterministic compliance state calculation, evidence expiration management, and actionable gap reporting.

## 2. Current Architecture & Implementation State
- **Current Milestone**: Module 9 - Aggregated Compliance Status Dashboard (Completed)
- **Active Branch**: `temporary` (all development occurs here; merges to `main` at module completion gates)
- **Status**: Cross-framework compliance dashboard with system overview, per-framework summaries, detailed requirement breakdowns, gap and evidence statistics. 348 total tests passing. Ready for Module 10.

## 3. Technology Stack
- **Language & Runtime**: Python 3.12+
- **API Framework**: FastAPI
- **Database**: PostgreSQL (Production source of truth); SQLite compatibility for fast, isolated testing
- **ORM & Migrations**: SQLAlchemy 2.0 (Declarative Base), Alembic
- **AI / LLM**: Grok (xAI API) via LangChain / custom adapter with strict anti-injection prompt boundaries; Mock LLM for deterministic tests
- **Durable Queue**: Database-backed job queue (`document_processing_jobs`) with lease-based locking and retry mechanisms
- **Testing**: Pytest, Pytest-asyncio, HTTPX

## 4. Key Architectural & Domain Rules
1. **Separation of Concerns**:
   - **Compliance Status**: Strictly `SATISFIED`, `PARTIAL`, `GAP`.
   - **Evidence Validity**: Modeled separately as `VALID`, `EXPIRING_SOON`, `EXPIRED`.
2. **Deterministic Compliance Approval**:
   - The LLM advises and extracts structured evidence quotes; the application enforces authoritative compliance state.
   - Confidence score is audit metadata only.
   - Approval strictly requires: structured criteria match, verbatim citation verification against raw document text, and active validity date checks.
3. **Prompt Injection & Untrusted Input Defenses**:
   - Evidence text is enclosed in `<UNTRUSTED_EVIDENCE_PAYLOAD>` with strict instructions forbidding tool invocation or system prompt overrides.
   - The LLM cannot mutate database state or approve without evidence.
4. **Early Authentication & Authorization Boundaries**:
   - `Role` constants (`compliance-officer`, `admin`, `auditor`) and `require_role(...)` dependency boundaries established in Module 0.
5. **Database Source of Truth & Normalization**:
   - Many-to-many relationship: One evidence document can match multiple requirements; one requirement can evaluate multiple evidence documents over time.
   - `evidence_matches` is an immutable append-only evaluation ledger.
   - `compliance_status` represents the current state snapshot per requirement (`UNIQUE(requirement_id)`).
   - `compliance_status_history` logs state transitions.

## 5. Important Files & Locations
- `src/config.py`: Centralized environment configuration via Pydantic Settings.
- `src/database/base.py`: SQLAlchemy 2.0 DeclarativeBase, UUIDPrimaryKeyMixin, TimestampMixin.
- `src/database/session.py`: Engine, sessionmaker, transactional_session, and SQLite PRAGMA configuration.
- `src/database/models/`: Entity definitions (`framework.py`, `evidence.py`, `match.py`, `compliance.py`, `gap_report.py`, `user.py`, `enums.py`).
- `src/database/seed.py`: Idempotent seeder for compliance frameworks, requirements, and default admin user.
- `seed/frameworks/`: Built-in seed frameworks (`soc2_type2.json`, `iso27001_2022.json`).
- `alembic/versions/0c0c5ce46f4c_0001_initial_schema.py`: Initial migration for all tables.
- `src/core/logging.py`: Structured JSON logging with credential and secret scrubbing.
- `src/core/security.py`: Auth boundaries, role definitions, and dependency guards.
- `src/main.py`: FastAPI application entrypoint.
- `src/schemas/framework.py`: Pydantic schemas for frameworks and requirements.
- `src/services/framework_service.py`: Business logic for framework/requirement CRUD.
- `src/api/v1/frameworks.py`: REST API endpoints for frameworks and requirements.
- `src/schemas/evidence.py`: Pydantic schemas for evidence upload/retrieval.
- `src/services/evidence_service.py`: Evidence upload, storage, hashing, text extraction.
- `src/api/v1/evidence.py`: REST API endpoints for evidence management.
- `src/services/job_queue_service.py`: Durable job queue with lease-based locking and retry.
- `src/workers/document_worker.py`: Background worker for document processing jobs.
- `src/ai/matching_service.py`: LLM abstraction (BaseLLMService), GrokLLMService, MockLLMService, EvidenceMatchingAgent.
- `src/ai/prompts.py`: Anti-injection prompt templates with `<UNTRUSTED_EVIDENCE_PAYLOAD>` boundary.
- `src/ai/schemas.py`: Pydantic structured output schema for LLM evidence evaluation.
- `src/schemas/matching.py`: API request/response schemas for evidence matching.
- `src/api/v1/matching.py`: REST API endpoints for compliance evaluation and match retrieval.
- `src/services/compliance_service.py`: Deterministic compliance evaluation engine with citation verification, expiration checks, and status resolution.
- `src/schemas/compliance.py`: Pydantic schemas for compliance status, history, and framework summary.
- `src/api/v1/compliance.py`: REST API endpoints for compliance evaluation, status, history, and expiration refresh.
- `src/services/gap_service.py`: Gap report CRUD and status transition lifecycle.
- `src/schemas/gap_report.py`: Pydantic schemas for gap reports and status updates.
- `src/api/v1/gap_reports.py`: REST API endpoints for gap report listing, retrieval, and status transitions.
- `src/services/auth_service.py`: User authentication, creation, management, and password operations.
- `src/schemas/auth.py`: Pydantic schemas for login, user CRUD, and password change.
- `src/api/v1/auth.py`: REST API endpoints for login, user profile, password change, and user management.
- `src/services/dashboard_service.py`: Aggregated compliance dashboard queries across frameworks, requirements, gaps, and evidence.
- `src/schemas/dashboard.py`: Pydantic schemas for dashboard responses.
- `src/api/v1/dashboard.py`: REST API endpoints for compliance dashboard views.
- `docs/`: Canonical engineering context documents.

## 6. Milestone Progress
- [x] **Module 0**: Project Foundation, Settings, Logging, Auth Boundaries, Context System, Test Harness *(Completed)*
- [x] **Module 1**: Database Foundation & Schemas, Alembic Migrations, Seed Data *(Completed)*
- [x] **Module 2**: Framework & Requirement Management APIs *(Completed)*
- [x] **Module 3**: Evidence Ingestion & Secure Storage *(Completed)*
- [x] **Module 4**: Durable DB-Backed Job Queue & Background Worker *(Completed)*
- [x] **Module 5**: AI Evidence Matching Agent *(Completed)*
- [x] **Module 6**: Compliance Evaluation Engine & Expiration *(Completed)*
- [x] **Module 7**: Gap Reporting Lifecycle *(Completed)*
- [x] **Module 8**: Full JWT Auth & RBAC *(Completed)*
- [x] **Module 9**: Aggregated Compliance Status Dashboard *(Completed)*
- [ ] **Module 10**: Hardening, E2E Verification & Demo
