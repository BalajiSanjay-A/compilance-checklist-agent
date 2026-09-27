"""Database model for compliance gap reports and requested remediations."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, List, Optional
import uuid

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSON,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from src.database.models.enums import GapStatus, GapType, Severity

if TYPE_CHECKING:
    from src.database.models.framework import Requirement
    from src.database.models.match import EvidenceMatch


class GapReport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Actionable compliance gap flagged by the evaluation engine."""

    __tablename__ = "gap_reports"
    __table_args__ = (
        Index("ix_gaps_req_status", "requirement_id", "status"),
        Index("ix_gaps_status_priority", "status", "priority"),
    )

    requirement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("requirements.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    evidence_match_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evidence_matches.id", ondelete="SET NULL"),
        nullable=True,
    )
    gap_type: Mapped[GapType] = mapped_column(
        Enum(GapType, name="gap_type_enum", native_enum=False),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requested_evidence: Mapped[List[Any]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="Specific evidence documents or configurations requested from user.",
    )
    priority: Mapped[Severity] = mapped_column(
        Enum(Severity, name="gap_priority_enum", native_enum=False),
        nullable=False,
        default=Severity.MEDIUM,
    )
    status: Mapped[GapStatus] = mapped_column(
        Enum(GapStatus, name="gap_status_enum", native_enum=False),
        nullable=False,
        default=GapStatus.OPEN,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    requirement: Mapped["Requirement"] = relationship(
        "Requirement",
        back_populates="gap_reports",
    )
    evidence_match: Mapped[Optional["EvidenceMatch"]] = relationship(
        "EvidenceMatch",
        back_populates="gap_reports",
    )
