# Database Architecture & Schema Documentation

## 1. Overview
The **Compliance Checklist Automation Agent** uses **PostgreSQL** as its primary production source of truth.
For local testing and offline execution, **SQLite** compatibility is supported through SQLAlchemy 2.0 without compromising production constraints.

## 2. Core Schemas & Entity Relationships

### Entity Relationship Diagram
```
COMPLIANCE_FRAMEWORKS (1) ───< REQUIREMENTS (N)
REQUIREMENTS (1) ───< EVIDENCE_MATCHES (N)
REQUIREMENTS (1) ─── (1) COMPLIANCE_STATUS
REQUIREMENTS (1) ───< COMPLIANCE_STATUS_HISTORY (N)
REQUIREMENTS (1) ───< GAP_REPORTS (N)

EVIDENCE_DOCUMENTS (1) ───< EVIDENCE_MATCHES (N)
EVIDENCE_DOCUMENTS (1) ───< DOCUMENT_PROCESSING_JOBS (N)

EVIDENCE_MATCHES (1) ─── (1) COMPLIANCE_STATUS (current_match)
EVIDENCE_MATCHES (1) ───< GAP_REPORTS (N)

USERS (1) ───< EVIDENCE_DOCUMENTS (uploaded_by)
```

## 3. Database Normalization & Integrity Rules
1. **Separation of Status Concepts**:
   - `compliance_status.status`: Enum (`SATISFIED`, `PARTIAL`, `GAP`).
   - `evidence_documents.validity_status`: Enum (`VALID`, `EXPIRING_SOON`, `EXPIRED`).
2. **Immutable AI Audit Ledger**:
   - `evidence_matches` records every evaluation event immutably.
   - Includes `model_name`, `prompt_version`, `citation_verified`, `supporting_evidence` (JSON array), and `confidence` (recorded strictly as metadata).
3. **Current State vs Historical Ledger**:
   - `compliance_status` holds the authoritative snapshot for each requirement (`UNIQUE(requirement_id)`).
   - `compliance_status_history` logs all state transitions with timestamps and reasons.
4. **Durable Job Queue**:
   - `document_processing_jobs` manages durable background execution with lease locking (`locked_at`, `locked_by`), retry counters (`attempts`, `max_attempts`), and failure logging.
5. **Foreign Key Integrity**:
   - Deleting a framework is restricted if requirements exist.
   - Deleting an evidence document cascades to jobs, but restricts deletion if active matches exist.
   - Deleting a requirement cascades to its current compliance status and history.

## 4. Migrations & Versioning
- Tool: **Alembic** (`alembic/`)
- Initial Revision: `0c0c5ce46f4c_0001_initial_schema.py`
- Commands:
  - Upgrade: `alembic upgrade head`
  - Downgrade: `alembic downgrade base`

## 5. Seeded Compliance Frameworks
- **SOC 2 Type II** (`seed/frameworks/soc2_type2.json`): 9 core criteria (CC6.1, CC6.2, CC6.3, CC6.6, CC6.7, CC6.8, CC7.1, CC7.2, CC8.1).
- **ISO/IEC 27001:2022** (`seed/frameworks/iso27001_2022.json`): 8 core controls (A.5.1, A.5.15, A.5.24, A.8.1, A.8.2, A.8.5, A.8.20, A.8.24).
- Seeder execution: `python -m src.database.seed` (fully idempotent).
