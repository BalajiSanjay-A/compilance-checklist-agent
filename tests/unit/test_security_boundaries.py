"""Unit tests for early security and authorization boundaries."""

import pytest
from fastapi import HTTPException

from src.core.exceptions import AuthenticationException
from src.core.security import (
    CurrentUser,
    Role,
    create_access_token,
    decode_access_token,
    get_password_hash,
    require_role,
    verify_password,
)


def test_password_hashing():
    """Verify bcrypt password hashing and verification."""
    password = "SuperSecretPassword123!"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False
    assert verify_password(password, "invalid_hash_string") is False


def test_jwt_token_encode_decode():
    """Verify JWT token encoding and decoding."""
    payload = {"sub": "auditor_user", "role": "auditor"}
    token = create_access_token(payload)
    decoded = decode_access_token(token)
    assert decoded["sub"] == "auditor_user"
    assert decoded["role"] == "auditor"


def test_jwt_invalid_token():
    """Verify invalid token raises AuthenticationException."""
    with pytest.raises(AuthenticationException):
        decode_access_token("completely-invalid-garbage-token")


@pytest.mark.asyncio
async def test_require_role_enforcement_pass():
    """Verify require_role passes when role matches."""
    officer_user = CurrentUser(username="test_officer", role=Role.COMPLIANCE_OFFICER)
    checker = require_role(Role.COMPLIANCE_OFFICER)
    result = await checker(current_user=officer_user)
    assert result == officer_user


@pytest.mark.asyncio
async def test_require_role_enforcement_forbidden():
    """Verify require_role raises 403 Forbidden when role does not match."""
    auditor_user = CurrentUser(username="test_auditor", role=Role.AUDITOR)
    checker = require_role(Role.COMPLIANCE_OFFICER)
    with pytest.raises(HTTPException) as exc_info:
        await checker(current_user=auditor_user)
    assert exc_info.value.status_code == 403
    assert "lacks required permissions" in exc_info.value.detail


@pytest.mark.asyncio
async def test_require_role_with_list_of_roles():
    """Verify require_role accepts list of permitted roles."""
    auditor_user = CurrentUser(username="test_auditor", role=Role.AUDITOR)
    checker = require_role([Role.COMPLIANCE_OFFICER, Role.AUDITOR])
    result = await checker(current_user=auditor_user)
    assert result == auditor_user
