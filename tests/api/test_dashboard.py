"""API integration tests for aggregated compliance dashboard endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from src.database.models import (
    ComplianceFramework,
    ComplianceStatus,
    ComplianceStatusRecord,
    DocumentType,
    EvidenceDocument,
    EvidenceValidity,
    GapReport,
    ProcessingStatus,
    Requirement,
    Severity,
)
from src.database.models.enums import GapStatus, GapType

AUDITOR_HEADERS = {"X-Dev-Role": "auditor", "X-Dev-User": "dev-auditor"}
DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _seed(session: Session):
    fw = ComplianceFramework(name="SOC 2 Type II", version="2024-test", is_active=True)
    session.add(fw)
    session.flush()

    req1 = Requirement(
        framework_id=fw.id, requirement_code="CC6.1",
        title="Logical Access", description="Access controls.", severity=Severity.HIGH,
    )
    req2 = Requirement(
        framework_id=fw.id, requirement_code="CC6.2",
        title="Encryption", description="Data encryption.", severity=Severity.MEDIUM,
    )
    session.add_all([req1, req2])
    session.flush()

    csr1 = ComplianceStatusRecord(
        requirement_id=req1.id, status=ComplianceStatus.SATISFIED,
        status_reason="All criteria met.",
    )
    csr2 = ComplianceStatusRecord(
        requirement_id=req2.id, status=ComplianceStatus.GAP,
        status_reason="No evidence.",
    )
    session.add_all([csr1, csr2])
    session.flush()

    gap = GapReport(
        requirement_id=req2.id, gap_type=GapType.MISSING_EVIDENCE,
        description="Missing encryption policy.", requested_evidence=["Encryption policy"],
        priority=Severity.MEDIUM, status=GapStatus.OPEN,
    )
    session.add(gap)
    session.flush()

    evidence = EvidenceDocument(
        filename="policy.txt", document_type=DocumentType.POLICY,
        storage_path="/tmp/test/policy.txt", file_hash="abc123",
        file_size_bytes=1024, uploaded_by=DEV_USER_ID,
        validity_status=EvidenceValidity.VALID, processing_status=ProcessingStatus.PROCESSED,
    )
    session.add(evidence)
    session.flush()

    return fw, req1, req2


# ── GET /api/v1/dashboard/overview ────────────────────────────────────


@pytest.mark.asyncio
async def test_overview(async_client_db):
    client, session = async_client_db
    _seed(session)

    resp = await client.get("/api/v1/dashboard/overview", headers=AUDITOR_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_frameworks"] == 1
    assert data["total_requirements"] == 2
    assert data["satisfied"] == 1
    assert data["gap"] == 1
    assert data["compliance_percentage"] == 50.0
    assert data["open_gaps"] == 1
    assert data["total_evidence"] == 1


@pytest.mark.asyncio
async def test_overview_empty(async_client_db):
    client, _ = async_client_db

    resp = await client.get("/api/v1/dashboard/overview", headers=AUDITOR_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["total_frameworks"] == 0


@pytest.mark.asyncio
async def test_overview_requires_auth(async_client_db):
    client, _ = async_client_db

    resp = await client.get("/api/v1/dashboard/overview")
    assert resp.status_code == 401


# ── GET /api/v1/dashboard/frameworks ──────────────────────────────────


@pytest.mark.asyncio
async def test_frameworks_summary(async_client_db):
    client, session = async_client_db
    _seed(session)

    resp = await client.get("/api/v1/dashboard/frameworks", headers=AUDITOR_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["framework_name"] == "SOC 2 Type II"
    assert data[0]["satisfied"] == 1
    assert data[0]["gap"] == 1


@pytest.mark.asyncio
async def test_frameworks_summary_requires_auth(async_client_db):
    client, _ = async_client_db

    resp = await client.get("/api/v1/dashboard/frameworks")
    assert resp.status_code == 401


# ── GET /api/v1/dashboard/frameworks/{id} ─────────────────────────────


@pytest.mark.asyncio
async def test_framework_detail(async_client_db):
    client, session = async_client_db
    fw, _, _ = _seed(session)

    resp = await client.get(
        f"/api/v1/dashboard/frameworks/{fw.id}", headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_requirements"] == 2
    assert len(data["requirements"]) == 2

    satisfied_req = next(r for r in data["requirements"] if r["status"] == "SATISFIED")
    assert satisfied_req["requirement_code"] == "CC6.1"


@pytest.mark.asyncio
async def test_framework_detail_not_found(async_client_db):
    client, _ = async_client_db

    resp = await client.get(
        f"/api/v1/dashboard/frameworks/{uuid.uuid4()}", headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_framework_detail_requires_auth(async_client_db):
    client, session = async_client_db
    fw, _, _ = _seed(session)

    resp = await client.get(f"/api/v1/dashboard/frameworks/{fw.id}")
    assert resp.status_code == 401


# ── GET /api/v1/dashboard/gaps ────────────────────────────────────────


@pytest.mark.asyncio
async def test_gap_summary(async_client_db):
    client, session = async_client_db
    _seed(session)

    resp = await client.get("/api/v1/dashboard/gaps", headers=AUDITOR_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["by_status"]["OPEN"] == 1
    assert data["by_type"]["MISSING_EVIDENCE"] == 1


@pytest.mark.asyncio
async def test_gap_summary_requires_auth(async_client_db):
    client, _ = async_client_db

    resp = await client.get("/api/v1/dashboard/gaps")
    assert resp.status_code == 401


# ── GET /api/v1/dashboard/evidence ────────────────────────────────────


@pytest.mark.asyncio
async def test_evidence_summary(async_client_db):
    client, session = async_client_db
    _seed(session)

    resp = await client.get("/api/v1/dashboard/evidence", headers=AUDITOR_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["by_validity"]["VALID"] == 1


@pytest.mark.asyncio
async def test_evidence_summary_requires_auth(async_client_db):
    client, _ = async_client_db

    resp = await client.get("/api/v1/dashboard/evidence")
    assert resp.status_code == 401
