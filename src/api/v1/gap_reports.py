"""API v1 endpoints for gap report lifecycle management."""

import math
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from src.api.dependencies import AuditorDep, ComplianceOfficerDep
from src.database.models.enums import GapStatus, GapType, Severity
from src.database.session import get_db, transactional_session
from src.schemas.gap_report import (
    GapReportListItem,
    GapReportResponse,
    GapStatusUpdateRequest,
    PaginatedGapReportsResponse,
)
from src.services.gap_service import GapService

router = APIRouter(tags=["Gap Reports"])


@router.get(
    "/gap-reports",
    response_model=PaginatedGapReportsResponse,
    summary="List gap reports",
    description="Retrieve paginated gap reports with optional filters by status, type, priority, and requirement.",
)
def list_gap_reports(
    requirement_id: Optional[uuid.UUID] = Query(None, description="Filter by requirement UUID"),
    gap_status: Optional[GapStatus] = Query(None, alias="status", description="Filter by gap status"),
    gap_type: Optional[GapType] = Query(None, description="Filter by gap type"),
    priority: Optional[Severity] = Query(None, description="Filter by priority"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    _user: AuditorDep = None,
    db: Session = Depends(get_db),
) -> PaginatedGapReportsResponse:
    items, total = GapService.list_gap_reports(
        db,
        requirement_id=requirement_id,
        status=gap_status,
        gap_type=gap_type,
        priority=priority,
        page=page,
        page_size=page_size,
    )
    pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginatedGapReportsResponse(
        items=[GapReportListItem.model_validate(g) for g in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/gap-reports/{gap_id}",
    response_model=GapReportResponse,
    summary="Get gap report details",
    description="Retrieve full details of a gap report by UUID.",
)
def get_gap_report(
    gap_id: uuid.UUID,
    _user: AuditorDep = None,
    db: Session = Depends(get_db),
) -> GapReportResponse:
    gap = GapService.get_gap_report(db, gap_id)
    return GapReportResponse.model_validate(gap)


@router.patch(
    "/gap-reports/{gap_id}",
    response_model=GapReportResponse,
    summary="Update gap report status",
    description="Transition a gap report's status (OPEN → IN_REVIEW → RESOLVED, or WAIVE). "
    "Requires compliance-officer role.",
)
def update_gap_report(
    gap_id: uuid.UUID,
    data: GapStatusUpdateRequest,
    _user: ComplianceOfficerDep = None,
    db: Session = Depends(get_db),
) -> GapReportResponse:
    with transactional_session(db):
        gap = GapService.update_gap_status(
            db,
            gap_id=gap_id,
            new_status=data.status,
            resolution_notes=data.resolution_notes,
        )
        return GapReportResponse.model_validate(gap)
