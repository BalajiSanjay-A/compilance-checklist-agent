"""Deterministic compliance evaluation engine.

This service is the authoritative decision layer. The LLM advises; this
service enforces compliance status based on:
1. Citation verification (verbatim quote matching against source text)
2. Missing evidence checks
3. Evidence validity / expiration date checks
4. Deterministic status resolution
"""

import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import and_
from sqlalchemy.orm import Session

from src.config import Settings, get_settings
from src.core.exceptions import EntityNotFoundException, ValidationException
from src.core.logging import get_logger
from src.database.models import (
    ComplianceStatus,
    ComplianceStatusHistory,
    ComplianceStatusRecord,
    EvidenceDocument,
    EvidenceMatch,
    EvidenceValidity,
    GapReport,
    Requirement,
)
from src.database.models.enums import GapStatus, GapType, Severity

logger = get_logger("services.compliance")


def _normalize_whitespace(text: str) -> str:
    """Collapse all whitespace (spaces, newlines, tabs) into single spaces and strip."""
    return re.sub(r"\s+", " ", text).strip().lower()


class ComplianceEvaluationService:
    """Deterministic compliance evaluation engine."""

    @staticmethod
    def verify_citations(
        match: EvidenceMatch,
        evidence: EvidenceDocument,
    ) -> Tuple[bool, List[str], List[str]]:
        """Verify that all supporting_evidence quotes exist verbatim in the evidence text.

        Returns (all_verified, verified_quotes, failed_quotes).
        """
        if not evidence.content_text:
            return False, [], list(match.supporting_evidence or [])

        normalized_source = _normalize_whitespace(evidence.content_text)
        verified = []
        failed = []

        for quote in (match.supporting_evidence or []):
            normalized_quote = _normalize_whitespace(quote)
            if not normalized_quote:
                continue
            if normalized_quote in normalized_source:
                verified.append(quote)
            else:
                failed.append(quote)

        all_ok = len(failed) == 0 and len(verified) > 0
        return all_ok, verified, failed

    @staticmethod
    def compute_evidence_validity(
        evidence: EvidenceDocument,
        settings: Optional[Settings] = None,
        reference_date: Optional[date] = None,
    ) -> EvidenceValidity:
        """Compute evidence validity based on expiration dates."""
        settings = settings or get_settings()
        today = reference_date or date.today()

        if evidence.expires_at is None:
            return EvidenceValidity.VALID

        if today > evidence.expires_at:
            return EvidenceValidity.EXPIRED

        warning_date = evidence.expires_at - timedelta(days=settings.expiration_warning_days)
        if today >= warning_date:
            return EvidenceValidity.EXPIRING_SOON

        return EvidenceValidity.VALID

    @staticmethod
    def resolve_compliance_status(
        match: EvidenceMatch,
        citations_verified: bool,
        failed_quotes: List[str],
        evidence_validity: EvidenceValidity,
    ) -> Tuple[ComplianceStatus, str]:
        """Deterministically resolve compliance status from evaluation factors.

        Returns (status, reason).
        """
        if evidence_validity == EvidenceValidity.EXPIRED:
            return (
                ComplianceStatus.GAP,
                "Evidence has expired. Fresh evidence required.",
            )

        if match.status == ComplianceStatus.GAP:
            return (
                ComplianceStatus.GAP,
                match.reasoning,
            )

        if match.status == ComplianceStatus.PARTIAL:
            return (
                ComplianceStatus.PARTIAL,
                match.reasoning,
            )

        if not citations_verified:
            reason_parts = ["Citation verification failed."]
            if failed_quotes:
                reason_parts.append(
                    f"{len(failed_quotes)} quote(s) could not be verified in the source document."
                )
            return (
                ComplianceStatus.PARTIAL,
                " ".join(reason_parts),
            )

        has_missing = bool(match.missing_evidence)
        if has_missing:
            return (
                ComplianceStatus.PARTIAL,
                f"Missing evidence items remain: {', '.join(match.missing_evidence[:3])}",
            )

        return (
            ComplianceStatus.SATISFIED,
            "All criteria met: LLM evaluation satisfied, citations verified, evidence valid.",
        )

    @staticmethod
    def evaluate_match(
        session: Session,
        match_id: uuid.UUID,
        settings: Optional[Settings] = None,
    ) -> ComplianceStatusRecord:
        """Run the full deterministic compliance evaluation pipeline for a match.

        1. Load match + evidence + requirement
        2. Verify citations
        3. Check evidence validity
        4. Resolve compliance status
        5. Update compliance_status record
        6. Log status history
        7. Generate gap report if needed
        """
        settings = settings or get_settings()

        match = session.get(EvidenceMatch, match_id)
        if not match:
            raise EntityNotFoundException(
                f"Evidence match '{match_id}' not found",
                details={"match_id": str(match_id)},
            )

        evidence = session.get(EvidenceDocument, match.evidence_id)
        if not evidence:
            raise EntityNotFoundException(
                f"Evidence document '{match.evidence_id}' not found",
                details={"evidence_id": str(match.evidence_id)},
            )

        requirement = session.get(Requirement, match.requirement_id)
        if not requirement:
            raise EntityNotFoundException(
                f"Requirement '{match.requirement_id}' not found",
                details={"requirement_id": str(match.requirement_id)},
            )

        citations_ok, verified_quotes, failed_quotes = (
            ComplianceEvaluationService.verify_citations(match, evidence)
        )

        match.citation_verified = citations_ok
        session.flush()

        validity = ComplianceEvaluationService.compute_evidence_validity(
            evidence, settings
        )
        if evidence.validity_status != validity:
            evidence.validity_status = validity
            session.flush()

        new_status, reason = ComplianceEvaluationService.resolve_compliance_status(
            match, citations_ok, failed_quotes, validity,
        )

        status_record = (
            session.query(ComplianceStatusRecord)
            .filter(ComplianceStatusRecord.requirement_id == requirement.id)
            .first()
        )

        if not status_record:
            status_record = ComplianceStatusRecord(
                requirement_id=requirement.id,
                status=new_status,
                status_reason=reason,
                current_match_id=match.id,
                last_evaluated_at=datetime.now(timezone.utc),
            )
            session.add(status_record)
        else:
            previous_status = status_record.status

            history = ComplianceStatusHistory(
                requirement_id=requirement.id,
                previous_status=previous_status,
                new_status=new_status,
                evidence_match_id=match.id,
                changed_by="system:compliance-engine",
                change_reason=reason,
            )
            session.add(history)

            status_record.status = new_status
            status_record.status_reason = reason
            status_record.current_match_id = match.id
            status_record.last_evaluated_at = datetime.now(timezone.utc)

        session.flush()

        if new_status in (ComplianceStatus.GAP, ComplianceStatus.PARTIAL):
            ComplianceEvaluationService._create_gap_report(
                session, match, requirement, new_status, reason, failed_quotes,
            )

        logger.info(
            "Compliance evaluation: requirement=%s status=%s citation_verified=%s validity=%s",
            requirement.id, new_status.value, citations_ok, validity.value,
        )

        return status_record

    @staticmethod
    def _create_gap_report(
        session: Session,
        match: EvidenceMatch,
        requirement: Requirement,
        status: ComplianceStatus,
        reason: str,
        failed_quotes: List[str],
    ) -> GapReport:
        """Create a gap report from an evaluation that did not fully satisfy."""
        if status == ComplianceStatus.GAP and not match.supporting_evidence:
            gap_type = GapType.MISSING_EVIDENCE
        elif failed_quotes:
            gap_type = GapType.AMBIGUOUS_EVIDENCE
        else:
            gap_type = GapType.PARTIAL_COVERAGE

        gap = GapReport(
            requirement_id=requirement.id,
            evidence_match_id=match.id,
            gap_type=gap_type,
            description=reason,
            requested_evidence=match.requested_evidence or [],
            priority=requirement.severity,
            status=GapStatus.OPEN,
        )
        session.add(gap)
        session.flush()
        return gap

    @staticmethod
    def refresh_expiration_status(
        session: Session,
        settings: Optional[Settings] = None,
    ) -> int:
        """Scan all evidence and update validity statuses. Returns count of changed records."""
        settings = settings or get_settings()
        documents = session.query(EvidenceDocument).filter(
            EvidenceDocument.expires_at.isnot(None)
        ).all()

        changed = 0
        for doc in documents:
            new_validity = ComplianceEvaluationService.compute_evidence_validity(
                doc, settings
            )
            if doc.validity_status != new_validity:
                doc.validity_status = new_validity
                changed += 1

        if changed:
            session.flush()
        return changed

    @staticmethod
    def get_compliance_status(
        session: Session,
        requirement_id: uuid.UUID,
    ) -> ComplianceStatusRecord:
        """Get the current compliance status for a requirement."""
        record = (
            session.query(ComplianceStatusRecord)
            .filter(ComplianceStatusRecord.requirement_id == requirement_id)
            .first()
        )
        if not record:
            raise EntityNotFoundException(
                f"Compliance status for requirement '{requirement_id}' not found",
                details={"requirement_id": str(requirement_id)},
            )
        return record

    @staticmethod
    def get_status_history(
        session: Session,
        requirement_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[ComplianceStatusHistory], int]:
        """Get paginated compliance status history for a requirement."""
        query = (
            session.query(ComplianceStatusHistory)
            .filter(ComplianceStatusHistory.requirement_id == requirement_id)
            .order_by(ComplianceStatusHistory.recorded_at.desc())
        )
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    @staticmethod
    def get_framework_compliance_summary(
        session: Session,
        framework_id: uuid.UUID,
    ) -> dict:
        """Get aggregated compliance status for all requirements in a framework."""
        from src.database.models import ComplianceFramework

        framework = session.get(ComplianceFramework, framework_id)
        if not framework:
            raise EntityNotFoundException(
                f"Framework '{framework_id}' not found",
                details={"framework_id": str(framework_id)},
            )

        requirements = (
            session.query(Requirement)
            .filter(Requirement.framework_id == framework_id, Requirement.is_active == True)
            .all()
        )

        summary = {
            "framework_id": str(framework_id),
            "framework_name": framework.name,
            "framework_version": framework.version,
            "total_requirements": len(requirements),
            "satisfied": 0,
            "partial": 0,
            "gap": 0,
            "not_evaluated": 0,
        }

        for req in requirements:
            status_record = (
                session.query(ComplianceStatusRecord)
                .filter(ComplianceStatusRecord.requirement_id == req.id)
                .first()
            )
            if not status_record:
                summary["not_evaluated"] += 1
            elif status_record.status == ComplianceStatus.SATISFIED:
                summary["satisfied"] += 1
            elif status_record.status == ComplianceStatus.PARTIAL:
                summary["partial"] += 1
            else:
                summary["gap"] += 1

        total = summary["total_requirements"]
        summary["compliance_percentage"] = (
            round(summary["satisfied"] / total * 100, 1) if total > 0 else 0.0
        )

        return summary
