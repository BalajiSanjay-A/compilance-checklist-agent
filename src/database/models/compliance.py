"""Database models for authoritative compliance status and audit history."""

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from src.database.models.enums import ComplianceStatus

if TYPE_CHECKING:
    from src.database.models.framework import Requirement
    from src.database.models.match import EvidenceMatch


class ComplianceStatusRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Authoritative current compliance state snapshot for a single requirement."""

    __tablename__ = "compliance_status"
    __table_args__ = (
        Index("ix_compliance_status_val", "status"),
    )

    requirement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    current_match_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evidence_matches.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[ComplianceStatus] = mapped_column(
        Enum(ComplianceStatus, name="compliance_status_enum", native_enum=False),
        nullable=False,
        default=ComplianceStatus.GAP,
    )
    status_reason: Mapped[str] = mapped_column(Text, nullable=False)
    effective_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    effective_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    last_evaluated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    requirement: Mapped["Requirement"] = relationship(
        "Requirement",
        back_populates="compliance_status",
    )
    current_match: Mapped[Optional["EvidenceMatch"]] = relationship(
        "EvidenceMatch",
        back_populates="compliance_status_record",
    )


class ComplianceStatusHistory(Base, UUIDPrimaryKeyMixin):
    """Immutable audit ledger recording compliance state transitions."""

    __tablename__ = "compliance_status_history"
    __table_args__ = (
        Index("ix_history_req_date", "requirement_id", "recorded_at"),
    )

    requirement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_status: Mapped[Optional[ComplianceStatus]] = mapped_column(
        Enum(ComplianceStatus, name="compliance_status_enum", native_enum=False),
        nullable=True,
    )
    new_status: Mapped[ComplianceStatus] = mapped_column(
        Enum(ComplianceStatus, name="compliance_status_enum", native_enum=False),
        nullable=False,
    )
    evidence_match_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evidence_matches.id", ondelete="SET NULL"),
        nullable=True,
    )
    changed_by: Mapped[str] = mapped_column(String(100), nullable=False)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    requirement: Mapped["Requirement"] = relationship(
        "Requirement",
        back_populates="status_history",
    )
