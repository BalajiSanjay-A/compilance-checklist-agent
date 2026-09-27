"""Integration tests for database models, relationships, and constraints."""

from datetime import date, datetime, timedelta, timezone
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.security import Role
from src.database.models import (
    ComplianceFramework,
    ComplianceStatus,
    ComplianceStatusHistory,
    ComplianceStatusRecord,
    DocumentProcessingJob,
    DocumentType,
    EvidenceDocument,
    EvidenceMatch,
    EvidenceValidity,
    GapReport,
    GapStatus,
    GapType,
    JobStatus,
    ProcessingStatus,
    Requirement,
    Severity,
    User,
)


def test_framework_and_requirement_creation(db_session: Session):
    """Verify creation and relationship between Framework and Requirement."""
    framework = ComplianceFramework(
        name="SOC 2 Type II",
        version="2017 TSC",
        description="AICPA Trust Services Criteria",
    )
    db_session.add(framework)
    db_session.flush()

    req = Requirement(
        framework_id=framework.id,
        requirement_code="CC6.1",
        title="Logical Access",
        description="Restricts logical access to authorized personnel.",
        severity=Severity.CRITICAL,
    )
    db_session.add(req)
    db_session.flush()

    # Query back
    saved_req = db_session.scalars(select(Requirement).where(Requirement.id == req.id)).one()
    assert saved_req.requirement_code == "CC6.1"
    assert saved_req.framework.name == "SOC 2 Type II"
    assert saved_req.severity == Severity.CRITICAL
    assert len(framework.requirements) == 1


def test_framework_unique_name_version_constraint(db_session: Session):
    """Verify unique constraint on (name, version) for frameworks."""
    f1 = ComplianceFramework(name="ISO 27001", version="2022")
    f2 = ComplianceFramework(name="ISO 27001", version="2022")
    db_session.add(f1)
    db_session.flush()

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(f2)
            db_session.flush()


def test_requirement_unique_code_per_framework_constraint(db_session: Session):
    """Verify unique constraint on (framework_id, requirement_code)."""
    framework = ComplianceFramework(name="Framework Test", version="1.0")
    db_session.add(framework)
    db_session.flush()

    r1 = Requirement(
        framework_id=framework.id,
        requirement_code="REQ-1",
        title="Req 1",
        description="Desc 1",
    )
    r2 = Requirement(
        framework_id=framework.id,
        requirement_code="REQ-1",
        title="Duplicate Req 1",
        description="Desc duplicate",
    )
    db_session.add(r1)
    db_session.flush()

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(r2)
            db_session.flush()


def test_enums_compliance_status_and_evidence_validity(db_session: Session):
    """Verify exact ComplianceStatus and EvidenceValidity enum values."""
    # ComplianceStatus
    assert ComplianceStatus.SATISFIED.value == "SATISFIED"
    assert ComplianceStatus.PARTIAL.value == "PARTIAL"
    assert ComplianceStatus.GAP.value == "GAP"

    # EvidenceValidity
    assert EvidenceValidity.VALID.value == "VALID"
    assert EvidenceValidity.EXPIRING_SOON.value == "EXPIRING_SOON"
    assert EvidenceValidity.EXPIRED.value == "EXPIRED"


def test_evidence_document_and_durable_jobs(db_session: Session):
    """Verify evidence document creation with hash, validity status, and job queueing."""
    user = User(
        username="uploader_user",
        email="uploader@example.com",
        hashed_password="fakehashedpassword",
        role=Role.COMPLIANCE_OFFICER,
    )
    db_session.add(user)
    db_session.flush()

    today = date.today()
    doc = EvidenceDocument(
        filename="access_policy.pdf",
        document_type=DocumentType.POLICY,
        storage_path="/storage/evidence/2026/09/hash123.bin",
        content_text="All systems enforce multi-factor authentication.",
        file_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        file_size_bytes=10240,
        uploaded_by=user.id,
        valid_from=today,
        expires_at=today + timedelta(days=365),
        validity_status=EvidenceValidity.VALID,
        processing_status=ProcessingStatus.UPLOADED,
    )
    db_session.add(doc)
    db_session.flush()

    # Create background processing job
    job = DocumentProcessingJob(
        evidence_id=doc.id,
        job_type="EXTRACT_TEXT",
        status=JobStatus.QUEUED,
        attempts=0,
    )
    db_session.add(job)
    db_session.flush()

    assert doc.uploader.username == "uploader_user"
    assert len(doc.jobs) == 1
    assert doc.jobs[0].status == JobStatus.QUEUED


def test_evidence_matching_many_to_many(db_session: Session):
    """
    Verify that a single evidence document can support multiple requirements
    through EvidenceMatch records.
    """
    framework = ComplianceFramework(name="SOC 2", version="2017")
    db_session.add(framework)
    db_session.flush()

    r1 = Requirement(framework_id=framework.id, requirement_code="CC6.1", title="Access", description="Logical Access")
    r2 = Requirement(framework_id=framework.id, requirement_code="CC6.2", title="Auth", description="User Auth")
    db_session.add_all([r1, r2])
    db_session.flush()

    doc = EvidenceDocument(
        filename="comprehensive_security_policy.pdf",
        document_type=DocumentType.POLICY,
        storage_path="/storage/evidence/policy.bin",
        content_text="Policy text supporting multiple controls.",
        file_hash="hash_multi_123",
        file_size_bytes=50000,
        validity_status=EvidenceValidity.VALID,
        processing_status=ProcessingStatus.PROCESSED,
    )
    db_session.add(doc)
    db_session.flush()

    # Match 1 for CC6.1
    m1 = EvidenceMatch(
        evidence_id=doc.id,
        requirement_id=r1.id,
        status=ComplianceStatus.SATISFIED,
        confidence=0.95,
        reasoning="Access control rules explicitly detailed.",
        supporting_evidence=["Section 2: RBAC enforced."],
        missing_evidence=[],
        requested_evidence=[],
        citation_verified=True,
        model_name="grok-beta",
        prompt_version="v1.0",
    )
    # Match 2 for CC6.2
    m2 = EvidenceMatch(
        evidence_id=doc.id,
        requirement_id=r2.id,
        status=ComplianceStatus.PARTIAL,
        confidence=0.65,
        reasoning="User registration covered but de-provisioning ambiguous.",
        supporting_evidence=["Section 3: Account creation."],
        missing_evidence=["De-provisioning within 24 hours SLA."],
        requested_evidence=["Submit Offboarding Procedure SOP."],
        citation_verified=True,
        model_name="grok-beta",
        prompt_version="v1.0",
    )
    db_session.add_all([m1, m2])
    db_session.flush()

    # Assert relations
    assert len(doc.matches) == 2
    assert len(r1.matches) == 1
    assert r1.matches[0].status == ComplianceStatus.SATISFIED
    assert len(r2.matches) == 1
    assert r2.matches[0].status == ComplianceStatus.PARTIAL
    assert r2.matches[0].requested_evidence == ["Submit Offboarding Procedure SOP."]


def test_compliance_status_unique_per_requirement_and_history(db_session: Session):
    """Verify ComplianceStatusRecord is unique per requirement and logs to history."""
    framework = ComplianceFramework(name="HIPAA", version="Security")
    db_session.add(framework)
    db_session.flush()

    req = Requirement(framework_id=framework.id, requirement_code="164.312", title="Technical Safeguards", description="Safeguards")
    db_session.add(req)
    db_session.flush()

    status_record = ComplianceStatusRecord(
        requirement_id=req.id,
        status=ComplianceStatus.SATISFIED,
        status_reason="All technical safeguards implemented.",
        effective_from=date.today(),
    )
    db_session.add(status_record)
    db_session.flush()

    # Attempting duplicate compliance_status for same requirement must fail
    duplicate_status = ComplianceStatusRecord(
        requirement_id=req.id,
        status=ComplianceStatus.GAP,
        status_reason="Duplicate attempt",
    )
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(duplicate_status)
            db_session.flush()

    # Test history logging
    history = ComplianceStatusHistory(
        requirement_id=req.id,
        previous_status=ComplianceStatus.GAP,
        new_status=ComplianceStatus.SATISFIED,
        changed_by="agent/evaluator",
        change_reason="Automated evidence evaluation completed successfully.",
    )
    db_session.add(history)
    db_session.flush()

    saved_histories = db_session.scalars(
        select(ComplianceStatusHistory).where(ComplianceStatusHistory.requirement_id == req.id)
    ).all()
    assert len(saved_histories) == 1
    assert saved_histories[0].new_status == ComplianceStatus.SATISFIED


def test_gap_report_creation_and_fields(db_session: Session):
    """Verify GapReport creation, priority, and structured requested evidence."""
    framework = ComplianceFramework(name="PCI-DSS", version="v4.0")
    db_session.add(framework)
    db_session.flush()

    req = Requirement(framework_id=framework.id, requirement_code="REQ-3", title="Cardholder Data", description="Protect Cardholder Data")
    db_session.add(req)
    db_session.flush()

    gap = GapReport(
        requirement_id=req.id,
        gap_type=GapType.MISSING_EVIDENCE,
        description="No encryption key rotation policy provided.",
        requested_evidence=["Provide KMS key rotation policy document."],
        priority=Severity.HIGH,
        status=GapStatus.OPEN,
    )
    db_session.add(gap)
    db_session.flush()

    assert gap.status == GapStatus.OPEN
    assert gap.priority == Severity.HIGH
    assert gap.requested_evidence == ["Provide KMS key rotation policy document."]
    assert gap.requirement.requirement_code == "REQ-3"
