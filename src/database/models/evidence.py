"""Database models for evidence documents and durable processing jobs."""

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, List, Optional
import uuid

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from src.database.models.enums import DocumentType, EvidenceValidity, JobStatus, ProcessingStatus

if TYPE_CHECKING:
    from src.database.models.match import EvidenceMatch
    from src.database.models.user import User


class EvidenceDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Uploaded compliance evidence artifact (policy, report, certificate, log)."""

    __tablename__ = "evidence_documents"
    __table_args__ = (
        Index("ix_evidence_hash", "file_hash"),
        Index("ix_evidence_status", "processing_status"),
        Index("ix_evidence_validity_dates", "valid_from", "expires_at"),
    )

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_type_enum", native_enum=False),
        nullable=False,
        default=DocumentType.OTHER,
    )
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    content_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Expiration and validity lifecycle
    valid_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expires_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    validity_status: Mapped[EvidenceValidity] = mapped_column(
        Enum(EvidenceValidity, name="evidence_validity_enum", native_enum=False),
        nullable=False,
        default=EvidenceValidity.VALID,
    )

    # Extraction and pipeline status
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="processing_status_enum", native_enum=False),
        nullable=False,
        default=ProcessingStatus.UPLOADED,
    )
    processing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    uploader: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="uploaded_documents",
    )
    matches: Mapped[List["EvidenceMatch"]] = relationship(
        "EvidenceMatch",
        back_populates="evidence",
        cascade="all, delete-orphan",
    )
    jobs: Mapped[List["DocumentProcessingJob"]] = relationship(
        "DocumentProcessingJob",
        back_populates="evidence",
        cascade="all, delete-orphan",
    )


class DocumentProcessingJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Durable job record for background document extraction and AI evaluation."""

    __tablename__ = "document_processing_jobs"
    __table_args__ = (
        Index("ix_jobs_status_scheduled", "status", "scheduled_at"),
    )

    evidence_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evidence_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_type: Mapped[str] = mapped_column(String(50), nullable=False, default="EXTRACT_TEXT")
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status_enum", native_enum=False),
        nullable=False,
        default=JobStatus.QUEUED,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    evidence: Mapped["EvidenceDocument"] = relationship(
        "EvidenceDocument",
        back_populates="jobs",
    )
