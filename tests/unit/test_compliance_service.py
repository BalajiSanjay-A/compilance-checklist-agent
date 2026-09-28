"""Unit tests for compliance evaluation engine."""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from src.config import Settings
from src.core.exceptions import EntityNotFoundException
from src.core.security import Role
from src.database.models import (
    ComplianceFramework,
    ComplianceStatus,
    ComplianceStatusHistory,
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
from src.services.compliance_service import (
    ComplianceEvaluationService,
    _normalize_whitespace,
)

DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _make_settings():
    return Settings(
        app_env="test",
        ai_mock_mode=True,
        use_sqlite_fallback=True,
        sqlite_db_path=":memory:",
        expiration_warning_days=30,
    )


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

    csr = ComplianceStatusRecord(
        requirement_id=req.id,
        status=ComplianceStatus.GAP,
        status_reason="Initial baseline",
    )
    session.add(csr)
    session.flush()

    evidence = EvidenceDocument(
        filename="policy.txt",
        document_type=DocumentType.POLICY,
        storage_path="/tmp/test/policy.txt",
        content_text="Our organization implements logical access controls including MFA and RBAC.",
        file_hash="abc123",
        file_size_bytes=1024,
        uploaded_by=DEV_USER_ID,
        validity_status=EvidenceValidity.VALID,
        processing_status=ProcessingStatus.PROCESSED,
    )
    session.add(evidence)
    session.flush()

    return fw, req, evidence


# ── Normalize Whitespace ───────────────────────────────────────────────


class TestNormalizeWhitespace:
    def test_collapses_spaces(self):
        assert _normalize_whitespace("hello   world") == "hello world"

    def test_collapses_newlines(self):
        assert _normalize_whitespace("hello\n\nworld") == "hello world"

    def test_collapses_tabs(self):
        assert _normalize_whitespace("hello\t\tworld") == "hello world"

    def test_strips_edges(self):
        assert _normalize_whitespace("  hello  ") == "hello"

    def test_lowercases(self):
        assert _normalize_whitespace("Hello World") == "hello world"


# ── Citation Verification ──────────────────────────────────────────────


class TestCitationVerification:
    def test_verified_when_quotes_match(self, db_session):
        _, req, evidence = _seed(db_session)
        match = EvidenceMatch(
            evidence_id=evidence.id,
            requirement_id=req.id,
            status=ComplianceStatus.SATISFIED,
            confidence=0.9,
            reasoning="Good",
            supporting_evidence=["logical access controls including MFA"],
            missing_evidence=[],
            requested_evidence=[],
            citation_verified=False,
            model_name="mock",
            prompt_version="v1.0",
            evaluated_at=datetime.now(timezone.utc),
        )
        db_session.add(match)
        db_session.flush()

        ok, verified, failed = ComplianceEvaluationService.verify_citations(match, evidence)
        assert ok is True
        assert len(verified) == 1
        assert len(failed) == 0

    def test_fails_when_quote_not_found(self, db_session):
        _, req, evidence = _seed(db_session)
        match = EvidenceMatch(
            evidence_id=evidence.id,
            requirement_id=req.id,
            status=ComplianceStatus.SATISFIED,
            confidence=0.9,
            reasoning="Good",
            supporting_evidence=["this quote does not exist in the document"],
            missing_evidence=[],
            requested_evidence=[],
            citation_verified=False,
            model_name="mock",
            prompt_version="v1.0",
            evaluated_at=datetime.now(timezone.utc),
        )
        db_session.add(match)
        db_session.flush()

        ok, verified, failed = ComplianceEvaluationService.verify_citations(match, evidence)
        assert ok is False
        assert len(verified) == 0
        assert len(failed) == 1

    def test_whitespace_normalized_matching(self, db_session):
        _, req, evidence = _seed(db_session)
        match = EvidenceMatch(
            evidence_id=evidence.id,
            requirement_id=req.id,
            status=ComplianceStatus.SATISFIED,
            confidence=0.9,
            reasoning="Good",
            supporting_evidence=["logical  access   controls   including   MFA"],
            missing_evidence=[],
            requested_evidence=[],
            citation_verified=False,
            model_name="mock",
            prompt_version="v1.0",
            evaluated_at=datetime.now(timezone.utc),
        )
        db_session.add(match)
        db_session.flush()

        ok, verified, failed = ComplianceEvaluationService.verify_citations(match, evidence)
        assert ok is True

    def test_case_insensitive_matching(self, db_session):
        _, req, evidence = _seed(db_session)
        match = EvidenceMatch(
            evidence_id=evidence.id,
            requirement_id=req.id,
            status=ComplianceStatus.SATISFIED,
            confidence=0.9,
            reasoning="Good",
            supporting_evidence=["LOGICAL ACCESS CONTROLS INCLUDING MFA"],
            missing_evidence=[],
            requested_evidence=[],
            citation_verified=False,
            model_name="mock",
            prompt_version="v1.0",
            evaluated_at=datetime.now(timezone.utc),
        )
        db_session.add(match)
        db_session.flush()

        ok, verified, failed = ComplianceEvaluationService.verify_citations(match, evidence)
        assert ok is True

    def test_no_content_text(self, db_session):
        _, req, evidence = _seed(db_session)
        evidence.content_text = None
        db_session.flush()

        match = EvidenceMatch(
            evidence_id=evidence.id,
            requirement_id=req.id,
            status=ComplianceStatus.SATISFIED,
            confidence=0.9,
            reasoning="Good",
            supporting_evidence=["something"],
            missing_evidence=[],
            requested_evidence=[],
            citation_verified=False,
            model_name="mock",
            prompt_version="v1.0",
            evaluated_at=datetime.now(timezone.utc),
        )
        db_session.add(match)
        db_session.flush()

        ok, verified, failed = ComplianceEvaluationService.verify_citations(match, evidence)
        assert ok is False

    def test_empty_quotes_not_verified(self, db_session):
        _, req, evidence = _seed(db_session)
        match = EvidenceMatch(
            evidence_id=evidence.id,
            requirement_id=req.id,
            status=ComplianceStatus.SATISFIED,
            confidence=0.9,
            reasoning="Good",
            supporting_evidence=[],
            missing_evidence=[],
            requested_evidence=[],
            citation_verified=False,
            model_name="mock",
            prompt_version="v1.0",
            evaluated_at=datetime.now(timezone.utc),
        )
        db_session.add(match)
        db_session.flush()

        ok, verified, failed = ComplianceEvaluationService.verify_citations(match, evidence)
        assert ok is False


# ── Evidence Validity Computation ──────────────────────────────────────


class TestComputeEvidenceValidity:
    def test_valid_no_expiry(self, db_session):
        _, _, evidence = _seed(db_session)
        evidence.expires_at = None
        result = ComplianceEvaluationService.compute_evidence_validity(evidence, _make_settings())
        assert result == EvidenceValidity.VALID

    def test_valid_future_expiry(self, db_session):
        _, _, evidence = _seed(db_session)
        evidence.expires_at = date.today() + timedelta(days=90)
        result = ComplianceEvaluationService.compute_evidence_validity(evidence, _make_settings())
        assert result == EvidenceValidity.VALID

    def test_expiring_soon(self, db_session):
        _, _, evidence = _seed(db_session)
        evidence.expires_at = date.today() + timedelta(days=15)
        result = ComplianceEvaluationService.compute_evidence_validity(evidence, _make_settings())
        assert result == EvidenceValidity.EXPIRING_SOON

    def test_expired(self, db_session):
        _, _, evidence = _seed(db_session)
        evidence.expires_at = date.today() - timedelta(days=1)
        result = ComplianceEvaluationService.compute_evidence_validity(evidence, _make_settings())
        assert result == EvidenceValidity.EXPIRED

    def test_boundary_day_exact_expiry(self, db_session):
        _, _, evidence = _seed(db_session)
        evidence.expires_at = date.today()
        result = ComplianceEvaluationService.compute_evidence_validity(evidence, _make_settings())
        assert result == EvidenceValidity.EXPIRING_SOON

    def test_boundary_warning_start(self, db_session):
        _, _, evidence = _seed(db_session)
        evidence.expires_at = date.today() + timedelta(days=30)
        result = ComplianceEvaluationService.compute_evidence_validity(evidence, _make_settings())
        assert result == EvidenceValidity.EXPIRING_SOON


# ── Status Resolution ──────────────────────────────────────────────────


class TestResolveComplianceStatus:
    def _make_match(self, status, missing=None):
        class FakeMatch:
            pass

        m = FakeMatch()
        m.status = status
        m.reasoning = "test reason"
        m.missing_evidence = missing or []
        return m

    def test_satisfied_all_good(self):
        m = self._make_match(ComplianceStatus.SATISFIED)
        status, reason = ComplianceEvaluationService.resolve_compliance_status(
            m, True, [], EvidenceValidity.VALID
        )
        assert status == ComplianceStatus.SATISFIED

    def test_gap_on_expired_evidence(self):
        m = self._make_match(ComplianceStatus.SATISFIED)
        status, reason = ComplianceEvaluationService.resolve_compliance_status(
            m, True, [], EvidenceValidity.EXPIRED
        )
        assert status == ComplianceStatus.GAP
        assert "expired" in reason.lower()

    def test_gap_from_llm_gap(self):
        m = self._make_match(ComplianceStatus.GAP)
        status, reason = ComplianceEvaluationService.resolve_compliance_status(
            m, True, [], EvidenceValidity.VALID
        )
        assert status == ComplianceStatus.GAP

    def test_partial_from_llm_partial(self):
        m = self._make_match(ComplianceStatus.PARTIAL)
        status, reason = ComplianceEvaluationService.resolve_compliance_status(
            m, True, [], EvidenceValidity.VALID
        )
        assert status == ComplianceStatus.PARTIAL

    def test_partial_on_failed_citations(self):
        m = self._make_match(ComplianceStatus.SATISFIED)
        status, reason = ComplianceEvaluationService.resolve_compliance_status(
            m, False, ["bad quote"], EvidenceValidity.VALID
        )
        assert status == ComplianceStatus.PARTIAL
        assert "citation" in reason.lower()

    def test_partial_on_missing_evidence(self):
        m = self._make_match(ComplianceStatus.SATISFIED, missing=["some control"])
        status, reason = ComplianceEvaluationService.resolve_compliance_status(
            m, True, [], EvidenceValidity.VALID
        )
        assert status == ComplianceStatus.PARTIAL

    def test_expiring_soon_does_not_block_satisfied(self):
        m = self._make_match(ComplianceStatus.SATISFIED)
        status, reason = ComplianceEvaluationService.resolve_compliance_status(
            m, True, [], EvidenceValidity.EXPIRING_SOON
        )
        assert status == ComplianceStatus.SATISFIED


# ── Full Evaluation Pipeline ───────────────────────────────────────────


class TestEvaluateMatch:
    def _create_match(self, session, req, evidence, match_status=ComplianceStatus.SATISFIED):
        match = EvidenceMatch(
            evidence_id=evidence.id,
            requirement_id=req.id,
            status=match_status,
            confidence=0.9,
            reasoning="Evidence matches requirement.",
            supporting_evidence=["logical access controls including MFA"],
            missing_evidence=[],
            requested_evidence=[],
            citation_verified=False,
            model_name="mock",
            prompt_version="v1.0",
            evaluated_at=datetime.now(timezone.utc),
        )
        session.add(match)
        session.flush()
        return match

    def test_full_pipeline_satisfied(self, db_session):
        _, req, evidence = _seed(db_session)
        match = self._create_match(db_session, req, evidence)

        result = ComplianceEvaluationService.evaluate_match(
            db_session, match.id, _make_settings()
        )
        assert result.status == ComplianceStatus.SATISFIED
        assert result.current_match_id == match.id

        reloaded = db_session.get(EvidenceMatch, match.id)
        assert reloaded.citation_verified is True

    def test_full_pipeline_gap_creates_report(self, db_session):
        _, req, evidence = _seed(db_session)
        match = EvidenceMatch(
            evidence_id=evidence.id,
            requirement_id=req.id,
            status=ComplianceStatus.GAP,
            confidence=0.1,
            reasoning="No relevant evidence.",
            supporting_evidence=[],
            missing_evidence=["Logical Access Controls"],
            requested_evidence=["Access control policy document"],
            citation_verified=False,
            model_name="mock",
            prompt_version="v1.0",
            evaluated_at=datetime.now(timezone.utc),
        )
        db_session.add(match)
        db_session.flush()

        result = ComplianceEvaluationService.evaluate_match(
            db_session, match.id, _make_settings()
        )
        assert result.status == ComplianceStatus.GAP

        gaps = db_session.query(GapReport).filter(
            GapReport.requirement_id == req.id
        ).all()
        assert len(gaps) >= 1
        assert gaps[0].gap_type == GapType.MISSING_EVIDENCE

    def test_history_recorded_on_transition(self, db_session):
        _, req, evidence = _seed(db_session)
        match = self._create_match(db_session, req, evidence)

        ComplianceEvaluationService.evaluate_match(
            db_session, match.id, _make_settings()
        )

        history = db_session.query(ComplianceStatusHistory).filter(
            ComplianceStatusHistory.requirement_id == req.id
        ).all()
        assert len(history) == 1
        assert history[0].previous_status == ComplianceStatus.GAP
        assert history[0].new_status == ComplianceStatus.SATISFIED

    def test_expired_evidence_forces_gap(self, db_session):
        _, req, evidence = _seed(db_session)
        evidence.expires_at = date.today() - timedelta(days=5)
        db_session.flush()

        match = self._create_match(db_session, req, evidence)
        result = ComplianceEvaluationService.evaluate_match(
            db_session, match.id, _make_settings()
        )
        assert result.status == ComplianceStatus.GAP

    def test_match_not_found_raises(self, db_session):
        _seed(db_session)
        with pytest.raises(EntityNotFoundException):
            ComplianceEvaluationService.evaluate_match(
                db_session, uuid.uuid4(), _make_settings()
            )

    def test_citation_failure_creates_gap_report(self, db_session):
        _, req, evidence = _seed(db_session)
        match = EvidenceMatch(
            evidence_id=evidence.id,
            requirement_id=req.id,
            status=ComplianceStatus.SATISFIED,
            confidence=0.9,
            reasoning="Looks good.",
            supporting_evidence=["this is a hallucinated quote that does not exist"],
            missing_evidence=[],
            requested_evidence=["Better documentation"],
            citation_verified=False,
            model_name="mock",
            prompt_version="v1.0",
            evaluated_at=datetime.now(timezone.utc),
        )
        db_session.add(match)
        db_session.flush()

        result = ComplianceEvaluationService.evaluate_match(
            db_session, match.id, _make_settings()
        )
        assert result.status == ComplianceStatus.PARTIAL

        gaps = db_session.query(GapReport).filter(
            GapReport.requirement_id == req.id
        ).all()
        assert len(gaps) >= 1
        assert gaps[0].gap_type == GapType.AMBIGUOUS_EVIDENCE


# ── Refresh Expiration ─────────────────────────────────────────────────


class TestRefreshExpiration:
    def test_updates_expired_documents(self, db_session):
        _, _, evidence = _seed(db_session)
        evidence.expires_at = date.today() - timedelta(days=1)
        evidence.validity_status = EvidenceValidity.VALID
        db_session.flush()

        changed = ComplianceEvaluationService.refresh_expiration_status(
            db_session, _make_settings()
        )
        assert changed == 1
        assert evidence.validity_status == EvidenceValidity.EXPIRED

    def test_no_changes_when_current(self, db_session):
        _, _, evidence = _seed(db_session)
        evidence.expires_at = date.today() + timedelta(days=90)
        evidence.validity_status = EvidenceValidity.VALID
        db_session.flush()

        changed = ComplianceEvaluationService.refresh_expiration_status(
            db_session, _make_settings()
        )
        assert changed == 0


# ── Framework Summary ──────────────────────────────────────────────────


class TestFrameworkComplianceSummary:
    def test_summary(self, db_session):
        fw, req, _ = _seed(db_session)

        summary = ComplianceEvaluationService.get_framework_compliance_summary(
            db_session, fw.id
        )
        assert summary["total_requirements"] == 1
        assert summary["gap"] == 1
        assert summary["compliance_percentage"] == 0.0

    def test_framework_not_found(self, db_session):
        with pytest.raises(EntityNotFoundException):
            ComplianceEvaluationService.get_framework_compliance_summary(
                db_session, uuid.uuid4()
            )
