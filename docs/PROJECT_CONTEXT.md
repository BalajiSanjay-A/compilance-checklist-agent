# PROJECT CONTEXT: Compliance Checklist Automation Agent

## 1. System Overview
The **Compliance Checklist Automation Agent** is a production-oriented, AI-assisted regulatory compliance platform designed to track recurring checklist items across frameworks (e.g., SOC 2 Type II, ISO/IEC 27001:2022). It handles evidence document ingestion, secure text extraction, asynchronous evidence matching against compliance requirements using Grok (xAI API), deterministic compliance state calculation, evidence expiration management, and actionable gap reporting.

## 2. Current Architecture & Implementation State
- **Current Milestone**: Module 0 - Project Foundation & Context Engineering
- **Active Branch**: `temporary` (all development occurs here; merges to `main` at module completion gates)
- **Status**: Scaffolding project foundation, dependency management, Pydantic settings, structured logging, auth boundary stubs, and engineering documentation memory layer.

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

## 5. Important Files & Locations
- `src/config.py`: Centralized environment configuration via Pydantic Settings.
- `src/core/logging.py`: Structured JSON logging with credential and secret scrubbing.
- `src/core/security.py`: Auth boundaries, role definitions, and dependency guards.
- `src/core/exceptions.py`: Standard domain exception hierarchy.
- `src/main.py`: FastAPI application entrypoint and health checks.
- `docs/`: Canonical engineering context documents.

## 6. Milestone Progress
- [x] **Module 0**: Project Foundation, Settings, Logging, Auth Boundaries, Context System, Test Harness *(Completed)*
- [ ] **Module 1**: Database Foundation & Schemas
- [ ] **Module 2**: Framework & Requirement Management APIs
- [ ] **Module 3**: Evidence Ingestion & Secure Storage
- [ ] **Module 4**: Durable DB-Backed Job Queue
- [ ] **Module 5**: AI Grok Matching Agent
- [ ] **Module 6**: Compliance Evaluation Engine & Expiration
- [ ] **Module 7**: Gap Reporting Lifecycle
- [ ] **Module 8**: Full JWT Auth & RBAC
- [ ] **Module 9**: Aggregated Compliance Status Dashboard
- [ ] **Module 10**: Hardening, E2E Verification & Demo
