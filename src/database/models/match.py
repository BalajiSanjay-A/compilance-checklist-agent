"""Database model for evidence match evaluation events."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, List, Optional
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from src.database.models.enums import ComplianceStatus

if TYPE_CHECKING:
    from src.database.models.compliance import ComplianceStatusRecord
    from src.database.models.evidence import EvidenceDocument
    from src.database.models.gap_report import GapReport
    from src.database.models.framework import Requirement


class EvidenceMatch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Immutable evaluation event recording an AI assessment between
    an evidence document and a compliance requirement.
    """

    __tablename__ = "evidence_matches"
    __table_args__ = (
        Index("ix_matches_req_eval", "requirement_id", "evaluated_at"),
        Index("ix_matches_evidence", "evidence_id"),
    )

    evidence_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evidence_documents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("requirements.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[ComplianceStatus] = mapped_column(
        Enum(ComplianceStatus, name="compliance_status_enum", native_enum=False),
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Confidence score from model (recorded strictly as audit metadata).",
    )
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_evidence: Mapped[List[Any]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="Array of direct quotes extracted from evidence.",
    )
    missing_evidence: Mapped[List[Any]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="Array of unmet criteria.",
    )
    requested_evidence: Mapped[List[Any]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="Array of recommended remediations.",
    )
    citation_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True if quotes were deterministically verified against raw document text.",
    )
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    evidence: Mapped["EvidenceDocument"] = relationship(
        "EvidenceDocument",
        back_populates="matches",
    )
    requirement: Mapped["Requirement"] = relationship(
        "Requirement",
        back_populates="matches",
    )
    compliance_status_record: Mapped[Optional["ComplianceStatusRecord"]] = relationship(
        "ComplianceStatusRecord",
        back_populates="current_match",
    )
    gap_reports: Mapped[List["GapReport"]] = relationship(
        "GapReport",
        back_populates="evidence_match",
    )
