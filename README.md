# Compliance Checklist Automation Agent

AI-powered compliance checklist automation agent for evidence matching, gap detection, and compliance status tracking across frameworks like SOC 2 Type II and ISO/IEC 27001:2022.

## Features

- **Framework & Requirement Management**: Create and manage compliance frameworks with requirements, severities, and tracking.
- **Evidence Ingestion**: Secure document upload with MIME validation, SHA-256 hashing, text extraction (PDF, TXT, MD, CSV), and expiration tracking.
- **AI Evidence Matching**: Grok (xAI API) evaluates evidence against requirements with structured reasoning, citations, and confidence scoring. Anti-prompt-injection boundaries protect the evaluation pipeline.
- **Deterministic Compliance Evaluation**: Citation verification, expiration checks, and status resolution (SATISFIED / PARTIAL / GAP) — the LLM advises, the application decides.
- **Gap Reporting Lifecycle**: Auto-generated gap reports with status workflow (OPEN → IN_REVIEW → RESOLVED / WAIVED).
- **Aggregated Dashboard**: Cross-framework compliance overview, per-requirement breakdowns, gap and evidence statistics.
- **Authentication & RBAC**: JWT-based authentication with three roles — `compliance-officer` (writes), `auditor` (reads), `admin` (user management).
- **Background Processing**: Durable database-backed job queue with lease-based locking and exponential backoff retry.

## Quick Start

### Prerequisites
- Python 3.12+
- PostgreSQL (production) or SQLite (dev/test fallback)

### Setup

```bash
# Clone and enter the project
git clone <repository-url>
cd compliance-checklist-agent

# Create virtual environment and install
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your settings (database URL, secret key, xAI API key)

# Run database migrations
alembic upgrade head

# Seed initial frameworks and admin user
python -m src.database.seed

# Start the server
uvicorn src.main:app --reload
```

### Running Tests

```bash
# All tests (uses SQLite in-memory, mock LLM)
pytest

# With coverage
pytest --cov=src --cov-report=term-missing
```

### Configuration

Key environment variables (see `.env.example` for full list):

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | `development`, `test`, or `production` |
| `SECRET_KEY` | (insecure default) | JWT signing key — **must change for production** |
| `DATABASE_URL` | `postgresql://...` | PostgreSQL connection string |
| `USE_SQLITE_FALLBACK` | `false` | Use SQLite instead of PostgreSQL |
| `AI_MOCK_MODE` | `true` | Use deterministic mock LLM (no API calls) |
| `XAI_API_KEY` | (empty) | xAI API key for Grok evaluations |
| `MAX_UPLOAD_SIZE_MB` | `25` | Maximum evidence file upload size |

### API Documentation

Once the server is running, interactive API docs are available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Default Roles

| Role | Access |
|---|---|
| `compliance-officer` | Upload evidence, trigger evaluations, manage gaps, manage frameworks |
| `auditor` | Read-only access to all compliance data, dashboard, and audit history |
| `admin` | User account management (create, update, deactivate) |

## Architecture

- **FastAPI** REST API with Pydantic v2 schemas
- **SQLAlchemy 2.0** ORM with Alembic migrations
- **PostgreSQL** (production) / **SQLite** (testing)
- **Grok (xAI)** via LangChain for evidence evaluation
- Modular service layer with dependency injection
- Immutable audit ledger for evidence matches and compliance history
