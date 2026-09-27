"""Database models for compliance frameworks and requirements."""

import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from src.database.models.enums import Severity

if TYPE_CHECKING:
    from src.database.models.compliance import ComplianceStatusHistory, ComplianceStatusRecord
    from src.database.models.gap_report import GapReport
    from src.database.models.match import EvidenceMatch


class ComplianceFramework(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Regulatory or industry compliance framework (e.g. SOC 2, ISO 27001)."""

    __tablename__ = "compliance_frameworks"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_framework_name_version"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    requirements: Mapped[List["Requirement"]] = relationship(
        "Requirement",
        back_populates="framework",
        cascade="all, delete-orphan",
        order_by="Requirement.requirement_code",
    )


class Requirement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Individual compliance checklist control or requirement item."""

    __tablename__ = "requirements"
    __table_args__ = (
        UniqueConstraint("framework_id", "requirement_code", name="uq_requirement_framework_code"),
        Index("ix_requirements_framework_active", "framework_id", "is_active"),
    )

    framework_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("compliance_frameworks.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    requirement_code: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[Severity] = mapped_column(
        Enum(Severity, name="severity_enum", native_enum=False),
        nullable=False,
        default=Severity.MEDIUM,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    framework: Mapped["ComplianceFramework"] = relationship(
        "ComplianceFramework",
        back_populates="requirements",
    )
    matches: Mapped[List["EvidenceMatch"]] = relationship(
        "EvidenceMatch",
        back_populates="requirement",
        cascade="all, delete-orphan",
        order_by="desc(EvidenceMatch.evaluated_at)",
    )
    compliance_status: Mapped[Optional["ComplianceStatusRecord"]] = relationship(
        "ComplianceStatusRecord",
        back_populates="requirement",
        uselist=False,
        cascade="all, delete-orphan",
    )
    status_history: Mapped[List["ComplianceStatusHistory"]] = relationship(
        "ComplianceStatusHistory",
        back_populates="requirement",
        cascade="all, delete-orphan",
        order_by="desc(ComplianceStatusHistory.recorded_at)",
    )
    gap_reports: Mapped[List["GapReport"]] = relationship(
        "GapReport",
        back_populates="requirement",
        cascade="all, delete-orphan",
    )
