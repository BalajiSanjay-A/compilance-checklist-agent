"""API integration tests for evidence upload and retrieval endpoints."""

import io
import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

OFFICER_HEADERS = {"X-Dev-Role": "compliance-officer", "X-Dev-User": "test-officer"}
AUDITOR_HEADERS = {"X-Dev-Role": "auditor", "X-Dev-User": "test-auditor"}


def _txt_file(content: str = "Access control policy: all users must use MFA."):
    return {"file": ("policy.txt", io.BytesIO(content.encode()), "text/plain")}


def _csv_file():
    return {"file": ("audit.csv", io.BytesIO(b"date,event\n2026-01-01,login\n"), "text/csv")}


# ── Upload ──────────────────────────────────────────────────────────────


class TestUploadEvidence:
    async def test_upload_txt_success(self, async_client_db: tuple[AsyncClient, Session]):
        client, _ = async_client_db
        resp = await client.post(
            "/api/v1/evidence/upload",
            files=_txt_file(),
            data={"document_type": "POLICY"},
            headers=OFFICER_HEADERS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["filename"] == "policy.txt"
        assert data["processing_status"] == "PROCESSED"
        assert len(data["file_hash"]) == 64
        assert data["file_size_bytes"] > 0

    async def test_upload_csv_success(self, async_client_db: tuple[AsyncClient, Session]):
        client, _ = async_client_db
        resp = await client.post(
            "/api/v1/evidence/upload",
            files=_csv_file(),
            data={"document_type": "AUDIT_LOG"},
            headers=OFFICER_HEADERS,
        )
        assert resp.status_code == 201
        assert resp.json()["processing_status"] == "PROCESSED"

    async def test_upload_with_validity_dates(self, async_client_db: tuple[AsyncClient, Session]):
        client, _ = async_client_db
        expires = (date.today() + timedelta(days=10)).isoformat()
        resp = await client.post(
            "/api/v1/evidence/upload",
            files=_txt_file(),
            data={
                "document_type": "CERTIFICATE",
                "valid_from": (date.today() - timedelta(days=30)).isoformat(),
                "expires_at": expires,
            },
            headers=OFFICER_HEADERS,
        )
        assert resp.status_code == 201
        assert resp.json()["validity_status"] == "EXPIRING_SOON"

    async def test_upload_expired_evidence(self, async_client_db: tuple[AsyncClient, Session]):
        client, _ = async_client_db
        resp = await client.post(
            "/api/v1/evidence/upload",
            files=_txt_file(),
            data={
                "document_type": "CERTIFICATE",
                "expires_at": (date.today() - timedelta(days=5)).isoformat(),
            },
            headers=OFFICER_HEADERS,
        )
        assert resp.status_code == 201
        assert resp.json()["validity_status"] == "EXPIRED"

    async def test_upload_invalid_mime_type(self, async_client_db: tuple[AsyncClient, Session]):
        client, _ = async_client_db
        resp = await client.post(
            "/api/v1/evidence/upload",
            files={"file": ("image.png", io.BytesIO(b"fake png"), "image/png")},
            headers=OFFICER_HEADERS,
        )
        assert resp.status_code == 422
        assert "not allowed" in resp.json()["message"]

    async def test_upload_forbidden_for_auditor(self, async_client_db: tuple[AsyncClient, Session]):
        client, _ = async_client_db
        resp = await client.post(
            "/api/v1/evidence/upload",
            files=_txt_file(),
            headers=AUDITOR_HEADERS,
        )
        assert resp.status_code == 403

    async def test_upload_unauthorized(self, async_client_db: tuple[AsyncClient, Session]):
        client, _ = async_client_db
        resp = await client.post(
            "/api/v1/evidence/upload",
            files=_txt_file(),
        )
        assert resp.status_code == 401


# ── Retrieval ───────────────────────────────────────────────────────────


class TestGetEvidence:
    async def test_get_by_id(self, async_client_db: tuple[AsyncClient, Session]):
        client, _ = async_client_db
        upload_resp = await client.post(
            "/api/v1/evidence/upload",
            files=_txt_file(),
            headers=OFFICER_HEADERS,
        )
        evidence_id = upload_resp.json()["id"]

        resp = await client.get(f"/api/v1/evidence/{evidence_id}", headers=AUDITOR_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == evidence_id
        assert data["has_content"] is True
        assert "MFA" in data["content_text"]

    async def test_get_not_found(self, async_client_db: tuple[AsyncClient, Session]):
        client, _ = async_client_db
        resp = await client.get(f"/api/v1/evidence/{uuid.uuid4()}", headers=AUDITOR_HEADERS)
        assert resp.status_code == 404


# ── List ────────────────────────────────────────────────────────────────


class TestListEvidence:
    async def test_empty_list(self, async_client_db: tuple[AsyncClient, Session]):
        client, _ = async_client_db
        resp = await client.get("/api/v1/evidence", headers=AUDITOR_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_with_uploads(self, async_client_db: tuple[AsyncClient, Session]):
        client, _ = async_client_db
        await client.post(
            "/api/v1/evidence/upload",
            files=_txt_file("Policy doc 1"),
            data={"document_type": "POLICY"},
            headers=OFFICER_HEADERS,
        )
        await client.post(
            "/api/v1/evidence/upload",
            files=_txt_file("Audit log entry"),
            data={"document_type": "AUDIT_LOG"},
            headers=OFFICER_HEADERS,
        )

        resp = await client.get("/api/v1/evidence", headers=AUDITOR_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    async def test_list_filter_by_document_type(self, async_client_db: tuple[AsyncClient, Session]):
        client, _ = async_client_db
        await client.post(
            "/api/v1/evidence/upload",
            files=_txt_file("Policy doc"),
            data={"document_type": "POLICY"},
            headers=OFFICER_HEADERS,
        )
        await client.post(
            "/api/v1/evidence/upload",
            files=_txt_file("Audit entry"),
            data={"document_type": "AUDIT_LOG"},
            headers=OFFICER_HEADERS,
        )

        resp = await client.get(
            "/api/v1/evidence?document_type=POLICY",
            headers=AUDITOR_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["document_type"] == "POLICY"

    async def test_list_pagination(self, async_client_db: tuple[AsyncClient, Session]):
        client, _ = async_client_db
        for i in range(5):
            await client.post(
                "/api/v1/evidence/upload",
                files=_txt_file(f"Document number {i}"),
                headers=OFFICER_HEADERS,
            )

        resp = await client.get(
            "/api/v1/evidence?page=1&page_size=2",
            headers=AUDITOR_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["pages"] == 3
