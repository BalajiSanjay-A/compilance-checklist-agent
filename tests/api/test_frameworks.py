"""API integration tests for framework and requirement management endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from src.database.models import ComplianceFramework, ComplianceStatusRecord, Requirement

OFFICER_HEADERS = {"X-Dev-Role": "compliance-officer", "X-Dev-User": "test-officer"}
AUDITOR_HEADERS = {"X-Dev-Role": "auditor", "X-Dev-User": "test-auditor"}


def _seed_framework(session: Session, name: str = "Test Framework", version: str = "1.0") -> ComplianceFramework:
    fw = ComplianceFramework(name=name, version=version, description="Test description")
    session.add(fw)
    session.flush()
    return fw


def _seed_requirement(session: Session, framework_id: uuid.UUID, code: str = "REQ-1") -> Requirement:
    req = Requirement(
        framework_id=framework_id,
        requirement_code=code,
        title=f"Requirement {code}",
        description=f"Description for {code}",
    )
    session.add(req)
    session.flush()
    return req


# ── Framework CRUD ──────────────────────────────────────────────────────


class TestCreateFramework:
    async def test_success(self, async_client_db: tuple[AsyncClient, Session]):
        client, _ = async_client_db
        resp = await client.post(
            "/api/v1/frameworks",
            json={"name": "SOC 2", "version": "2023", "description": "Security framework"},
            headers=OFFICER_HEADERS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "SOC 2"
        assert data["version"] == "2023"
        assert data["requirement_count"] == 0
        assert "id" in data
        assert "created_at" in data

    async def test_duplicate_returns_409(self, async_client_db: tuple[AsyncClient, Session]):
        client, _ = async_client_db
        payload = {"name": "DupFW", "version": "1.0"}
        resp1 = await client.post("/api/v1/frameworks", json=payload, headers=OFFICER_HEADERS)
        assert resp1.status_code == 201
        resp2 = await client.post("/api/v1/frameworks", json=payload, headers=OFFICER_HEADERS)
        assert resp2.status_code == 409
        assert resp2.json()["error"] == "DuplicateEntityException"

    async def test_forbidden_for_auditor(self, async_client_db: tuple[AsyncClient, Session]):
        client, _ = async_client_db
        resp = await client.post(
            "/api/v1/frameworks",
            json={"name": "X", "version": "1"},
            headers=AUDITOR_HEADERS,
        )
        assert resp.status_code == 403

    async def test_unauthorized_no_auth(self, async_client_db: tuple[AsyncClient, Session]):
        client, _ = async_client_db
        resp = await client.post("/api/v1/frameworks", json={"name": "X", "version": "1"})
        assert resp.status_code == 401

    async def test_validation_error_missing_fields(self, async_client_db: tuple[AsyncClient, Session]):
        client, _ = async_client_db
        resp = await client.post("/api/v1/frameworks", json={}, headers=OFFICER_HEADERS)
        assert resp.status_code == 422


class TestListFrameworks:
    async def test_empty_list(self, async_client_db: tuple[AsyncClient, Session]):
        client, _ = async_client_db
        resp = await client.get("/api/v1/frameworks", headers=AUDITOR_HEADERS)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_seeded_frameworks(self, async_client_db: tuple[AsyncClient, Session]):
        client, session = async_client_db
        _seed_framework(session, "FW-A", "1.0")
        _seed_framework(session, "FW-B", "2.0")
        resp = await client.get("/api/v1/frameworks", headers=AUDITOR_HEADERS)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_filter_by_active(self, async_client_db: tuple[AsyncClient, Session]):
        client, session = async_client_db
        fw_active = _seed_framework(session, "Active", "1")
        fw_inactive = ComplianceFramework(name="Inactive", version="1", is_active=False)
        session.add(fw_inactive)
        session.flush()

        resp = await client.get("/api/v1/frameworks?is_active=true", headers=AUDITOR_HEADERS)
        assert resp.status_code == 200
        names = [fw["name"] for fw in resp.json()]
        assert "Active" in names
        assert "Inactive" not in names

    async def test_includes_requirement_counts(self, async_client_db: tuple[AsyncClient, Session]):
        client, session = async_client_db
        fw = _seed_framework(session, "Counted", "1")
        _seed_requirement(session, fw.id, "R-1")
        _seed_requirement(session, fw.id, "R-2")

        resp = await client.get("/api/v1/frameworks", headers=AUDITOR_HEADERS)
        assert resp.status_code == 200
        fw_data = resp.json()[0]
        assert fw_data["requirement_count"] == 2


class TestGetFramework:
    async def test_success(self, async_client_db: tuple[AsyncClient, Session]):
        client, session = async_client_db
        fw = _seed_framework(session)
        resp = await client.get(f"/api/v1/frameworks/{fw.id}", headers=AUDITOR_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["name"] == fw.name

    async def test_not_found(self, async_client_db: tuple[AsyncClient, Session]):
        client, _ = async_client_db
        resp = await client.get(f"/api/v1/frameworks/{uuid.uuid4()}", headers=AUDITOR_HEADERS)
        assert resp.status_code == 404


class TestUpdateFramework:
    async def test_success(self, async_client_db: tuple[AsyncClient, Session]):
        client, session = async_client_db
        fw = _seed_framework(session, "Original", "1")
        resp = await client.patch(
            f"/api/v1/frameworks/{fw.id}",
            json={"name": "Updated"},
            headers=OFFICER_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"
        assert resp.json()["version"] == "1"

    async def test_not_found(self, async_client_db: tuple[AsyncClient, Session]):
        client, _ = async_client_db
        resp = await client.patch(
            f"/api/v1/frameworks/{uuid.uuid4()}",
            json={"name": "X"},
            headers=OFFICER_HEADERS,
        )
        assert resp.status_code == 404

    async def test_forbidden_for_auditor(self, async_client_db: tuple[AsyncClient, Session]):
        client, session = async_client_db
        fw = _seed_framework(session)
        resp = await client.patch(
            f"/api/v1/frameworks/{fw.id}",
            json={"name": "X"},
            headers=AUDITOR_HEADERS,
        )
        assert resp.status_code == 403


# ── Requirement CRUD ────────────────────────────────────────────────────


class TestCreateRequirement:
    async def test_success(self, async_client_db: tuple[AsyncClient, Session]):
        client, session = async_client_db
        fw = _seed_framework(session)
        resp = await client.post(
            f"/api/v1/frameworks/{fw.id}/requirements",
            json={
                "requirement_code": "CC6.1",
                "title": "Logical Access",
                "description": "Control access to information assets.",
                "severity": "HIGH",
            },
            headers=OFFICER_HEADERS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["requirement_code"] == "CC6.1"
        assert data["framework_id"] == str(fw.id)

    async def test_auto_creates_gap_status(self, async_client_db: tuple[AsyncClient, Session]):
        client, session = async_client_db
        fw = _seed_framework(session)
        resp = await client.post(
            f"/api/v1/frameworks/{fw.id}/requirements",
            json={
                "requirement_code": "CC6.2",
                "title": "Test Req",
                "description": "Test description",
            },
            headers=OFFICER_HEADERS,
        )
        assert resp.status_code == 201
        req_id = uuid.UUID(resp.json()["id"])
        status_record = session.query(ComplianceStatusRecord).filter_by(requirement_id=req_id).first()
        assert status_record is not None
        assert status_record.status.value == "GAP"

    async def test_duplicate_code_returns_409(self, async_client_db: tuple[AsyncClient, Session]):
        client, session = async_client_db
        fw = _seed_framework(session)
        payload = {
            "requirement_code": "DUP-1",
            "title": "Dup",
            "description": "Duplicate test",
        }
        resp1 = await client.post(f"/api/v1/frameworks/{fw.id}/requirements", json=payload, headers=OFFICER_HEADERS)
        assert resp1.status_code == 201
        resp2 = await client.post(f"/api/v1/frameworks/{fw.id}/requirements", json=payload, headers=OFFICER_HEADERS)
        assert resp2.status_code == 409

    async def test_framework_not_found(self, async_client_db: tuple[AsyncClient, Session]):
        client, _ = async_client_db
        resp = await client.post(
            f"/api/v1/frameworks/{uuid.uuid4()}/requirements",
            json={"requirement_code": "X", "title": "X", "description": "X"},
            headers=OFFICER_HEADERS,
        )
        assert resp.status_code == 404

    async def test_forbidden_for_auditor(self, async_client_db: tuple[AsyncClient, Session]):
        client, session = async_client_db
        fw = _seed_framework(session)
        resp = await client.post(
            f"/api/v1/frameworks/{fw.id}/requirements",
            json={"requirement_code": "X", "title": "X", "description": "X"},
            headers=AUDITOR_HEADERS,
        )
        assert resp.status_code == 403


class TestListRequirements:
    async def test_empty_list(self, async_client_db: tuple[AsyncClient, Session]):
        client, session = async_client_db
        fw = _seed_framework(session)
        resp = await client.get(f"/api/v1/frameworks/{fw.id}/requirements", headers=AUDITOR_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_pagination(self, async_client_db: tuple[AsyncClient, Session]):
        client, session = async_client_db
        fw = _seed_framework(session)
        for i in range(5):
            _seed_requirement(session, fw.id, f"REQ-{i:02d}")

        resp = await client.get(
            f"/api/v1/frameworks/{fw.id}/requirements?page=1&page_size=2",
            headers=AUDITOR_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["pages"] == 3

    async def test_filter_by_severity(self, async_client_db: tuple[AsyncClient, Session]):
        client, session = async_client_db
        fw = _seed_framework(session)
        req_high = Requirement(
            framework_id=fw.id, requirement_code="H-1", title="High", description="High sev", severity="HIGH"
        )
        req_low = Requirement(
            framework_id=fw.id, requirement_code="L-1", title="Low", description="Low sev", severity="LOW"
        )
        session.add_all([req_high, req_low])
        session.flush()

        resp = await client.get(
            f"/api/v1/frameworks/{fw.id}/requirements?severity=HIGH",
            headers=AUDITOR_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["requirement_code"] == "H-1"

    async def test_framework_not_found(self, async_client_db: tuple[AsyncClient, Session]):
        client, _ = async_client_db
        resp = await client.get(
            f"/api/v1/frameworks/{uuid.uuid4()}/requirements",
            headers=AUDITOR_HEADERS,
        )
        assert resp.status_code == 404


class TestGetRequirement:
    async def test_success(self, async_client_db: tuple[AsyncClient, Session]):
        client, session = async_client_db
        fw = _seed_framework(session)
        req = _seed_requirement(session, fw.id)
        resp = await client.get(f"/api/v1/requirements/{req.id}", headers=AUDITOR_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["requirement_code"] == req.requirement_code

    async def test_not_found(self, async_client_db: tuple[AsyncClient, Session]):
        client, _ = async_client_db
        resp = await client.get(f"/api/v1/requirements/{uuid.uuid4()}", headers=AUDITOR_HEADERS)
        assert resp.status_code == 404


class TestUpdateRequirement:
    async def test_success(self, async_client_db: tuple[AsyncClient, Session]):
        client, session = async_client_db
        fw = _seed_framework(session)
        req = _seed_requirement(session, fw.id)
        resp = await client.patch(
            f"/api/v1/requirements/{req.id}",
            json={"title": "Updated Title"},
            headers=OFFICER_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"
        assert resp.json()["requirement_code"] == req.requirement_code

    async def test_not_found(self, async_client_db: tuple[AsyncClient, Session]):
        client, _ = async_client_db
        resp = await client.patch(
            f"/api/v1/requirements/{uuid.uuid4()}",
            json={"title": "X"},
            headers=OFFICER_HEADERS,
        )
        assert resp.status_code == 404

    async def test_forbidden_for_auditor(self, async_client_db: tuple[AsyncClient, Session]):
        client, session = async_client_db
        fw = _seed_framework(session)
        req = _seed_requirement(session, fw.id)
        resp = await client.patch(
            f"/api/v1/requirements/{req.id}",
            json={"title": "X"},
            headers=AUDITOR_HEADERS,
        )
        assert resp.status_code == 403
