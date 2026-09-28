"""Pydantic schemas for authentication and user management."""

import math
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.core.security import Role


class LoginRequest(BaseModel):
    """Login credentials."""

    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    """JWT token response after successful authentication."""

    access_token: str
    token_type: str = "bearer"
    user_id: UUID
    username: str
    role: str
    expires_in: int = Field(description="Token lifetime in seconds")


class UserCreateRequest(BaseModel):
    """Request to create a new user (admin operation)."""

    username: str = Field(..., min_length=3, max_length=100)
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    role: Role

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email address")
        return v.lower().strip()


class UserResponse(BaseModel):
    """User profile response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: str
    role: Role
    is_active: bool
    created_at: Optional[datetime] = None


class UserUpdateRequest(BaseModel):
    """Partial update request for user management (admin operation)."""

    email: Optional[str] = Field(None, min_length=5, max_length=255)
    role: Optional[Role] = None
    is_active: Optional[bool] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email address")
        return v.lower().strip()


class ChangePasswordRequest(BaseModel):
    """Request to change own password."""

    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


class PaginatedUsersResponse(BaseModel):
    """Paginated list of users."""

    items: List[UserResponse]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def build(cls, items: list, total: int, page: int, page_size: int) -> "PaginatedUsersResponse":
        return cls(
            items=[UserResponse.model_validate(u) for u in items],
            total=total,
            page=page,
            page_size=page_size,
            pages=max(1, math.ceil(total / page_size)),
        )
