# Engineering Task Board

## Now (Module 0)
- [x] Python environment & dependencies (`pyproject.toml`, `requirements.txt`).
- [x] Context engineering documentation system in `docs/`.
- [ ] Application configuration in `src/config.py`.
- [ ] Structured logging with secret scrubbing in `src/core/logging.py`.
- [ ] Base domain exceptions in `src/core/exceptions.py`.
- [ ] Early authentication & role boundary scaffolding in `src/core/security.py`.
- [ ] FastAPI entrypoint & health checks in `src/main.py`.
- [ ] Pytest testing harness and initial test suite.

## Next (Module 1)
- [ ] SQLAlchemy 2.0 DeclarativeBase & UUID mixins.
- [ ] Relational models (`compliance_frameworks`, `requirements`, `evidence_documents`, `evidence_matches`, `compliance_status`, `compliance_status_history`, `gap_reports`, `document_processing_jobs`, `users`).
- [ ] Alembic migration initialization.
- [ ] Seed frameworks (SOC 2 Type II, ISO/IEC 27001:2022).

## Later (Modules 2 - 10)
- [ ] Framework and requirement management APIs (Module 2).
- [ ] Secure evidence ingestion and text extraction (Module 3).
- [ ] Durable database-backed job queue and background worker (Module 4).
- [ ] AI Grok matching agent with anti-injection prompts (Module 5).
- [ ] Deterministic compliance evaluation and expiration engine (Module 6).
- [ ] Gap reporting lifecycle (Module 7).
- [ ] Full JWT auth and RBAC implementation (Module 8).
- [ ] Aggregated compliance dashboard API (Module 9).
- [ ] Hardening, security testing, and end-to-end demo (Module 10).
