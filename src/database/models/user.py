"""Database model for application users and role assignments."""

from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.security import Role
from src.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.database.models.evidence import EvidenceDocument


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """User account entity with role-based access control."""

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(
        Enum(Role, name="user_role_enum", native_enum=False),
        nullable=False,
        default=Role.COMPLIANCE_OFFICER,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    uploaded_documents: Mapped[List["EvidenceDocument"]] = relationship(
        "EvidenceDocument",
        back_populates="uploader",
    )
