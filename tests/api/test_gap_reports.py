"""API integration tests for gap report endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from src.database.models import (
    ComplianceFramework,
    ComplianceStatus,
    ComplianceStatusRecord,
    GapReport,
    Requirement,
    Severity,
)
from src.database.models.enums import GapStatus, GapType

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
        description="The organization implements logical access security.",
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

    return fw, req


def _create_gap(session, req, gap_status=GapStatus.OPEN):
    gap = GapReport(
        requirement_id=req.id,
        gap_type=GapType.MISSING_EVIDENCE,
        description="Missing access control policy.",
        requested_evidence=["Access control policy document"],
        priority=req.severity,
        status=gap_status,
    )
    session.add(gap)
    session.flush()
    return gap


# ── GET /api/v1/gap-reports ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_gap_reports(async_client_db):
    client, session = async_client_db
    _, req = _seed(session)
    _create_gap(session, req)
    _create_gap(session, req)

    resp = await client.get("/api/v1/gap-reports", headers=AUDITOR_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_list_gap_reports_filter_by_status(async_client_db):
    client, session = async_client_db
    _, req = _seed(session)
    _create_gap(session, req, GapStatus.OPEN)
    _create_gap(session, req, GapStatus.IN_REVIEW)

    resp = await client.get(
        "/api/v1/gap-reports?status=OPEN", headers=AUDITOR_HEADERS
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "OPEN"


@pytest.mark.asyncio
async def test_list_gap_reports_empty(async_client_db):
    client, _ = async_client_db

    resp = await client.get("/api/v1/gap-reports", headers=AUDITOR_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_list_gap_reports_pagination(async_client_db):
    client, session = async_client_db
    _, req = _seed(session)
    for _ in range(5):
        _create_gap(session, req)

    resp = await client.get(
        "/api/v1/gap-reports?page=1&page_size=2", headers=AUDITOR_HEADERS
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["pages"] == 3


@pytest.mark.asyncio
async def test_list_gap_reports_requires_auth(async_client_db):
    client, _ = async_client_db
    resp = await client.get("/api/v1/gap-reports")
    assert resp.status_code == 401


# ── GET /api/v1/gap-reports/{gap_id} ──────────────────────────────────


@pytest.mark.asyncio
async def test_get_gap_report(async_client_db):
    client, session = async_client_db
    _, req = _seed(session)
    gap = _create_gap(session, req)

    resp = await client.get(
        f"/api/v1/gap-reports/{gap.id}", headers=AUDITOR_HEADERS
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(gap.id)
    assert data["gap_type"] == "MISSING_EVIDENCE"
    assert data["status"] == "OPEN"
    assert data["priority"] == "HIGH"


@pytest.mark.asyncio
async def test_get_gap_report_not_found(async_client_db):
    client, _ = async_client_db
    resp = await client.get(
        f"/api/v1/gap-reports/{uuid.uuid4()}", headers=AUDITOR_HEADERS
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_gap_report_requires_auth(async_client_db):
    client, session = async_client_db
    _, req = _seed(session)
    gap = _create_gap(session, req)

    resp = await client.get(f"/api/v1/gap-reports/{gap.id}")
    assert resp.status_code == 401


# ── PATCH /api/v1/gap-reports/{gap_id} ────────────────────────────────


@pytest.mark.asyncio
async def test_update_gap_to_in_review(async_client_db):
    client, session = async_client_db
    _, req = _seed(session)
    gap = _create_gap(session, req)

    resp = await client.patch(
        f"/api/v1/gap-reports/{gap.id}",
        json={"status": "IN_REVIEW"},
        headers=OFFICER_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "IN_REVIEW"


@pytest.mark.asyncio
async def test_update_gap_to_resolved(async_client_db):
    client, session = async_client_db
    _, req = _seed(session)
    gap = _create_gap(session, req, GapStatus.IN_REVIEW)

    resp = await client.patch(
        f"/api/v1/gap-reports/{gap.id}",
        json={"status": "RESOLVED", "resolution_notes": "Evidence provided and verified."},
        headers=OFFICER_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "RESOLVED"
    assert data["resolved_at"] is not None
    assert data["resolution_notes"] == "Evidence provided and verified."


@pytest.mark.asyncio
async def test_update_gap_to_waived(async_client_db):
    client, session = async_client_db
    _, req = _seed(session)
    gap = _create_gap(session, req)

    resp = await client.patch(
        f"/api/v1/gap-reports/{gap.id}",
        json={"status": "WAIVED", "resolution_notes": "Risk accepted by management."},
        headers=OFFICER_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "WAIVED"


@pytest.mark.asyncio
async def test_update_gap_invalid_transition(async_client_db):
    client, session = async_client_db
    _, req = _seed(session)
    gap = _create_gap(session, req, GapStatus.OPEN)

    resp = await client.patch(
        f"/api/v1/gap-reports/{gap.id}",
        json={"status": "RESOLVED"},
        headers=OFFICER_HEADERS,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_gap_requires_officer(async_client_db):
    client, session = async_client_db
    _, req = _seed(session)
    gap = _create_gap(session, req)

    resp = await client.patch(
        f"/api/v1/gap-reports/{gap.id}",
        json={"status": "IN_REVIEW"},
        headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_gap_requires_auth(async_client_db):
    client, session = async_client_db
    _, req = _seed(session)
    gap = _create_gap(session, req)

    resp = await client.patch(
        f"/api/v1/gap-reports/{gap.id}",
        json={"status": "IN_REVIEW"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_gap_not_found(async_client_db):
    client, _ = async_client_db
    resp = await client.patch(
        f"/api/v1/gap-reports/{uuid.uuid4()}",
        json={"status": "IN_REVIEW"},
        headers=OFFICER_HEADERS,
    )
    assert resp.status_code == 404
