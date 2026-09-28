"""API integration tests for evidence matching endpoints."""

import uuid
from datetime import date

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
    ProcessingStatus,
    Requirement,
    Severity,
)

OFFICER_HEADERS = {"X-Dev-Role": "compliance-officer", "X-Dev-User": "dev-officer"}
AUDITOR_HEADERS = {"X-Dev-Role": "auditor", "X-Dev-User": "dev-auditor"}


def _seed_framework_and_evidence(session: Session):
    """Seed a framework, requirement, and evidence document for matching tests."""
    framework = ComplianceFramework(
        name="SOC 2 Type II",
        version="2024-test",
        description="SOC 2 for testing",
        is_active=True,
    )
    session.add(framework)
    session.flush()

    requirement = Requirement(
        framework_id=framework.id,
        requirement_code="CC6.1",
        title="Logical Access Controls",
        description="The organization implements logical access security measures.",
        severity=Severity.HIGH,
    )
    session.add(requirement)
    session.flush()

    status_record = ComplianceStatusRecord(
        requirement_id=requirement.id,
        status=ComplianceStatus.GAP,
        status_reason="Initial baseline",
    )
    session.add(status_record)
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

    return framework, requirement, evidence


# ── POST /api/v1/compliance/evaluate ───────────────────────────────────


@pytest.mark.asyncio
async def test_evaluate_evidence_success(async_client_db):
    client, session = async_client_db
    _, requirement, evidence = _seed_framework_and_evidence(session)

    resp = await client.post(
        "/api/v1/compliance/evaluate",
        json={
            "evidence_id": str(evidence.id),
            "requirement_id": str(requirement.id),
        },
        headers=OFFICER_HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["evidence_id"] == str(evidence.id)
    assert data["requirement_id"] == str(requirement.id)
    assert data["status"] in ["SATISFIED", "PARTIAL", "GAP"]
    assert "confidence" in data
    assert "reasoning" in data
    assert data["model_name"] == "mock-deterministic-v1"
    assert data["citation_verified"] is False


@pytest.mark.asyncio
async def test_evaluate_evidence_satisfied_result(async_client_db):
    client, session = async_client_db
    _, requirement, evidence = _seed_framework_and_evidence(session)

    resp = await client.post(
        "/api/v1/compliance/evaluate",
        json={
            "evidence_id": str(evidence.id),
            "requirement_id": str(requirement.id),
        },
        headers=OFFICER_HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "SATISFIED"
    assert len(data["supporting_evidence"]) > 0


@pytest.mark.asyncio
async def test_evaluate_requires_auth(async_client_db):
    client, session = async_client_db
    _, requirement, evidence = _seed_framework_and_evidence(session)

    resp = await client.post(
        "/api/v1/compliance/evaluate",
        json={
            "evidence_id": str(evidence.id),
            "requirement_id": str(requirement.id),
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_evaluate_requires_officer_role(async_client_db):
    client, session = async_client_db
    _, requirement, evidence = _seed_framework_and_evidence(session)

    resp = await client.post(
        "/api/v1/compliance/evaluate",
        json={
            "evidence_id": str(evidence.id),
            "requirement_id": str(requirement.id),
        },
        headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_evaluate_evidence_not_found(async_client_db):
    client, session = async_client_db
    _, requirement, _ = _seed_framework_and_evidence(session)

    resp = await client.post(
        "/api/v1/compliance/evaluate",
        json={
            "evidence_id": str(uuid.uuid4()),
            "requirement_id": str(requirement.id),
        },
        headers=OFFICER_HEADERS,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_evaluate_requirement_not_found(async_client_db):
    client, session = async_client_db
    _, _, evidence = _seed_framework_and_evidence(session)

    resp = await client.post(
        "/api/v1/compliance/evaluate",
        json={
            "evidence_id": str(evidence.id),
            "requirement_id": str(uuid.uuid4()),
        },
        headers=OFFICER_HEADERS,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_evaluate_no_content_text(async_client_db):
    client, session = async_client_db
    framework, requirement, _ = _seed_framework_and_evidence(session)

    no_text = EvidenceDocument(
        filename="empty.pdf",
        document_type=DocumentType.OTHER,
        storage_path="/tmp/test/empty.pdf",
        content_text=None,
        file_hash="notext000",
        file_size_bytes=100,
        uploaded_by=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        validity_status=EvidenceValidity.VALID,
        processing_status=ProcessingStatus.UPLOADED,
    )
    session.add(no_text)
    session.flush()

    resp = await client.post(
        "/api/v1/compliance/evaluate",
        json={
            "evidence_id": str(no_text.id),
            "requirement_id": str(requirement.id),
        },
        headers=OFFICER_HEADERS,
    )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_evaluate_invalid_uuid_format(async_client_db):
    client, _ = async_client_db
    resp = await client.post(
        "/api/v1/compliance/evaluate",
        json={
            "evidence_id": "not-a-uuid",
            "requirement_id": "also-not-a-uuid",
        },
        headers=OFFICER_HEADERS,
    )
    assert resp.status_code == 422


# ── GET /api/v1/compliance/matches/{match_id} ─────────────────────────


@pytest.mark.asyncio
async def test_get_match_success(async_client_db):
    client, session = async_client_db
    _, requirement, evidence = _seed_framework_and_evidence(session)

    create_resp = await client.post(
        "/api/v1/compliance/evaluate",
        json={
            "evidence_id": str(evidence.id),
            "requirement_id": str(requirement.id),
        },
        headers=OFFICER_HEADERS,
    )
    match_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/v1/compliance/matches/{match_id}",
        headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == match_id
    assert data["status"] in ["SATISFIED", "PARTIAL", "GAP"]


@pytest.mark.asyncio
async def test_get_match_not_found(async_client_db):
    client, _ = async_client_db
    resp = await client.get(
        f"/api/v1/compliance/matches/{uuid.uuid4()}",
        headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_match_requires_auth(async_client_db):
    client, _ = async_client_db
    resp = await client.get(f"/api/v1/compliance/matches/{uuid.uuid4()}")
    assert resp.status_code == 401


# ── GET /api/v1/compliance/requirements/{id}/matches ───────────────────


@pytest.mark.asyncio
async def test_list_requirement_matches(async_client_db):
    client, session = async_client_db
    _, requirement, evidence = _seed_framework_and_evidence(session)

    await client.post(
        "/api/v1/compliance/evaluate",
        json={
            "evidence_id": str(evidence.id),
            "requirement_id": str(requirement.id),
        },
        headers=OFFICER_HEADERS,
    )

    resp = await client.get(
        f"/api/v1/compliance/requirements/{requirement.id}/matches",
        headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["requirement_id"] == str(requirement.id)


@pytest.mark.asyncio
async def test_list_requirement_matches_empty(async_client_db):
    client, session = async_client_db
    _, requirement, _ = _seed_framework_and_evidence(session)

    resp = await client.get(
        f"/api/v1/compliance/requirements/{requirement.id}/matches",
        headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_matches_pagination(async_client_db):
    client, session = async_client_db
    _, requirement, evidence = _seed_framework_and_evidence(session)

    for _ in range(3):
        await client.post(
            "/api/v1/compliance/evaluate",
            json={
                "evidence_id": str(evidence.id),
                "requirement_id": str(requirement.id),
            },
            headers=OFFICER_HEADERS,
        )

    resp = await client.get(
        f"/api/v1/compliance/requirements/{requirement.id}/matches?page=1&page_size=2",
        headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["pages"] == 2


@pytest.mark.asyncio
async def test_list_matches_requires_auth(async_client_db):
    client, _ = async_client_db
    resp = await client.get(
        f"/api/v1/compliance/requirements/{uuid.uuid4()}/matches",
    )
    assert resp.status_code == 401
