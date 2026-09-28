# API Specifications & Contracts

## 1. Overview
The API is built using **FastAPI** adhering to RESTful conventions.
All requests and responses use JSON (except multipart file uploads) and strictly validated Pydantic schemas.

## 2. Authentication & Authorization Boundaries
- **Header**: `Authorization: Bearer <token>`
- **Roles**:
  - `compliance-officer`: Full access to upload evidence, trigger evaluations, resolve gap reports, manage frameworks.
  - `auditor`: Read-only access to frameworks, compliance status, evidence citations, and audit history.
  - `admin`: User and system management.

## 3. Core Endpoint Catalog
- `GET /health` & `GET /api/v1/health`: System health and connectivity.
- `POST /api/v1/auth/login`: Authenticate and receive JWT token.
- `GET /api/v1/auth/me`: Inspect current user and active role.
- `GET /api/v1/frameworks`: List compliance frameworks (optional `?is_active=` filter). **Implemented (Module 2).**
- `POST /api/v1/frameworks`: Register a new framework. Returns 201. **Implemented (Module 2).**
- `GET /api/v1/frameworks/{id}`: Get single framework with requirement count. **Implemented (Module 2).**
- `PATCH /api/v1/frameworks/{id}`: Partial update framework metadata. **Implemented (Module 2).**
- `GET /api/v1/frameworks/{id}/requirements`: Paginated requirements with `?is_active=`, `?severity=`, `?page=`, `?page_size=` filters. **Implemented (Module 2).**
- `POST /api/v1/frameworks/{id}/requirements`: Add requirement to framework; auto-creates baseline GAP status. Returns 201. **Implemented (Module 2).**
- `GET /api/v1/requirements/{id}`: Get single requirement by UUID. **Implemented (Module 2).**
- `PATCH /api/v1/requirements/{id}`: Partial update requirement. **Implemented (Module 2).**
- `POST /api/v1/evidence/upload`: Multipart file upload with `document_type`, `valid_from`, `expires_at` form fields. MIME allowlist: PDF, TXT, MD, CSV. Max 25MB. SHA-256 hashing. Returns 201. **Implemented (Module 3).**
- `GET /api/v1/evidence/{id}`: Full evidence metadata including content text and processing status. **Implemented (Module 3).**
- `GET /api/v1/evidence`: Paginated evidence list with `?document_type=`, `?validity_status=`, `?processing_status=`, `?page=`, `?page_size=` filters. **Implemented (Module 3).**
- `POST /api/v1/compliance/evaluate`: Trigger AI evidence matching against a requirement. Accepts `evidence_id` and `requirement_id`. Returns structured match result with status, confidence, reasoning, and citations. Requires compliance-officer role. Returns 201. **Implemented (Module 5).**
- `GET /api/v1/compliance/matches/{id}`: Retrieve full details of an evidence match evaluation by UUID. **Implemented (Module 5).**
- `GET /api/v1/compliance/requirements/{id}/matches`: Paginated list of all evidence match evaluations for a requirement with `?page=`, `?page_size=` parameters. **Implemented (Module 5).**
- `POST /api/v1/compliance/evaluate-and-resolve`: Full pipeline: AI evidence matching + deterministic compliance evaluation. Accepts `evidence_id` and `requirement_id`. Returns updated compliance status with match reference, history, and auto-generated gap report if non-satisfied. Requires compliance-officer role. Returns 201. **Implemented (Module 6).**
- `GET /api/v1/compliance/{framework_id}/status`: Aggregated compliance status scorecard with counts (satisfied/partial/gap/not_evaluated) and compliance percentage. Requires auditor role. **Implemented (Module 6).**
- `GET /api/v1/compliance/requirements/{id}/status`: Current compliance status for a specific requirement. Requires auditor role. **Implemented (Module 6).**
- `GET /api/v1/compliance/requirements/{id}/history`: Paginated audit trail of compliance status transitions for a requirement with `?page=`, `?page_size=` parameters. Requires auditor role. **Implemented (Module 6).**
- `POST /api/v1/compliance/refresh-expiration`: Scan all evidence and update validity statuses based on current date. Returns count of updated records. Requires compliance-officer role. **Implemented (Module 6).**
- `GET /api/v1/gap-reports`: Paginated list of gap reports with `?status=`, `?requirement_id=`, `?gap_type=`, `?priority=`, `?page=`, `?page_size=` filters. Ordered by priority desc, detected_at desc. Requires auditor role. **Implemented (Module 7).**
- `GET /api/v1/gap-reports/{id}`: Retrieve full gap report details by UUID. Requires auditor role. **Implemented (Module 7).**
- `PATCH /api/v1/gap-reports/{id}`: Update gap report status with validated state machine transitions. Accepts `status` and optional `resolution_notes`. Requires compliance-officer role. **Implemented (Module 7).**
