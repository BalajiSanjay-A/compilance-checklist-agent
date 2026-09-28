"""API integration tests for authentication and user management endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from src.core.security import Role, get_password_hash
from src.database.models import User

ADMIN_HEADERS = {"X-Dev-Role": "admin", "X-Dev-User": "dev-admin"}
OFFICER_HEADERS = {"X-Dev-Role": "compliance-officer", "X-Dev-User": "dev-officer"}
AUDITOR_HEADERS = {"X-Dev-Role": "auditor", "X-Dev-User": "dev-auditor"}


def _seed_login_user(session: Session, username="loginuser", password="TestPass123",
                     role=Role.COMPLIANCE_OFFICER, is_active=True):
    user = User(
        username=username,
        email=f"{username}@test.local",
        hashed_password=get_password_hash(password),
        role=role,
        is_active=is_active,
    )
    session.add(user)
    session.flush()
    return user


# ── POST /api/v1/auth/login ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_success(async_client_db):
    client, session = async_client_db
    _seed_login_user(session, username="myuser", password="MyPassword1")

    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "myuser", "password": "MyPassword1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["username"] == "myuser"
    assert data["role"] == "compliance-officer"
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_wrong_password(async_client_db):
    client, session = async_client_db
    _seed_login_user(session, username="user1", password="CorrectPass1")

    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "user1", "password": "WrongPassword"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(async_client_db):
    client, _ = async_client_db

    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "ghost", "password": "anything"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_deactivated_user(async_client_db):
    client, session = async_client_db
    _seed_login_user(session, username="inactive", password="ValidPass1", is_active=False)

    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "inactive", "password": "ValidPass1"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_then_access_protected_endpoint(async_client_db):
    client, session = async_client_db
    _seed_login_user(session, username="jwtuser", password="JwtPass123")

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "jwtuser", "password": "JwtPass123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    me_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "jwtuser"


# ── GET /api/v1/auth/me ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_me_with_dev_headers(async_client_db):
    client, _ = async_client_db

    resp = await client.get("/api/v1/auth/me", headers=OFFICER_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["role"] == "compliance-officer"


@pytest.mark.asyncio
async def test_me_requires_auth(async_client_db):
    client, _ = async_client_db

    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


# ── PATCH /api/v1/auth/me/password ───────────────────────────────────


@pytest.mark.asyncio
async def test_change_password(async_client_db):
    client, session = async_client_db
    user = _seed_login_user(session, username="changer", password="OldPass123")

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "changer", "password": "OldPass123"},
    )
    token = login_resp.json()["access_token"]

    resp = await client.patch(
        "/api/v1/auth/me/password",
        json={"current_password": "OldPass123", "new_password": "NewPass456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == "Password changed successfully."

    verify_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "changer", "password": "NewPass456"},
    )
    assert verify_resp.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current(async_client_db):
    client, session = async_client_db
    _seed_login_user(session, username="changer2", password="OldPass123")

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "changer2", "password": "OldPass123"},
    )
    token = login_resp.json()["access_token"]

    resp = await client.patch(
        "/api/v1/auth/me/password",
        json={"current_password": "WrongPass", "new_password": "NewPass456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_change_password_requires_auth(async_client_db):
    client, _ = async_client_db

    resp = await client.patch(
        "/api/v1/auth/me/password",
        json={"current_password": "any", "new_password": "NewPass456"},
    )
    assert resp.status_code == 401


# ── POST /api/v1/auth/users (admin) ─────────────────────────────────


@pytest.mark.asyncio
async def test_create_user(async_client_db):
    client, _ = async_client_db

    resp = await client.post(
        "/api/v1/auth/users",
        json={
            "username": "newauditor",
            "email": "auditor@test.local",
            "password": "AuditPass1",
            "role": "auditor",
        },
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "newauditor"
    assert data["role"] == "auditor"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_user_duplicate_username(async_client_db):
    client, session = async_client_db
    _seed_login_user(session, username="existing")

    resp = await client.post(
        "/api/v1/auth/users",
        json={
            "username": "existing",
            "email": "other@test.local",
            "password": "ValidPass1",
            "role": "auditor",
        },
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_user_requires_admin(async_client_db):
    client, _ = async_client_db

    resp = await client.post(
        "/api/v1/auth/users",
        json={
            "username": "blocked",
            "email": "blocked@test.local",
            "password": "ValidPass1",
            "role": "auditor",
        },
        headers=OFFICER_HEADERS,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_user_requires_auth(async_client_db):
    client, _ = async_client_db

    resp = await client.post(
        "/api/v1/auth/users",
        json={
            "username": "noauth",
            "email": "noauth@test.local",
            "password": "ValidPass1",
            "role": "auditor",
        },
    )
    assert resp.status_code == 401


# ── GET /api/v1/auth/users (admin) ──────────────────────────────────


@pytest.mark.asyncio
async def test_list_users(async_client_db):
    client, session = async_client_db
    _seed_login_user(session, username="u1", role=Role.AUDITOR)
    _seed_login_user(session, username="u2", role=Role.COMPLIANCE_OFFICER)

    resp = await client.get("/api/v1/auth/users", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2


@pytest.mark.asyncio
async def test_list_users_filter_active(async_client_db):
    client, session = async_client_db
    _seed_login_user(session, username="active1", is_active=True)
    _seed_login_user(session, username="inactive1", is_active=False)

    resp = await client.get(
        "/api/v1/auth/users?is_active=true", headers=ADMIN_HEADERS
    )
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["is_active"] is True


@pytest.mark.asyncio
async def test_list_users_requires_admin(async_client_db):
    client, _ = async_client_db

    resp = await client.get("/api/v1/auth/users", headers=AUDITOR_HEADERS)
    assert resp.status_code == 403


# ── GET /api/v1/auth/users/{id} (admin) ─────────────────────────────


@pytest.mark.asyncio
async def test_get_user(async_client_db):
    client, session = async_client_db
    user = _seed_login_user(session, username="findme")

    resp = await client.get(
        f"/api/v1/auth/users/{user.id}", headers=ADMIN_HEADERS
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == "findme"


@pytest.mark.asyncio
async def test_get_user_not_found(async_client_db):
    client, _ = async_client_db

    resp = await client.get(
        f"/api/v1/auth/users/{uuid.uuid4()}", headers=ADMIN_HEADERS
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_user_requires_admin(async_client_db):
    client, session = async_client_db
    user = _seed_login_user(session, username="hidden")

    resp = await client.get(
        f"/api/v1/auth/users/{user.id}", headers=OFFICER_HEADERS
    )
    assert resp.status_code == 403


# ── PATCH /api/v1/auth/users/{id} (admin) ───────────────────────────


@pytest.mark.asyncio
async def test_update_user_role(async_client_db):
    client, session = async_client_db
    user = _seed_login_user(session, username="promote")

    resp = await client.patch(
        f"/api/v1/auth/users/{user.id}",
        json={"role": "admin"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_deactivate_user(async_client_db):
    client, session = async_client_db
    user = _seed_login_user(session, username="deactivate")

    resp = await client.patch(
        f"/api/v1/auth/users/{user.id}",
        json={"is_active": False},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_update_user_not_found(async_client_db):
    client, _ = async_client_db

    resp = await client.patch(
        f"/api/v1/auth/users/{uuid.uuid4()}",
        json={"role": "admin"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_user_requires_admin(async_client_db):
    client, session = async_client_db
    user = _seed_login_user(session, username="notadmin")

    resp = await client.patch(
        f"/api/v1/auth/users/{user.id}",
        json={"role": "admin"},
        headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_user_requires_auth(async_client_db):
    client, session = async_client_db
    user = _seed_login_user(session, username="noauth2")

    resp = await client.patch(
        f"/api/v1/auth/users/{user.id}",
        json={"role": "admin"},
    )
    assert resp.status_code == 401
