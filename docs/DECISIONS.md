# Architecture Decision Records (ADRs)

## ADR-001: Modular Monolith vs Distributed Architecture
- **Context**: Regulatory compliance tracking requires high auditability, durability, and atomic state transitions without unnecessary operational complexity.
- **Decision**: Build the application as a clean, modular monolith with FastAPI and PostgreSQL. Do not introduce Redis, Celery, Vector Databases, or microservices.
- **Consequences**: Greatly simplified local development, deterministic debugging, and single-database transactional guarantees.

## ADR-002: Separation of Compliance Status and Evidence Validity
- **Context**: Documents expire over time (e.g. certificates), but requirement status should describe whether compliance is satisfied or in a gap.
- **Decision**: Compliance status is strictly `SATISFIED`, `PARTIAL`, `GAP`. Evidence validity is tracked separately as `VALID`, `EXPIRING_SOON`, `EXPIRED`.
- **Consequences**: Clean domain modeling; expiration logic deterministically updates requirements relying on expired evidence to `GAP`.

## ADR-003: LLM as Advisory Evaluator, Not Authoritative Decision Maker
- **Context**: LLMs can hallucinate and be subject to prompt injection from untrusted documents.
- **Decision**: LLM provides structured evaluation recommendations. The application deterministically verifies cited quotes against raw text and checks expiration before altering database state.
- **Consequences**: Guarantees verifiable audits and prevents prompt injection attacks from compromising compliance status.

## ADR-004: In-Database Durable Job Queue
- **Context**: Document processing and evaluation need to be asynchronous and retryable without adding Redis/Celery.
- **Decision**: Implement a database-backed job queue table (`document_processing_jobs`) using lease-based locking and exponential backoff.
- **Consequences**: Zero external infrastructure dependencies; completely transactional and durable.
