"""Security and authorization boundaries: RBAC, password hashing, and token validation."""

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable, Optional
from uuid import UUID, uuid4

import bcrypt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field

from src.config import get_settings
from src.core.exceptions import AuthenticationException, AuthorizationException

# HTTP Bearer scheme
security_bearer = HTTPBearer(auto_error=False)


class Role(str, Enum):
    """System authorization roles."""

    COMPLIANCE_OFFICER = "compliance-officer"
    ADMIN = "admin"
    AUDITOR = "auditor"


class CurrentUser(BaseModel):
    """Authenticated user context passed across API and service boundaries."""

    user_id: UUID = Field(default_factory=uuid4)
    username: str
    role: Role
    is_active: bool = True


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify raw password against bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8")[:72],
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Generate bcrypt hash for password."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8")[:72], salt).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generate a signed JWT token."""
    settings = get_settings()
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError as e:
        raise AuthenticationException(f"Invalid or expired authentication token: {str(e)}")


async def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    x_dev_role: Optional[str] = Header(None, alias="X-Dev-Role"),
    x_dev_username: Optional[str] = Header(None, alias="X-Dev-User"),
) -> CurrentUser:
    """
    Extract and validate authenticated user from JWT Bearer token or development headers.
    Ensures early security boundaries without requiring manual token issuance in local tests.
    """
    settings = get_settings()

    # In test/dev mode, allow X-Dev-Role / X-Dev-User headers for fast integration testing
    if settings.app_env in ("development", "test") and x_dev_role:
        try:
            role_enum = Role(x_dev_role)
            return CurrentUser(
                user_id=UUID("00000000-0000-0000-0000-000000000001"),
                username=x_dev_username or "dev-officer",
                role=role_enum,
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid development role: {x_dev_role}",
            )

    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(auth.credentials)
        username: str = payload.get("sub", "")
        role_str: str = payload.get("role", "")
        user_id_str: str = payload.get("user_id", "")

        if not username or not role_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed token payload.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        role = Role(role_str)
        user_id = UUID(user_id_str) if user_id_str else uuid4()

        return CurrentUser(user_id=user_id, username=username, role=role)

    except (AuthenticationException, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )


def _to_role_value(role: str | Role) -> str:
    """Normalize role to string value."""
    return role.value if isinstance(role, Role) else str(role)


def require_role(allowed_roles: str | list[str] | Role | list[Role]) -> Callable:
    """Dependency factory enforcing role-based access control (RBAC)."""
    if isinstance(allowed_roles, (str, Role)):
        roles_set = {_to_role_value(allowed_roles)}
    else:
        roles_set = {_to_role_value(r) for r in allowed_roles}

    async def role_checker(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        user_role_str = _to_role_value(current_user.role)
        if user_role_str not in roles_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: User role '{user_role_str}' lacks required permissions.",
            )
        return current_user

    return role_checker
