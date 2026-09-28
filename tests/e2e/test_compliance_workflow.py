"""End-to-end test covering the complete compliance workflow.

Exercises the full pipeline through the API layer:
  framework → requirements → evidence → AI matching →
  compliance evaluation → gap reporting → dashboard
with authentication and RBAC enforcement at every step.
"""

import pytest

ADMIN_HEADERS = {"X-Dev-Role": "admin", "X-Dev-User": "dev-admin"}
OFFICER_HEADERS = {"X-Dev-Role": "compliance-officer", "X-Dev-User": "dev-officer"}
AUDITOR_HEADERS = {"X-Dev-Role": "auditor", "X-Dev-User": "dev-auditor"}


@pytest.mark.asyncio
async def test_full_compliance_workflow(async_client_db):
    """E2E: framework → requirement → evidence → evaluation → gap → dashboard."""
    client, session = async_client_db

    # ── 1. Admin creates users ────────────────────────────────────────
    resp = await client.post(
        "/api/v1/auth/users",
        json={
            "username": "e2e_officer",
            "email": "officer@e2e.local",
            "password": "OfficerPass1",
            "role": "compliance-officer",
        },
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 201
    officer_id = resp.json()["id"]

    resp = await client.post(
        "/api/v1/auth/users",
        json={
            "username": "e2e_auditor",
            "email": "auditor@e2e.local",
            "password": "AuditorPass1",
            "role": "auditor",
        },
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 201

    # ── 2. Login as officer ───────────────────────────────────────────
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "e2e_officer", "password": "OfficerPass1"},
    )
    assert resp.status_code == 200
    officer_token = resp.json()["access_token"]
    officer_auth = {"Authorization": f"Bearer {officer_token}"}

    # ── 3. Login as auditor ───────────────────────────────────────────
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "e2e_auditor", "password": "AuditorPass1"},
    )
    assert resp.status_code == 200
    auditor_token = resp.json()["access_token"]
    auditor_auth = {"Authorization": f"Bearer {auditor_token}"}

    # ── 4. Officer creates framework ──────────────────────────────────
    resp = await client.post(
        "/api/v1/frameworks",
        json={
            "name": "E2E Test Framework",
            "version": "1.0",
            "description": "End-to-end test framework.",
        },
        headers=OFFICER_HEADERS,
    )
    assert resp.status_code == 201
    framework_id = resp.json()["id"]

    # ── 5. Officer adds requirements ──────────────────────────────────
    resp = await client.post(
        f"/api/v1/frameworks/{framework_id}/requirements",
        json={
            "requirement_code": "E2E.1",
            "title": "Access Control Policy",
            "description": "Organization must implement logical access controls.",
            "severity": "HIGH",
        },
        headers=OFFICER_HEADERS,
    )
    assert resp.status_code == 201
    req_id = resp.json()["id"]

    # Verify baseline GAP status was auto-created
    resp = await client.get(
        f"/api/v1/compliance/requirements/{req_id}/status",
        headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "GAP"

    # ── 6. Officer uploads evidence ───────────────────────────────────
    evidence_text = (
        "Our organization implements logical access controls including MFA, "
        "role-based access, and quarterly access reviews. All access is logged."
    )
    resp = await client.post(
        "/api/v1/evidence/upload",
        files={"file": ("access_policy.txt", evidence_text.encode(), "text/plain")},
        data={"document_type": "POLICY"},
        headers=OFFICER_HEADERS,
    )
    assert resp.status_code == 201
    evidence_id = resp.json()["id"]

    # Verify evidence is stored with extracted text
    resp = await client.get(
        f"/api/v1/evidence/{evidence_id}",
        headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["content_text"] is not None

    # ── 7. Auditor cannot write (RBAC enforcement) ────────────────────
    resp = await client.post(
        "/api/v1/compliance/evaluate-and-resolve",
        json={"evidence_id": evidence_id, "requirement_id": req_id},
        headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 403

    # ── 8. Officer runs full evaluation pipeline ──────────────────────
    resp = await client.post(
        "/api/v1/compliance/evaluate-and-resolve",
        json={"evidence_id": evidence_id, "requirement_id": req_id},
        headers=OFFICER_HEADERS,
    )
    assert resp.status_code == 201
    eval_result = resp.json()
    assert eval_result["status"] in ["SATISFIED", "PARTIAL", "GAP"]
    assert eval_result["current_match_id"] is not None

    # ── 9. Check compliance status updated ────────────────────────────
    resp = await client.get(
        f"/api/v1/compliance/requirements/{req_id}/status",
        headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 200
    status_data = resp.json()
    assert status_data["status"] == eval_result["status"]

    # ── 10. Check compliance history recorded ─────────────────────────
    resp = await client.get(
        f"/api/v1/compliance/requirements/{req_id}/history",
        headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 200
    history = resp.json()
    assert history["total"] >= 1
    assert history["items"][0]["previous_status"] == "GAP"

    # ── 11. Check evidence matches ────────────────────────────────────
    resp = await client.get(
        f"/api/v1/compliance/requirements/{req_id}/matches",
        headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 200
    matches_data = resp.json()
    assert matches_data["total"] >= 1

    # ── 12. Check gap reports (if evaluation produced gaps) ───────────
    resp = await client.get(
        "/api/v1/gap-reports", headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 200
    gaps = resp.json()

    if gaps["total"] > 0:
        gap_id = gaps["items"][0]["id"]

        # Auditor cannot update gap status
        resp = await client.patch(
            f"/api/v1/gap-reports/{gap_id}",
            json={"status": "IN_REVIEW"},
            headers=AUDITOR_HEADERS,
        )
        assert resp.status_code == 403

        # Officer can transition gap
        resp = await client.patch(
            f"/api/v1/gap-reports/{gap_id}",
            json={"status": "IN_REVIEW"},
            headers=OFFICER_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "IN_REVIEW"

    # ── 13. Check framework compliance scorecard ──────────────────────
    resp = await client.get(
        f"/api/v1/compliance/{framework_id}/status",
        headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 200
    scorecard = resp.json()
    assert scorecard["total_requirements"] == 1
    assert scorecard["framework_name"] == "E2E Test Framework"

    # ── 14. Dashboard: system overview ────────────────────────────────
    resp = await client.get(
        "/api/v1/dashboard/overview", headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 200
    overview = resp.json()
    assert overview["total_frameworks"] >= 1
    assert overview["total_requirements"] >= 1
    assert overview["total_evidence"] >= 1

    # ── 15. Dashboard: framework detail ───────────────────────────────
    resp = await client.get(
        f"/api/v1/dashboard/frameworks/{framework_id}",
        headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 200
    detail = resp.json()
    assert len(detail["requirements"]) == 1
    assert detail["requirements"][0]["requirement_code"] == "E2E.1"

    # ── 16. Dashboard: gap summary ────────────────────────────────────
    resp = await client.get(
        "/api/v1/dashboard/gaps", headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 200

    # ── 17. Dashboard: evidence summary ───────────────────────────────
    resp = await client.get(
        "/api/v1/dashboard/evidence", headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # ── 18. Verify no auth leaks ──────────────────────────────────────
    resp = await client.get("/api/v1/dashboard/overview")
    assert resp.status_code == 401

    resp = await client.get(f"/api/v1/compliance/{framework_id}/status")
    assert resp.status_code == 401

    resp = await client.post(
        "/api/v1/frameworks",
        json={"name": "Hack", "version": "1.0"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_expired_evidence_forces_gap(async_client_db):
    """E2E: expired evidence always resolves to GAP regardless of LLM result."""
    client, session = async_client_db

    # Create framework and requirement
    resp = await client.post(
        "/api/v1/frameworks",
        json={"name": "Expiry Test", "version": "1.0"},
        headers=OFFICER_HEADERS,
    )
    assert resp.status_code == 201
    fw_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/frameworks/{fw_id}/requirements",
        json={
            "requirement_code": "EXP.1",
            "title": "Expiry Control",
            "description": "Test expiration.",
            "severity": "HIGH",
        },
        headers=OFFICER_HEADERS,
    )
    assert resp.status_code == 201
    req_id = resp.json()["id"]

    # Upload evidence with past expiration
    resp = await client.post(
        "/api/v1/evidence/upload",
        files={"file": ("expired.txt", b"Access controls implemented.", "text/plain")},
        data={"document_type": "POLICY", "expires_at": "2020-01-01"},
        headers=OFFICER_HEADERS,
    )
    assert resp.status_code == 201
    ev_id = resp.json()["id"]

    # Evaluate — must resolve to GAP due to expiration
    resp = await client.post(
        "/api/v1/compliance/evaluate-and-resolve",
        json={"evidence_id": ev_id, "requirement_id": req_id},
        headers=OFFICER_HEADERS,
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "GAP"


@pytest.mark.asyncio
async def test_admin_user_management_lifecycle(async_client_db):
    """E2E: admin creates, lists, updates, and deactivates users."""
    client, _ = async_client_db

    # Create user
    resp = await client.post(
        "/api/v1/auth/users",
        json={
            "username": "lifecycle_user",
            "email": "lifecycle@e2e.local",
            "password": "LifePass1",
            "role": "auditor",
        },
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 201
    user_id = resp.json()["id"]

    # List users
    resp = await client.get("/api/v1/auth/users", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # Update role
    resp = await client.patch(
        f"/api/v1/auth/users/{user_id}",
        json={"role": "compliance-officer"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "compliance-officer"

    # Deactivate
    resp = await client.patch(
        f"/api/v1/auth/users/{user_id}",
        json={"is_active": False},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    # Deactivated user cannot login
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "lifecycle_user", "password": "LifePass1"},
    )
    assert resp.status_code == 401
