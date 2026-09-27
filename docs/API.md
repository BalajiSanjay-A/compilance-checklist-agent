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
- `GET /api/v1/frameworks`: List all active compliance frameworks.
- `POST /api/v1/frameworks`: Register or seed a framework.
- `GET /api/v1/frameworks/{id}/requirements`: List requirements for a framework.
- `POST /api/v1/frameworks/{id}/requirements`: Add a requirement to a framework.
- `POST /api/v1/evidence/upload`: Upload evidence document (multipart).
- `GET /api/v1/evidence/{id}`: Inspect evidence metadata and processing status.
- `GET /api/v1/compliance/{framework_id}/status`: Aggregated compliance status scorecard.
- `POST /api/v1/compliance/evaluate`: Trigger evidence matching against a requirement.
- `GET /api/v1/compliance/requirements/{id}/history`: Full audit trail for a requirement.
- `GET /api/v1/gap-reports`: List open, in-review, or resolved gap reports.
- `PATCH /api/v1/gap-reports/{id}`: Resolve or waive a gap report.
