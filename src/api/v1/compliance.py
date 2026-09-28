"""API v1 endpoints for compliance evaluation, status, and history."""

import math
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from src.ai.matching_service import EvidenceMatchingAgent, get_llm_service
from src.api.dependencies import AuditorDep, ComplianceOfficerDep, SettingsDep
from src.database.session import get_db, transactional_session
from src.schemas.compliance import (
    ComplianceHistoryItem,
    ComplianceStatusResponse,
    EvaluateAndResolveRequest,
    FrameworkComplianceSummary,
    PaginatedHistoryResponse,
)
from src.schemas.matching import EvidenceMatchResponse
from src.services.compliance_service import ComplianceEvaluationService

router = APIRouter(tags=["Compliance"])


@router.post(
    "/compliance/evaluate-and-resolve",
    response_model=ComplianceStatusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Evaluate evidence and resolve compliance status",
    description="Run the full pipeline: AI matching → citation verification → "
    "compliance status resolution → gap report generation. "
    "Requires compliance-officer role.",
)
def evaluate_and_resolve(
    data: EvaluateAndResolveRequest,
    user: ComplianceOfficerDep = None,
    db: Session = Depends(get_db),
    settings: SettingsDep = None,
) -> ComplianceStatusResponse:
    llm = get_llm_service(settings)
    agent = EvidenceMatchingAgent(llm_service=llm, settings=settings)

    with transactional_session(db):
        match = agent.match_evidence_to_requirement(
            session=db,
            evidence_id=data.evidence_id,
            requirement_id=data.requirement_id,
        )

        status_record = ComplianceEvaluationService.evaluate_match(
            session=db,
            match_id=match.id,
            settings=settings,
        )
        return ComplianceStatusResponse.model_validate(status_record)


@router.get(
    "/compliance/{framework_id}/status",
    response_model=FrameworkComplianceSummary,
    summary="Get framework compliance scorecard",
    description="Aggregated compliance status for all active requirements in a framework.",
)
def get_framework_compliance_status(
    framework_id: uuid.UUID,
    _user: AuditorDep = None,
    db: Session = Depends(get_db),
) -> FrameworkComplianceSummary:
    summary = ComplianceEvaluationService.get_framework_compliance_summary(
        db, framework_id
    )
    return FrameworkComplianceSummary(**summary)


@router.get(
    "/compliance/requirements/{requirement_id}/status",
    response_model=ComplianceStatusResponse,
    summary="Get requirement compliance status",
    description="Retrieve current compliance status for a specific requirement.",
)
def get_requirement_compliance_status(
    requirement_id: uuid.UUID,
    _user: AuditorDep = None,
    db: Session = Depends(get_db),
) -> ComplianceStatusResponse:
    record = ComplianceEvaluationService.get_compliance_status(db, requirement_id)
    return ComplianceStatusResponse.model_validate(record)


@router.get(
    "/compliance/requirements/{requirement_id}/history",
    response_model=PaginatedHistoryResponse,
    summary="Get compliance status history",
    description="Full audit trail of compliance status transitions for a requirement.",
)
def get_compliance_history(
    requirement_id: uuid.UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    _user: AuditorDep = None,
    db: Session = Depends(get_db),
) -> PaginatedHistoryResponse:
    items, total = ComplianceEvaluationService.get_status_history(
        db, requirement_id, page=page, page_size=page_size
    )
    pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginatedHistoryResponse(
        items=[ComplianceHistoryItem.model_validate(h) for h in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post(
    "/compliance/refresh-expiration",
    summary="Refresh evidence expiration statuses",
    description="Scan all evidence and update validity statuses based on current date. "
    "Requires compliance-officer role.",
)
def refresh_expiration(
    _user: ComplianceOfficerDep = None,
    db: Session = Depends(get_db),
    settings: SettingsDep = None,
) -> dict:
    with transactional_session(db):
        changed = ComplianceEvaluationService.refresh_expiration_status(db, settings)
    return {"updated_count": changed}
