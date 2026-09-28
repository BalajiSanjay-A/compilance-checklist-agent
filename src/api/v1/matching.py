"""API v1 endpoints for AI evidence matching and evaluation."""

import math
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from src.ai.matching_service import EvidenceMatchingAgent, get_llm_service
from src.api.dependencies import AuditorDep, ComplianceOfficerDep, SettingsDep
from src.config import get_settings
from src.core.exceptions import EntityNotFoundException
from src.database.models import EvidenceMatch
from src.database.session import get_db, transactional_session
from src.schemas.matching import (
    EvaluateEvidenceRequest,
    EvidenceMatchListItem,
    EvidenceMatchResponse,
    PaginatedMatchesResponse,
)

router = APIRouter(tags=["Compliance Evaluation"])


@router.post(
    "/compliance/evaluate",
    response_model=EvidenceMatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Evaluate evidence against a requirement",
    description="Trigger AI matching of an evidence document against a compliance requirement. "
    "Returns the structured match result. Requires compliance-officer role.",
)
def evaluate_evidence(
    data: EvaluateEvidenceRequest,
    user: ComplianceOfficerDep = None,
    db: Session = Depends(get_db),
    settings: SettingsDep = None,
) -> EvidenceMatchResponse:
    llm = get_llm_service(settings)
    agent = EvidenceMatchingAgent(llm_service=llm, settings=settings)

    with transactional_session(db):
        match = agent.match_evidence_to_requirement(
            session=db,
            evidence_id=data.evidence_id,
            requirement_id=data.requirement_id,
        )
        return EvidenceMatchResponse.model_validate(match)


@router.get(
    "/compliance/matches/{match_id}",
    response_model=EvidenceMatchResponse,
    summary="Get match result details",
    description="Retrieve full details of an evidence match evaluation by UUID.",
)
def get_match(
    match_id: uuid.UUID,
    _user: AuditorDep = None,
    db: Session = Depends(get_db),
) -> EvidenceMatchResponse:
    match = db.get(EvidenceMatch, match_id)
    if not match:
        raise EntityNotFoundException(
            f"Evidence match '{match_id}' not found",
            details={"match_id": str(match_id)},
        )
    return EvidenceMatchResponse.model_validate(match)


@router.get(
    "/compliance/requirements/{requirement_id}/matches",
    response_model=PaginatedMatchesResponse,
    summary="List match evaluations for a requirement",
    description="Retrieve paginated list of all evidence match evaluations for a specific requirement.",
)
def list_requirement_matches(
    requirement_id: uuid.UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    _user: AuditorDep = None,
    db: Session = Depends(get_db),
) -> PaginatedMatchesResponse:
    query = (
        db.query(EvidenceMatch)
        .filter(EvidenceMatch.requirement_id == requirement_id)
        .order_by(EvidenceMatch.evaluated_at.desc())
    )
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginatedMatchesResponse(
        items=[EvidenceMatchListItem.model_validate(m) for m in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )
