"""Domain and database enums."""

from enum import Enum


class ComplianceStatus(str, Enum):
    """Authoritative compliance status for requirements."""

    SATISFIED = "SATISFIED"
    PARTIAL = "PARTIAL"
    GAP = "GAP"


class EvidenceValidity(str, Enum):
    """Validity state of an evidence document based on expiration dates."""

    VALID = "VALID"
    EXPIRING_SOON = "EXPIRING_SOON"
    EXPIRED = "EXPIRED"


class ProcessingStatus(str, Enum):
    """Lifecycle status for uploaded evidence document processing."""

    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class JobStatus(str, Enum):
    """Durable job queue status."""

    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DocumentType(str, Enum):
    """Categories of evidence documents."""

    POLICY = "POLICY"
    AUDIT_LOG = "AUDIT_LOG"
    CERTIFICATE = "CERTIFICATE"
    CONFIG = "CONFIG"
    OTHER = "OTHER"


class Severity(str, Enum):
    """Risk severity levels for requirements and gaps."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class GapType(str, Enum):
    """Types of compliance gaps detected."""

    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    AMBIGUOUS_EVIDENCE = "AMBIGUOUS_EVIDENCE"
    EXPIRED_EVIDENCE = "EXPIRED_EVIDENCE"
    PARTIAL_COVERAGE = "PARTIAL_COVERAGE"


class GapStatus(str, Enum):
    """Workflow status for gap reports."""

    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"
    WAIVED = "WAIVED"
