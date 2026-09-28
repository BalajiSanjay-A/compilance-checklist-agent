"""Authentication and user management service."""

import uuid
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.exceptions import (
    AuthenticationException,
    DuplicateEntityException,
    EntityNotFoundException,
    ValidationException,
)
from src.core.logging import get_logger
from src.core.security import Role, get_password_hash, verify_password
from src.database.models import User

logger = get_logger("services.auth")

MIN_PASSWORD_LENGTH = 8


class AuthService:
    """User authentication and management operations."""

    @staticmethod
    def authenticate_user(
        session: Session,
        username: str,
        password: str,
    ) -> User:
        """Verify credentials and return the authenticated user.

        Raises AuthenticationException on invalid username or password.
        """
        user = session.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()

        if not user:
            verify_password(password, get_password_hash("dummy"))
            raise AuthenticationException("Invalid username or password.")

        if not user.is_active:
            raise AuthenticationException("User account is deactivated.")

        if not verify_password(password, user.hashed_password):
            raise AuthenticationException("Invalid username or password.")

        return user

    @staticmethod
    def create_user(
        session: Session,
        username: str,
        email: str,
        password: str,
        role: Role,
    ) -> User:
        """Create a new user account."""
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValidationException(
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
            )

        existing = session.execute(
            select(User).where(
                (User.username == username) | (User.email == email)
            )
        ).scalar_one_or_none()

        if existing:
            field = "username" if existing.username == username else "email"
            raise DuplicateEntityException(
                f"User with this {field} already exists.",
                details={field: username if field == "username" else email},
            )

        user = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            role=role,
            is_active=True,
        )
        session.add(user)
        session.flush()
        logger.info("Created user: %s (role: %s)", username, role.value)
        return user

    @staticmethod
    def get_user(session: Session, user_id: uuid.UUID) -> User:
        """Get a user by ID."""
        user = session.get(User, user_id)
        if not user:
            raise EntityNotFoundException(
                f"User '{user_id}' not found",
                details={"user_id": str(user_id)},
            )
        return user

    @staticmethod
    def list_users(
        session: Session,
        page: int = 1,
        page_size: int = 50,
        is_active: Optional[bool] = None,
    ) -> Tuple[List[User], int]:
        """List users with optional active filter and pagination."""
        query = session.query(User)

        if is_active is not None:
            query = query.filter(User.is_active == is_active)

        total_count = query.count()
        users = (
            query.order_by(User.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return users, total_count

    @staticmethod
    def update_user(
        session: Session,
        user_id: uuid.UUID,
        email: Optional[str] = None,
        role: Optional[Role] = None,
        is_active: Optional[bool] = None,
    ) -> User:
        """Update user fields (admin operation)."""
        user = session.get(User, user_id)
        if not user:
            raise EntityNotFoundException(
                f"User '{user_id}' not found",
                details={"user_id": str(user_id)},
            )

        if email is not None:
            existing = session.execute(
                select(User).where(User.email == email, User.id != user_id)
            ).scalar_one_or_none()
            if existing:
                raise DuplicateEntityException(
                    "User with this email already exists.",
                    details={"email": email},
                )
            user.email = email

        if role is not None:
            user.role = role

        if is_active is not None:
            user.is_active = is_active

        session.flush()
        logger.info("Updated user %s: email=%s role=%s active=%s", user_id, email, role, is_active)
        return user

    @staticmethod
    def change_password(
        session: Session,
        user_id: uuid.UUID,
        current_password: str,
        new_password: str,
    ) -> User:
        """Change a user's own password after verifying current password."""
        user = session.get(User, user_id)
        if not user:
            raise EntityNotFoundException(
                f"User '{user_id}' not found",
                details={"user_id": str(user_id)},
            )

        if not verify_password(current_password, user.hashed_password):
            raise AuthenticationException("Current password is incorrect.")

        if len(new_password) < MIN_PASSWORD_LENGTH:
            raise ValidationException(
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
            )

        user.hashed_password = get_password_hash(new_password)
        session.flush()
        logger.info("Password changed for user %s", user_id)
        return user
