"""Unit tests for authentication and user management service."""

import uuid

import pytest

from src.core.exceptions import (
    AuthenticationException,
    DuplicateEntityException,
    EntityNotFoundException,
    ValidationException,
)
from src.core.security import Role, get_password_hash
from src.database.models import User
from src.services.auth_service import AuthService

DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _seed_user(session, username="officer", email="officer@test.local",
               password="SecurePass123", role=Role.COMPLIANCE_OFFICER, is_active=True):
    user = User(
        username=username,
        email=email,
        hashed_password=get_password_hash(password),
        role=role,
        is_active=is_active,
    )
    session.add(user)
    session.flush()
    return user


# ── authenticate_user ─────────────────────────────────────────────────


class TestAuthenticateUser:
    def test_valid_credentials(self, db_session):
        user = _seed_user(db_session)

        result = AuthService.authenticate_user(db_session, "officer", "SecurePass123")
        assert result.id == user.id
        assert result.username == "officer"

    def test_wrong_password(self, db_session):
        _seed_user(db_session)

        with pytest.raises(AuthenticationException, match="Invalid username or password"):
            AuthService.authenticate_user(db_session, "officer", "WrongPassword")

    def test_nonexistent_user(self, db_session):
        with pytest.raises(AuthenticationException, match="Invalid username or password"):
            AuthService.authenticate_user(db_session, "ghost", "any_password")

    def test_deactivated_user(self, db_session):
        _seed_user(db_session, is_active=False)

        with pytest.raises(AuthenticationException, match="deactivated"):
            AuthService.authenticate_user(db_session, "officer", "SecurePass123")


# ── create_user ───────────────────────────────────────────────────────


class TestCreateUser:
    def test_success(self, db_session):
        user = AuthService.create_user(
            db_session, "newuser", "new@test.local", "StrongPass1", Role.AUDITOR,
        )
        assert user.username == "newuser"
        assert user.email == "new@test.local"
        assert user.role == Role.AUDITOR
        assert user.is_active is True

    def test_duplicate_username(self, db_session):
        _seed_user(db_session, username="taken", email="a@test.local")

        with pytest.raises(DuplicateEntityException, match="username"):
            AuthService.create_user(
                db_session, "taken", "b@test.local", "StrongPass1", Role.AUDITOR,
            )

    def test_duplicate_email(self, db_session):
        _seed_user(db_session, username="user1", email="dup@test.local")

        with pytest.raises(DuplicateEntityException, match="email"):
            AuthService.create_user(
                db_session, "user2", "dup@test.local", "StrongPass1", Role.AUDITOR,
            )

    def test_short_password_rejected(self, db_session):
        with pytest.raises(ValidationException, match="at least 8"):
            AuthService.create_user(
                db_session, "user", "u@test.local", "short", Role.AUDITOR,
            )


# ── get_user ──────────────────────────────────────────────────────────


class TestGetUser:
    def test_found(self, db_session):
        user = _seed_user(db_session)

        result = AuthService.get_user(db_session, user.id)
        assert result.username == "officer"

    def test_not_found(self, db_session):
        with pytest.raises(EntityNotFoundException, match="User"):
            AuthService.get_user(db_session, uuid.uuid4())


# ── list_users ────────────────────────────────────────────────────────


class TestListUsers:
    def test_list_all(self, db_session):
        _seed_user(db_session, username="a", email="a@t.local")
        _seed_user(db_session, username="b", email="b@t.local")

        users, total = AuthService.list_users(db_session)
        assert total == 2
        assert len(users) == 2

    def test_filter_active(self, db_session):
        _seed_user(db_session, username="active", email="active@t.local", is_active=True)
        _seed_user(db_session, username="inactive", email="inactive@t.local", is_active=False)

        users, total = AuthService.list_users(db_session, is_active=True)
        assert total == 1
        assert users[0].username == "active"

    def test_pagination(self, db_session):
        for i in range(5):
            _seed_user(db_session, username=f"u{i}", email=f"u{i}@t.local")

        users, total = AuthService.list_users(db_session, page=2, page_size=2)
        assert total == 5
        assert len(users) == 2

    def test_empty(self, db_session):
        users, total = AuthService.list_users(db_session)
        assert total == 0
        assert users == []


# ── update_user ───────────────────────────────────────────────────────


class TestUpdateUser:
    def test_update_role(self, db_session):
        user = _seed_user(db_session)

        result = AuthService.update_user(db_session, user.id, role=Role.ADMIN)
        assert result.role == Role.ADMIN

    def test_update_email(self, db_session):
        user = _seed_user(db_session)

        result = AuthService.update_user(db_session, user.id, email="new@test.local")
        assert result.email == "new@test.local"

    def test_deactivate_user(self, db_session):
        user = _seed_user(db_session)

        result = AuthService.update_user(db_session, user.id, is_active=False)
        assert result.is_active is False

    def test_duplicate_email_rejected(self, db_session):
        user1 = _seed_user(db_session, username="u1", email="taken@test.local")
        user2 = _seed_user(db_session, username="u2", email="other@test.local")

        with pytest.raises(DuplicateEntityException, match="email"):
            AuthService.update_user(db_session, user2.id, email="taken@test.local")

    def test_not_found(self, db_session):
        with pytest.raises(EntityNotFoundException):
            AuthService.update_user(db_session, uuid.uuid4(), role=Role.ADMIN)

    def test_no_change_noop(self, db_session):
        user = _seed_user(db_session)

        result = AuthService.update_user(db_session, user.id)
        assert result.id == user.id


# ── change_password ───────────────────────────────────────────────────


class TestChangePassword:
    def test_success(self, db_session):
        user = _seed_user(db_session, password="OldPassword1")

        AuthService.change_password(
            db_session, user.id, "OldPassword1", "NewPassword2",
        )

        result = AuthService.authenticate_user(db_session, "officer", "NewPassword2")
        assert result.id == user.id

    def test_wrong_current_password(self, db_session):
        user = _seed_user(db_session, password="OldPassword1")

        with pytest.raises(AuthenticationException, match="incorrect"):
            AuthService.change_password(
                db_session, user.id, "WrongCurrent", "NewPassword2",
            )

    def test_short_new_password(self, db_session):
        user = _seed_user(db_session, password="OldPassword1")

        with pytest.raises(ValidationException, match="at least 8"):
            AuthService.change_password(
                db_session, user.id, "OldPassword1", "short",
            )

    def test_not_found(self, db_session):
        with pytest.raises(EntityNotFoundException):
            AuthService.change_password(
                db_session, uuid.uuid4(), "any", "NewPassword2",
            )
