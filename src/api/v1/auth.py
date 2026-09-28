"""Authentication and user management API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from src.api.dependencies import AdminDep, CurrentUserDep, SettingsDep
from src.core.security import create_access_token
from src.database.session import get_db, transactional_session
from src.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    PaginatedUsersResponse,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
from src.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    db: Session = Depends(get_db),
    settings: SettingsDep = None,
):
    """Authenticate with username and password, receive a JWT access token."""
    user = AuthService.authenticate_user(db, body.username, body.password)

    token = create_access_token({
        "sub": user.username,
        "role": user.role.value,
        "user_id": str(user.id),
    })

    return LoginResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        role=user.role.value,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get("/me")
def get_me(current_user: CurrentUserDep):
    """Return the authenticated user's identity from their token or dev headers."""
    return {
        "user_id": str(current_user.user_id),
        "username": current_user.username,
        "role": current_user.role.value,
        "is_active": current_user.is_active,
    }


@router.patch("/me/password", status_code=status.HTTP_200_OK)
def change_own_password(
    body: ChangePasswordRequest,
    current_user: CurrentUserDep,
    db: Session = Depends(get_db),
):
    """Change the authenticated user's password."""
    with transactional_session(db):
        AuthService.change_password(
            db, current_user.user_id, body.current_password, body.new_password,
        )
    return {"message": "Password changed successfully."}


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreateRequest,
    _admin: AdminDep,
    db: Session = Depends(get_db),
):
    """Create a new user account (admin only)."""
    with transactional_session(db):
        user = AuthService.create_user(
            db, body.username, body.email, body.password, body.role,
        )
    return UserResponse.model_validate(user)


@router.get("/users", response_model=PaginatedUsersResponse)
def list_users(
    _admin: AdminDep,
    db: Session = Depends(get_db),
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    """List all users with optional filters (admin only)."""
    users, total = AuthService.list_users(db, page, page_size, is_active)
    return PaginatedUsersResponse.build(users, total, page, page_size)


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: UUID,
    _admin: AdminDep,
    db: Session = Depends(get_db),
):
    """Get a user by ID (admin only)."""
    user = AuthService.get_user(db, user_id)
    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    body: UserUpdateRequest,
    _admin: AdminDep,
    db: Session = Depends(get_db),
):
    """Update user fields such as role, email, or active status (admin only)."""
    with transactional_session(db):
        user = AuthService.update_user(
            db,
            user_id,
            email=body.email,
            role=body.role,
            is_active=body.is_active,
        )
    return UserResponse.model_validate(user)
