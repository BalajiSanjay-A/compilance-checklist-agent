"""Unit tests for gap reporting lifecycle service."""

import uuid
from datetime import datetime, timezone

import pytest

from src.core.exceptions import EntityNotFoundException, ValidationException
from src.core.security import Role
from src.database.models import (
    ComplianceFramework,
    ComplianceStatus,
    ComplianceStatusRecord,
    DocumentType,
    EvidenceDocument,
    EvidenceMatch,
    EvidenceValidity,
    GapReport,
    ProcessingStatus,
    Requirement,
    Severity,
    User,
)
from src.database.models.enums import GapStatus, GapType
from src.services.gap_service import GapService

DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _seed(session):
    user = User(
        id=DEV_USER_ID,
        username="test",
        email="test@test.local",
        hashed_password="$2b$12$fake",
        role=Role.COMPLIANCE_OFFICER,
    )
    session.add(user)
    session.flush()

    fw = ComplianceFramework(name="SOC 2", version="2024", is_active=True)
    session.add(fw)
    session.flush()

    req = Requirement(
        framework_id=fw.id,
        requirement_code="CC6.1",
        title="Logical Access Controls",
        description="Org implements access controls.",
        severity=Severity.HIGH,
    )
    session.add(req)
    session.flush()

    return fw, req


def _create_gap(session, req, gap_status=GapStatus.OPEN, gap_type=GapType.MISSING_EVIDENCE):
    gap = GapReport(
        requirement_id=req.id,
        gap_type=gap_type,
        description="Missing access control policy.",
        requested_evidence=["Access control policy document"],
        priority=req.severity,
        status=gap_status,
    )
    session.add(gap)
    session.flush()
    return gap


# ── get_gap_report ─────────────────────────────────────────────────────


class TestGetGapReport:
    def test_found(self, db_session):
        _, req = _seed(db_session)
        gap = _create_gap(db_session, req)

        result = GapService.get_gap_report(db_session, gap.id)
        assert result.id == gap.id
        assert result.gap_type == GapType.MISSING_EVIDENCE

    def test_not_found(self, db_session):
        with pytest.raises(EntityNotFoundException, match="Gap report"):
            GapService.get_gap_report(db_session, uuid.uuid4())


# ── list_gap_reports ───────────────────────────────────────────────────


class TestListGapReports:
    def test_list_all(self, db_session):
        _, req = _seed(db_session)
        _create_gap(db_session, req)
        _create_gap(db_session, req, gap_type=GapType.PARTIAL_COVERAGE)

        items, total = GapService.list_gap_reports(db_session)
        assert total == 2
        assert len(items) == 2

    def test_filter_by_status(self, db_session):
        _, req = _seed(db_session)
        _create_gap(db_session, req, gap_status=GapStatus.OPEN)
        _create_gap(db_session, req, gap_status=GapStatus.IN_REVIEW)

        items, total = GapService.list_gap_reports(db_session, status=GapStatus.OPEN)
        assert total == 1
        assert items[0].status == GapStatus.OPEN

    def test_filter_by_requirement(self, db_session):
        fw, req = _seed(db_session)

        req2 = Requirement(
            framework_id=fw.id,
            requirement_code="CC6.2",
            title="Another Control",
            description="Description.",
            severity=Severity.MEDIUM,
        )
        db_session.add(req2)
        db_session.flush()

        _create_gap(db_session, req)
        _create_gap(db_session, req2)

        items, total = GapService.list_gap_reports(db_session, requirement_id=req.id)
        assert total == 1

    def test_filter_by_type(self, db_session):
        _, req = _seed(db_session)
        _create_gap(db_session, req, gap_type=GapType.MISSING_EVIDENCE)
        _create_gap(db_session, req, gap_type=GapType.AMBIGUOUS_EVIDENCE)

        items, total = GapService.list_gap_reports(
            db_session, gap_type=GapType.MISSING_EVIDENCE
        )
        assert total == 1

    def test_filter_by_priority(self, db_session):
        fw, req = _seed(db_session)
        _create_gap(db_session, req)

        req2 = Requirement(
            framework_id=fw.id,
            requirement_code="CC6.2",
            title="Low Priority",
            description="Low desc.",
            severity=Severity.LOW,
        )
        db_session.add(req2)
        db_session.flush()

        gap2 = GapReport(
            requirement_id=req2.id,
            gap_type=GapType.MISSING_EVIDENCE,
            description="Low gap.",
            requested_evidence=[],
            priority=Severity.LOW,
            status=GapStatus.OPEN,
        )
        db_session.add(gap2)
        db_session.flush()

        items, total = GapService.list_gap_reports(db_session, priority=Severity.HIGH)
        assert total == 1

    def test_pagination(self, db_session):
        _, req = _seed(db_session)
        for _ in range(5):
            _create_gap(db_session, req)

        items, total = GapService.list_gap_reports(db_session, page=1, page_size=2)
        assert total == 5
        assert len(items) == 2

    def test_empty_list(self, db_session):
        items, total = GapService.list_gap_reports(db_session)
        assert total == 0
        assert items == []


# ── update_gap_status ──────────────────────────────────────────────────


class TestUpdateGapStatus:
    def test_open_to_in_review(self, db_session):
        _, req = _seed(db_session)
        gap = _create_gap(db_session, req, gap_status=GapStatus.OPEN)

        result = GapService.update_gap_status(db_session, gap.id, GapStatus.IN_REVIEW)
        assert result.status == GapStatus.IN_REVIEW

    def test_open_to_waived(self, db_session):
        _, req = _seed(db_session)
        gap = _create_gap(db_session, req, gap_status=GapStatus.OPEN)

        result = GapService.update_gap_status(
            db_session, gap.id, GapStatus.WAIVED, resolution_notes="Risk accepted"
        )
        assert result.status == GapStatus.WAIVED
        assert result.resolution_notes == "Risk accepted"

    def test_in_review_to_resolved(self, db_session):
        _, req = _seed(db_session)
        gap = _create_gap(db_session, req, gap_status=GapStatus.IN_REVIEW)

        result = GapService.update_gap_status(
            db_session, gap.id, GapStatus.RESOLVED, resolution_notes="Fixed"
        )
        assert result.status == GapStatus.RESOLVED
        assert result.resolved_at is not None
        assert result.resolution_notes == "Fixed"

    def test_in_review_back_to_open(self, db_session):
        _, req = _seed(db_session)
        gap = _create_gap(db_session, req, gap_status=GapStatus.IN_REVIEW)

        result = GapService.update_gap_status(db_session, gap.id, GapStatus.OPEN)
        assert result.status == GapStatus.OPEN

    def test_waived_to_open(self, db_session):
        _, req = _seed(db_session)
        gap = _create_gap(db_session, req, gap_status=GapStatus.WAIVED)

        result = GapService.update_gap_status(db_session, gap.id, GapStatus.OPEN)
        assert result.status == GapStatus.OPEN

    def test_resolved_cannot_transition(self, db_session):
        _, req = _seed(db_session)
        gap = _create_gap(db_session, req, gap_status=GapStatus.RESOLVED)

        with pytest.raises(ValidationException, match="Cannot transition"):
            GapService.update_gap_status(db_session, gap.id, GapStatus.OPEN)

    def test_invalid_transition_open_to_resolved(self, db_session):
        _, req = _seed(db_session)
        gap = _create_gap(db_session, req, gap_status=GapStatus.OPEN)

        with pytest.raises(ValidationException, match="Cannot transition"):
            GapService.update_gap_status(db_session, gap.id, GapStatus.RESOLVED)

    def test_not_found(self, db_session):
        with pytest.raises(EntityNotFoundException):
            GapService.update_gap_status(db_session, uuid.uuid4(), GapStatus.IN_REVIEW)
