"""Aggregated compliance dashboard service."""

import uuid
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from src.core.exceptions import EntityNotFoundException
from src.core.logging import get_logger
from src.database.models import (
    ComplianceFramework,
    ComplianceStatus,
    ComplianceStatusRecord,
    EvidenceDocument,
    EvidenceValidity,
    GapReport,
    Requirement,
)
from src.database.models.enums import GapStatus, GapType, Severity

logger = get_logger("services.dashboard")


class DashboardService:
    """Aggregated compliance dashboard queries."""

    @staticmethod
    def get_system_overview(session: Session) -> dict:
        """System-wide compliance overview across all active frameworks."""
        frameworks = (
            session.query(ComplianceFramework)
            .filter(ComplianceFramework.is_active == True)
            .all()
        )

        total_requirements = 0
        satisfied = 0
        partial = 0
        gap = 0
        not_evaluated = 0

        for fw in frameworks:
            reqs = (
                session.query(Requirement)
                .filter(Requirement.framework_id == fw.id, Requirement.is_active == True)
                .all()
            )
            total_requirements += len(reqs)

            for req in reqs:
                record = (
                    session.query(ComplianceStatusRecord)
                    .filter(ComplianceStatusRecord.requirement_id == req.id)
                    .first()
                )
                if not record:
                    not_evaluated += 1
                elif record.status == ComplianceStatus.SATISFIED:
                    satisfied += 1
                elif record.status == ComplianceStatus.PARTIAL:
                    partial += 1
                else:
                    gap += 1

        compliance_pct = (
            round(satisfied / total_requirements * 100, 1)
            if total_requirements > 0
            else 0.0
        )

        open_gaps = session.query(GapReport).filter(
            GapReport.status.in_([GapStatus.OPEN, GapStatus.IN_REVIEW])
        ).count()

        total_evidence = session.query(EvidenceDocument).count()
        expiring_evidence = session.query(EvidenceDocument).filter(
            EvidenceDocument.validity_status == EvidenceValidity.EXPIRING_SOON
        ).count()
        expired_evidence = session.query(EvidenceDocument).filter(
            EvidenceDocument.validity_status == EvidenceValidity.EXPIRED
        ).count()

        return {
            "total_frameworks": len(frameworks),
            "total_requirements": total_requirements,
            "satisfied": satisfied,
            "partial": partial,
            "gap": gap,
            "not_evaluated": not_evaluated,
            "compliance_percentage": compliance_pct,
            "open_gaps": open_gaps,
            "total_evidence": total_evidence,
            "expiring_evidence": expiring_evidence,
            "expired_evidence": expired_evidence,
        }

    @staticmethod
    def get_all_frameworks_summary(session: Session) -> List[dict]:
        """Compliance summary for every active framework."""
        frameworks = (
            session.query(ComplianceFramework)
            .filter(ComplianceFramework.is_active == True)
            .order_by(ComplianceFramework.name)
            .all()
        )

        results = []
        for fw in frameworks:
            reqs = (
                session.query(Requirement)
                .filter(Requirement.framework_id == fw.id, Requirement.is_active == True)
                .all()
            )
            counts = {"satisfied": 0, "partial": 0, "gap": 0, "not_evaluated": 0}
            for req in reqs:
                record = (
                    session.query(ComplianceStatusRecord)
                    .filter(ComplianceStatusRecord.requirement_id == req.id)
                    .first()
                )
                if not record:
                    counts["not_evaluated"] += 1
                elif record.status == ComplianceStatus.SATISFIED:
                    counts["satisfied"] += 1
                elif record.status == ComplianceStatus.PARTIAL:
                    counts["partial"] += 1
                else:
                    counts["gap"] += 1

            total = len(reqs)
            results.append({
                "framework_id": str(fw.id),
                "framework_name": fw.name,
                "framework_version": fw.version,
                "total_requirements": total,
                **counts,
                "compliance_percentage": (
                    round(counts["satisfied"] / total * 100, 1) if total > 0 else 0.0
                ),
            })

        return results

    @staticmethod
    def get_framework_detail(
        session: Session,
        framework_id: uuid.UUID,
    ) -> dict:
        """Detailed framework view with per-requirement compliance breakdown."""
        framework = session.get(ComplianceFramework, framework_id)
        if not framework:
            raise EntityNotFoundException(
                f"Framework '{framework_id}' not found",
                details={"framework_id": str(framework_id)},
            )

        reqs = (
            session.query(Requirement)
            .filter(Requirement.framework_id == framework_id, Requirement.is_active == True)
            .order_by(Requirement.requirement_code)
            .all()
        )

        requirement_details = []
        counts = {"satisfied": 0, "partial": 0, "gap": 0, "not_evaluated": 0}

        for req in reqs:
            record = (
                session.query(ComplianceStatusRecord)
                .filter(ComplianceStatusRecord.requirement_id == req.id)
                .first()
            )
            status_val = record.status.value if record else "NOT_EVALUATED"
            reason = record.status_reason if record else "Awaiting evidence evaluation."
            last_eval = record.last_evaluated_at if record else None

            if not record:
                counts["not_evaluated"] += 1
            elif record.status == ComplianceStatus.SATISFIED:
                counts["satisfied"] += 1
            elif record.status == ComplianceStatus.PARTIAL:
                counts["partial"] += 1
            else:
                counts["gap"] += 1

            gap_count = session.query(GapReport).filter(
                GapReport.requirement_id == req.id,
                GapReport.status.in_([GapStatus.OPEN, GapStatus.IN_REVIEW]),
            ).count()

            requirement_details.append({
                "requirement_id": str(req.id),
                "requirement_code": req.requirement_code,
                "title": req.title,
                "severity": req.severity.value,
                "status": status_val,
                "status_reason": reason,
                "last_evaluated_at": last_eval.isoformat() if last_eval else None,
                "open_gaps": gap_count,
            })

        total = len(reqs)
        return {
            "framework_id": str(framework_id),
            "framework_name": framework.name,
            "framework_version": framework.version,
            "total_requirements": total,
            **counts,
            "compliance_percentage": (
                round(counts["satisfied"] / total * 100, 1) if total > 0 else 0.0
            ),
            "requirements": requirement_details,
        }

    @staticmethod
    def get_gap_summary(session: Session) -> dict:
        """Gap report statistics by status, type, and priority."""
        by_status = {}
        for gs in GapStatus:
            by_status[gs.value] = session.query(GapReport).filter(
                GapReport.status == gs
            ).count()

        by_type = {}
        for gt in GapType:
            by_type[gt.value] = session.query(GapReport).filter(
                GapReport.gap_type == gt
            ).count()

        by_priority = {}
        for sev in Severity:
            by_priority[sev.value] = session.query(GapReport).filter(
                GapReport.priority == sev
            ).count()

        return {
            "total": session.query(GapReport).count(),
            "by_status": by_status,
            "by_type": by_type,
            "by_priority": by_priority,
        }

    @staticmethod
    def get_evidence_summary(session: Session) -> dict:
        """Evidence document statistics by validity and processing status."""
        from src.database.models.enums import ProcessingStatus

        by_validity = {}
        for ev in EvidenceValidity:
            by_validity[ev.value] = session.query(EvidenceDocument).filter(
                EvidenceDocument.validity_status == ev
            ).count()

        by_processing = {}
        for ps in ProcessingStatus:
            by_processing[ps.value] = session.query(EvidenceDocument).filter(
                EvidenceDocument.processing_status == ps
            ).count()

        return {
            "total": session.query(EvidenceDocument).count(),
            "by_validity": by_validity,
            "by_processing": by_processing,
        }
