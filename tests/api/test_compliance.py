"""API integration tests for compliance evaluation endpoints."""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from src.database.models import (
    ComplianceFramework,
    ComplianceStatus,
    ComplianceStatusHistory,
    ComplianceStatusRecord,
    DocumentType,
    EvidenceDocument,
    EvidenceValidity,
    ProcessingStatus,
    Requirement,
    Severity,
)

OFFICER_HEADERS = {"X-Dev-Role": "compliance-officer", "X-Dev-User": "dev-officer"}
AUDITOR_HEADERS = {"X-Dev-Role": "auditor", "X-Dev-User": "dev-auditor"}


def _seed(session: Session):
    fw = ComplianceFramework(
        name="SOC 2 Type II", version="2024-test", is_active=True,
    )
    session.add(fw)
    session.flush()

    req = Requirement(
        framework_id=fw.id,
        requirement_code="CC6.1",
        title="Logical Access Controls",
        description="The organization implements logical access security measures.",
        severity=Severity.HIGH,
    )
    session.add(req)
    session.flush()

    csr = ComplianceStatusRecord(
        requirement_id=req.id,
        status=ComplianceStatus.GAP,
        status_reason="Initial baseline",
    )
    session.add(csr)
    session.flush()

    evidence = EvidenceDocument(
        filename="access_policy.txt",
        document_type=DocumentType.POLICY,
        storage_path="/tmp/test/access_policy.txt",
        content_text="Our organization implements logical access controls including MFA and role-based access.",
        file_hash="abc123def456",
        file_size_bytes=2048,
        uploaded_by=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        validity_status=EvidenceValidity.VALID,
        processing_status=ProcessingStatus.PROCESSED,
    )
    session.add(evidence)
    session.flush()

    return fw, req, evidence


# ── POST /api/v1/compliance/evaluate-and-resolve ───────────────────────


@pytest.mark.asyncio
async def test_evaluate_and_resolve_success(async_client_db):
    client, session = async_client_db
    _, req, evidence = _seed(session)

    resp = await client.post(
        "/api/v1/compliance/evaluate-and-resolve",
        json={"evidence_id": str(evidence.id), "requirement_id": str(req.id)},
        headers=OFFICER_HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["requirement_id"] == str(req.id)
    assert data["status"] in ["SATISFIED", "PARTIAL", "GAP"]
    assert data["current_match_id"] is not None
    assert data["last_evaluated_at"] is not None


@pytest.mark.asyncio
async def test_evaluate_and_resolve_creates_history(async_client_db):
    client, session = async_client_db
    _, req, evidence = _seed(session)

    await client.post(
        "/api/v1/compliance/evaluate-and-resolve",
        json={"evidence_id": str(evidence.id), "requirement_id": str(req.id)},
        headers=OFFICER_HEADERS,
    )

    history = session.query(ComplianceStatusHistory).filter(
        ComplianceStatusHistory.requirement_id == req.id
    ).all()
    assert len(history) >= 1


@pytest.mark.asyncio
async def test_evaluate_and_resolve_requires_officer(async_client_db):
    client, session = async_client_db
    _, req, evidence = _seed(session)

    resp = await client.post(
        "/api/v1/compliance/evaluate-and-resolve",
        json={"evidence_id": str(evidence.id), "requirement_id": str(req.id)},
        headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_evaluate_and_resolve_requires_auth(async_client_db):
    client, session = async_client_db
    _, req, evidence = _seed(session)

    resp = await client.post(
        "/api/v1/compliance/evaluate-and-resolve",
        json={"evidence_id": str(evidence.id), "requirement_id": str(req.id)},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_evaluate_and_resolve_evidence_not_found(async_client_db):
    client, session = async_client_db
    _, req, _ = _seed(session)

    resp = await client.post(
        "/api/v1/compliance/evaluate-and-resolve",
        json={"evidence_id": str(uuid.uuid4()), "requirement_id": str(req.id)},
        headers=OFFICER_HEADERS,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_evaluate_and_resolve_expired_evidence_forces_gap(async_client_db):
    client, session = async_client_db
    _, req, evidence = _seed(session)
    evidence.expires_at = date.today() - timedelta(days=5)
    session.flush()

    resp = await client.post(
        "/api/v1/compliance/evaluate-and-resolve",
        json={"evidence_id": str(evidence.id), "requirement_id": str(req.id)},
        headers=OFFICER_HEADERS,
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "GAP"


# ── GET /api/v1/compliance/{framework_id}/status ───────────────────────


@pytest.mark.asyncio
async def test_framework_compliance_status(async_client_db):
    client, session = async_client_db
    fw, req, _ = _seed(session)

    resp = await client.get(
        f"/api/v1/compliance/{fw.id}/status",
        headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["framework_name"] == "SOC 2 Type II"
    assert data["total_requirements"] == 1
    assert data["gap"] == 1
    assert data["compliance_percentage"] == 0.0


@pytest.mark.asyncio
async def test_framework_compliance_status_not_found(async_client_db):
    client, _ = async_client_db

    resp = await client.get(
        f"/api/v1/compliance/{uuid.uuid4()}/status",
        headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_framework_status_requires_auth(async_client_db):
    client, session = async_client_db
    fw, _, _ = _seed(session)

    resp = await client.get(f"/api/v1/compliance/{fw.id}/status")
    assert resp.status_code == 401


# ── GET /api/v1/compliance/requirements/{id}/status ────────────────────


@pytest.mark.asyncio
async def test_requirement_compliance_status(async_client_db):
    client, session = async_client_db
    _, req, _ = _seed(session)

    resp = await client.get(
        f"/api/v1/compliance/requirements/{req.id}/status",
        headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "GAP"
    assert data["status_reason"] == "Initial baseline"


@pytest.mark.asyncio
async def test_requirement_status_not_found(async_client_db):
    client, _ = async_client_db

    resp = await client.get(
        f"/api/v1/compliance/requirements/{uuid.uuid4()}/status",
        headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 404


# ── GET /api/v1/compliance/requirements/{id}/history ───────────────────


@pytest.mark.asyncio
async def test_compliance_history_after_evaluation(async_client_db):
    client, session = async_client_db
    _, req, evidence = _seed(session)

    await client.post(
        "/api/v1/compliance/evaluate-and-resolve",
        json={"evidence_id": str(evidence.id), "requirement_id": str(req.id)},
        headers=OFFICER_HEADERS,
    )

    resp = await client.get(
        f"/api/v1/compliance/requirements/{req.id}/history",
        headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["items"][0]["previous_status"] == "GAP"


@pytest.mark.asyncio
async def test_compliance_history_empty(async_client_db):
    client, session = async_client_db
    _, req, _ = _seed(session)

    resp = await client.get(
        f"/api/v1/compliance/requirements/{req.id}/history",
        headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_compliance_history_requires_auth(async_client_db):
    client, session = async_client_db
    _, req, _ = _seed(session)

    resp = await client.get(
        f"/api/v1/compliance/requirements/{req.id}/history",
    )
    assert resp.status_code == 401


# ── POST /api/v1/compliance/refresh-expiration ─────────────────────────


@pytest.mark.asyncio
async def test_refresh_expiration(async_client_db):
    client, session = async_client_db
    _, _, evidence = _seed(session)
    evidence.expires_at = date.today() - timedelta(days=1)
    evidence.validity_status = EvidenceValidity.VALID
    session.flush()

    resp = await client.post(
        "/api/v1/compliance/refresh-expiration",
        headers=OFFICER_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["updated_count"] == 1


@pytest.mark.asyncio
async def test_refresh_expiration_requires_officer(async_client_db):
    client, _ = async_client_db

    resp = await client.post(
        "/api/v1/compliance/refresh-expiration",
        headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 403
