"""Aggregated compliance dashboard API endpoints."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.dependencies import AuditorDep
from src.database.session import get_db
from src.schemas.dashboard import (
    EvidenceSummary,
    FrameworkDetailResponse,
    FrameworkSummaryItem,
    GapSummary,
    SystemOverview,
)
from src.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "/overview",
    response_model=SystemOverview,
    summary="System-wide compliance overview",
)
def get_system_overview(
    _user: AuditorDep = None,
    db: Session = Depends(get_db),
) -> SystemOverview:
    data = DashboardService.get_system_overview(db)
    return SystemOverview(**data)


@router.get(
    "/frameworks",
    response_model=list[FrameworkSummaryItem],
    summary="All frameworks compliance summary",
)
def get_all_frameworks_summary(
    _user: AuditorDep = None,
    db: Session = Depends(get_db),
) -> list[FrameworkSummaryItem]:
    items = DashboardService.get_all_frameworks_summary(db)
    return [FrameworkSummaryItem(**item) for item in items]


@router.get(
    "/frameworks/{framework_id}",
    response_model=FrameworkDetailResponse,
    summary="Detailed framework compliance with requirement breakdown",
)
def get_framework_detail(
    framework_id: uuid.UUID,
    _user: AuditorDep = None,
    db: Session = Depends(get_db),
) -> FrameworkDetailResponse:
    data = DashboardService.get_framework_detail(db, framework_id)
    return FrameworkDetailResponse(**data)


@router.get(
    "/gaps",
    response_model=GapSummary,
    summary="Gap report statistics",
)
def get_gap_summary(
    _user: AuditorDep = None,
    db: Session = Depends(get_db),
) -> GapSummary:
    data = DashboardService.get_gap_summary(db)
    return GapSummary(**data)


@router.get(
    "/evidence",
    response_model=EvidenceSummary,
    summary="Evidence document statistics",
)
def get_evidence_summary(
    _user: AuditorDep = None,
    db: Session = Depends(get_db),
) -> EvidenceSummary:
    data = DashboardService.get_evidence_summary(db)
    return EvidenceSummary(**data)
