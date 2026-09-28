"""Unit tests for aggregated compliance dashboard service."""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from src.core.exceptions import EntityNotFoundException
from src.core.security import Role
from src.database.models import (
    ComplianceFramework,
    ComplianceStatus,
    ComplianceStatusRecord,
    DocumentType,
    EvidenceDocument,
    EvidenceValidity,
    GapReport,
    ProcessingStatus,
    Requirement,
    Severity,
    User,
)
from src.database.models.enums import GapStatus, GapType
from src.services.dashboard_service import DashboardService

DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _seed_base(session):
    user = User(
        id=DEV_USER_ID,
        username="test",
        email="test@test.local",
        hashed_password="$2b$12$fake",
        role=Role.COMPLIANCE_OFFICER,
    )
    session.add(user)
    session.flush()
    return user


def _seed_framework(session, name="SOC 2", version="2024", reqs=None):
    fw = ComplianceFramework(name=name, version=version, is_active=True)
    session.add(fw)
    session.flush()

    requirements = []
    for i, (code, severity_val, status_val) in enumerate(reqs or []):
        req = Requirement(
            framework_id=fw.id,
            requirement_code=code,
            title=f"Control {code}",
            description=f"Description for {code}",
            severity=severity_val,
        )
        session.add(req)
        session.flush()

        if status_val is not None:
            csr = ComplianceStatusRecord(
                requirement_id=req.id,
                status=status_val,
                status_reason=f"Status: {status_val.value}",
                last_evaluated_at=datetime.now(timezone.utc) if status_val != ComplianceStatus.GAP else None,
            )
            session.add(csr)
            session.flush()

        requirements.append(req)
    return fw, requirements


# ── System Overview ───────────────────────────────────────────────────


class TestSystemOverview:
    def test_empty_system(self, db_session):
        result = DashboardService.get_system_overview(db_session)
        assert result["total_frameworks"] == 0
        assert result["total_requirements"] == 0
        assert result["compliance_percentage"] == 0.0

    def test_with_data(self, db_session):
        _seed_base(db_session)
        _seed_framework(db_session, "SOC 2", "v1", [
            ("CC6.1", Severity.HIGH, ComplianceStatus.SATISFIED),
            ("CC6.2", Severity.MEDIUM, ComplianceStatus.GAP),
            ("CC6.3", Severity.LOW, None),
        ])
        _seed_framework(db_session, "ISO 27001", "v1", [
            ("A.5.1", Severity.HIGH, ComplianceStatus.SATISFIED),
        ])

        result = DashboardService.get_system_overview(db_session)
        assert result["total_frameworks"] == 2
        assert result["total_requirements"] == 4
        assert result["satisfied"] == 2
        assert result["gap"] == 1
        assert result["not_evaluated"] == 1
        assert result["compliance_percentage"] == 50.0

    def test_includes_gap_counts(self, db_session):
        _seed_base(db_session)
        fw, reqs = _seed_framework(db_session, reqs=[
            ("CC6.1", Severity.HIGH, ComplianceStatus.GAP),
        ])

        gap = GapReport(
            requirement_id=reqs[0].id,
            gap_type=GapType.MISSING_EVIDENCE,
            description="Missing.",
            requested_evidence=[],
            priority=Severity.HIGH,
            status=GapStatus.OPEN,
        )
        session = db_session
        session.add(gap)
        session.flush()

        result = DashboardService.get_system_overview(session)
        assert result["open_gaps"] == 1

    def test_includes_evidence_stats(self, db_session):
        _seed_base(db_session)
        for validity in [EvidenceValidity.VALID, EvidenceValidity.EXPIRING_SOON, EvidenceValidity.EXPIRED]:
            doc = EvidenceDocument(
                filename=f"doc_{validity.value}.txt",
                document_type=DocumentType.POLICY,
                storage_path=f"/tmp/{validity.value}",
                file_hash=f"hash_{validity.value}",
                file_size_bytes=100,
                uploaded_by=DEV_USER_ID,
                validity_status=validity,
                processing_status=ProcessingStatus.PROCESSED,
            )
            db_session.add(doc)
        db_session.flush()

        result = DashboardService.get_system_overview(db_session)
        assert result["total_evidence"] == 3
        assert result["expiring_evidence"] == 1
        assert result["expired_evidence"] == 1


# ── All Frameworks Summary ────────────────────────────────────────────


class TestAllFrameworksSummary:
    def test_empty(self, db_session):
        result = DashboardService.get_all_frameworks_summary(db_session)
        assert result == []

    def test_multiple_frameworks(self, db_session):
        _seed_base(db_session)
        _seed_framework(db_session, "Alpha", "v1", [
            ("A.1", Severity.HIGH, ComplianceStatus.SATISFIED),
            ("A.2", Severity.HIGH, ComplianceStatus.GAP),
        ])
        _seed_framework(db_session, "Beta", "v1", [
            ("B.1", Severity.MEDIUM, ComplianceStatus.SATISFIED),
        ])

        result = DashboardService.get_all_frameworks_summary(db_session)
        assert len(result) == 2

        alpha = next(r for r in result if r["framework_name"] == "Alpha")
        assert alpha["satisfied"] == 1
        assert alpha["gap"] == 1
        assert alpha["compliance_percentage"] == 50.0

        beta = next(r for r in result if r["framework_name"] == "Beta")
        assert beta["satisfied"] == 1
        assert beta["compliance_percentage"] == 100.0


# ── Framework Detail ──────────────────────────────────────────────────


class TestFrameworkDetail:
    def test_detail_with_requirements(self, db_session):
        _seed_base(db_session)
        fw, reqs = _seed_framework(db_session, reqs=[
            ("CC6.1", Severity.HIGH, ComplianceStatus.SATISFIED),
            ("CC6.2", Severity.MEDIUM, ComplianceStatus.PARTIAL),
            ("CC6.3", Severity.LOW, None),
        ])

        result = DashboardService.get_framework_detail(db_session, fw.id)
        assert result["total_requirements"] == 3
        assert result["satisfied"] == 1
        assert result["partial"] == 1
        assert result["not_evaluated"] == 1
        assert len(result["requirements"]) == 3

        req_detail = next(r for r in result["requirements"] if r["requirement_code"] == "CC6.1")
        assert req_detail["status"] == "SATISFIED"
        assert req_detail["severity"] == "HIGH"

    def test_not_found(self, db_session):
        with pytest.raises(EntityNotFoundException):
            DashboardService.get_framework_detail(db_session, uuid.uuid4())

    def test_includes_open_gap_count(self, db_session):
        _seed_base(db_session)
        fw, reqs = _seed_framework(db_session, reqs=[
            ("CC6.1", Severity.HIGH, ComplianceStatus.GAP),
        ])
        gap = GapReport(
            requirement_id=reqs[0].id,
            gap_type=GapType.MISSING_EVIDENCE,
            description="Missing.",
            requested_evidence=[],
            priority=Severity.HIGH,
            status=GapStatus.OPEN,
        )
        db_session.add(gap)
        db_session.flush()

        result = DashboardService.get_framework_detail(db_session, fw.id)
        assert result["requirements"][0]["open_gaps"] == 1


# ── Gap Summary ───────────────────────────────────────────────────────


class TestGapSummary:
    def test_empty(self, db_session):
        result = DashboardService.get_gap_summary(db_session)
        assert result["total"] == 0

    def test_counts_by_status(self, db_session):
        _seed_base(db_session)
        fw, reqs = _seed_framework(db_session, reqs=[
            ("CC6.1", Severity.HIGH, ComplianceStatus.GAP),
        ])

        for gs in [GapStatus.OPEN, GapStatus.OPEN, GapStatus.IN_REVIEW]:
            g = GapReport(
                requirement_id=reqs[0].id,
                gap_type=GapType.MISSING_EVIDENCE,
                description="Gap.",
                requested_evidence=[],
                priority=Severity.HIGH,
                status=gs,
            )
            db_session.add(g)
        db_session.flush()

        result = DashboardService.get_gap_summary(db_session)
        assert result["total"] == 3
        assert result["by_status"]["OPEN"] == 2
        assert result["by_status"]["IN_REVIEW"] == 1
        assert result["by_status"]["RESOLVED"] == 0


# ── Evidence Summary ──────────────────────────────────────────────────


class TestEvidenceSummary:
    def test_empty(self, db_session):
        result = DashboardService.get_evidence_summary(db_session)
        assert result["total"] == 0

    def test_counts_by_validity(self, db_session):
        _seed_base(db_session)
        for validity in [EvidenceValidity.VALID, EvidenceValidity.VALID, EvidenceValidity.EXPIRED]:
            doc = EvidenceDocument(
                filename=f"doc_{uuid.uuid4().hex[:6]}.txt",
                document_type=DocumentType.POLICY,
                storage_path=f"/tmp/{uuid.uuid4().hex}",
                file_hash=uuid.uuid4().hex,
                file_size_bytes=100,
                uploaded_by=DEV_USER_ID,
                validity_status=validity,
                processing_status=ProcessingStatus.PROCESSED,
            )
            db_session.add(doc)
        db_session.flush()

        result = DashboardService.get_evidence_summary(db_session)
        assert result["total"] == 3
        assert result["by_validity"]["VALID"] == 2
        assert result["by_validity"]["EXPIRED"] == 1
        assert result["by_processing"]["PROCESSED"] == 3
