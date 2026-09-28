"""Gap reporting lifecycle service."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from src.core.exceptions import EntityNotFoundException, ValidationException
from src.core.logging import get_logger
from src.database.models import GapReport, Requirement
from src.database.models.enums import GapStatus, GapType, Severity

logger = get_logger("services.gap")


class GapService:
    """Business logic for gap report lifecycle management."""

    @staticmethod
    def get_gap_report(session: Session, gap_id: uuid.UUID) -> GapReport:
        """Get a single gap report by UUID."""
        gap = session.get(GapReport, gap_id)
        if not gap:
            raise EntityNotFoundException(
                f"Gap report '{gap_id}' not found",
                details={"gap_id": str(gap_id)},
            )
        return gap

    @staticmethod
    def list_gap_reports(
        session: Session,
        requirement_id: Optional[uuid.UUID] = None,
        status: Optional[GapStatus] = None,
        gap_type: Optional[GapType] = None,
        priority: Optional[Severity] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[GapReport], int]:
        """List gap reports with optional filters and pagination."""
        query = session.query(GapReport)

        if requirement_id:
            query = query.filter(GapReport.requirement_id == requirement_id)
        if status:
            query = query.filter(GapReport.status == status)
        if gap_type:
            query = query.filter(GapReport.gap_type == gap_type)
        if priority:
            query = query.filter(GapReport.priority == priority)

        query = query.order_by(
            GapReport.priority.desc(),
            GapReport.detected_at.desc(),
        )

        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    @staticmethod
    def update_gap_status(
        session: Session,
        gap_id: uuid.UUID,
        new_status: GapStatus,
        resolution_notes: Optional[str] = None,
    ) -> GapReport:
        """Transition a gap report's status with validation."""
        gap = GapService.get_gap_report(session, gap_id)

        valid_transitions = {
            GapStatus.OPEN: {GapStatus.IN_REVIEW, GapStatus.WAIVED},
            GapStatus.IN_REVIEW: {GapStatus.RESOLVED, GapStatus.OPEN, GapStatus.WAIVED},
            GapStatus.RESOLVED: set(),
            GapStatus.WAIVED: {GapStatus.OPEN},
        }

        allowed = valid_transitions.get(gap.status, set())
        if new_status not in allowed:
            raise ValidationException(
                f"Cannot transition gap from '{gap.status.value}' to '{new_status.value}'",
                details={
                    "gap_id": str(gap_id),
                    "current_status": gap.status.value,
                    "requested_status": new_status.value,
                    "allowed_transitions": [s.value for s in allowed],
                },
            )

        gap.status = new_status

        if resolution_notes is not None:
            gap.resolution_notes = resolution_notes

        if new_status == GapStatus.RESOLVED:
            gap.resolved_at = datetime.now(timezone.utc)

        session.flush()

        logger.info(
            "Gap report %s transitioned to %s",
            gap_id, new_status.value,
        )

        return gap
