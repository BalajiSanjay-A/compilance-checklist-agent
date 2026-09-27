# System Architecture & Boundaries

## 1. Architectural Philosophy
The **Compliance Checklist Automation Agent** is architected as a **clean, modular monolith**.
It avoids premature distributed infrastructure (such as Redis, Celery, Vector Databases, or microservices) in favor of simple, auditable, and durable database-backed components with explicit layer separation.

## 2. Layer Separation & Dependency Flow
```
Client / Compliance Officer
        │ (HTTP / JSON / JWT)
        ▼
   API Layer (FastAPI Routers)
        │ (DTOs / Request Schemas / Injected Dependencies)
        ▼
Domain & Business Logic Layer (Services)
        │
   ┌────┴──────────────────────────┐
   ▼                               ▼
AI / LLM Services             Data Access & Storage
(Grok xAI / Mock LLM)        (SQLAlchemy / Filesystem)
```

1. **API Layer (`src/api/`)**:
   - Thin route handlers responsible strictly for request validation, role enforcement, calling domain services, and returning serialized response models.
   - No direct database writes or LLM calls in route handlers.
2. **Business Logic Layer (`src/services/`)**:
   - Encapsulates compliance domain rules: framework management, evidence validation, deterministic compliance status transitions, and gap report lifecycles.
3. **Data Access Layer (`src/database/`)**:
   - SQLAlchemy 2.0 models, declarative base, and explicit transactional sessions.
   - PostgreSQL as production target; SQLite support for fast deterministic tests.
4. **AI & Agent Layer (`src/ai/`)**:
   - Pluggable LLM interface (`BaseLLMService`) with implementations `GrokLLMService` and `MockLLMService`.
   - Untrusted evidence sanitization and prompt injection isolation.
5. **Durable Processing Layer (`src/jobs/`)**:
   - Transactional, database-backed job queue with lease-based locking and retry policies.

## 3. Core Domain Boundary: Compliance Status vs Evidence Validity
- **Compliance Status**: Exactly `SATISFIED`, `PARTIAL`, `GAP`.
- **Evidence Validity**: Exactly `VALID`, `EXPIRING_SOON`, `EXPIRED`.
- The application evaluates evidence validity deterministically and transitions compliance status to `GAP` upon evidence expiration.

## 4. Multi-Factor Compliance Approval Engine
Approval of a requirement requires satisfying all of:
1. Structured LLM recommendation against requirement criteria.
2. Exact verbatim quote verification: every supporting quote must exist in the source document.
3. Absence of remaining unresolved missing items.
4. Active validity of evidence (`today <= expires_at`).
*LLM confidence score is recorded strictly as metadata.*
