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
   - Includes `model_name`, `prompt_version`, `citation_verified`, `supporting_evidence` (JSONB array), and `confidence` (recorded strictly as metadata).
3. **Current State vs Historical Ledger**:
   - `compliance_status` holds the authoritative snapshot for each requirement (`UNIQUE(requirement_id)`).
   - `compliance_status_history` logs all state transitions with timestamps and reasons.
4. **Durable Job Queue**:
   - `document_processing_jobs` manages durable background execution with lease locking, retry counters, and failure logging.
