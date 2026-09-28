"""API v1 endpoints for compliance frameworks and requirements."""

import math
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from src.api.dependencies import AuditorDep, ComplianceOfficerDep
from src.database.models.enums import Severity
from src.database.session import get_db, transactional_session
from src.schemas.framework import (
    FrameworkCreate,
    FrameworkResponse,
    FrameworkUpdate,
    PaginatedRequirementsResponse,
    RequirementCreate,
    RequirementResponse,
    RequirementUpdate,
)
from src.services.framework_service import FrameworkService

router = APIRouter(tags=["Frameworks & Requirements"])


@router.get(
    "/frameworks",
    response_model=List[FrameworkResponse],
    summary="List compliance frameworks",
    description="Retrieve list of all compliance frameworks, optionally filtered by active status.",
)
def list_frameworks(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    _user: AuditorDep = None,
    db: Session = Depends(get_db),
) -> List[FrameworkResponse]:
    frameworks_with_counts = FrameworkService.list_frameworks(db, is_active=is_active)
    results = []
    for fw, count in frameworks_with_counts:
        item = FrameworkResponse.model_validate(fw)
        item.requirement_count = count
        results.append(item)
    return results


@router.post(
    "/frameworks",
    response_model=FrameworkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a compliance framework",
    description="Register a new compliance framework. Requires compliance-officer role.",
)
def create_framework(
    data: FrameworkCreate,
    _user: ComplianceOfficerDep = None,
    db: Session = Depends(get_db),
) -> FrameworkResponse:
    with transactional_session(db):
        framework = FrameworkService.create_framework(db, data)
        item = FrameworkResponse.model_validate(framework)
        item.requirement_count = 0
        return item


@router.get(
    "/frameworks/{id}",
    response_model=FrameworkResponse,
    summary="Get framework details",
    description="Retrieve details of a single compliance framework by its UUID.",
)
def get_framework(
    id: uuid.UUID,
    _user: AuditorDep = None,
    db: Session = Depends(get_db),
) -> FrameworkResponse:
    framework, count = FrameworkService.get_framework(db, id)
    item = FrameworkResponse.model_validate(framework)
    item.requirement_count = count
    return item


@router.patch(
    "/frameworks/{id}",
    response_model=FrameworkResponse,
    summary="Update framework",
    description="Update metadata for an existing compliance framework. Requires compliance-officer role.",
)
def update_framework(
    id: uuid.UUID,
    data: FrameworkUpdate,
    _user: ComplianceOfficerDep = None,
    db: Session = Depends(get_db),
) -> FrameworkResponse:
    with transactional_session(db):
        framework = FrameworkService.update_framework(db, id, data)
        _, count = FrameworkService.get_framework(db, id)
        item = FrameworkResponse.model_validate(framework)
        item.requirement_count = count
        return item


@router.get(
    "/frameworks/{id}/requirements",
    response_model=PaginatedRequirementsResponse,
    summary="List requirements for framework",
    description="Retrieve paginated requirements under a framework, with optional active and severity filters.",
)
def list_requirements(
    id: uuid.UUID,
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    severity: Optional[Severity] = Query(None, description="Filter by risk severity"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    _user: AuditorDep = None,
    db: Session = Depends(get_db),
) -> PaginatedRequirementsResponse:
    items, total = FrameworkService.list_requirements(
        db,
        framework_id=id,
        is_active=is_active,
        severity=severity,
        page=page,
        page_size=page_size,
    )
    pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginatedRequirementsResponse(
        items=[RequirementResponse.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post(
    "/frameworks/{id}/requirements",
    response_model=RequirementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add requirement to framework",
    description="Add a new requirement to a framework and initialize baseline GAP status. Requires compliance-officer role.",
)
def create_requirement(
    id: uuid.UUID,
    data: RequirementCreate,
    _user: ComplianceOfficerDep = None,
    db: Session = Depends(get_db),
) -> RequirementResponse:
    with transactional_session(db):
        requirement = FrameworkService.create_requirement(db, framework_id=id, data=data)
        return RequirementResponse.model_validate(requirement)


@router.get(
    "/requirements/{id}",
    response_model=RequirementResponse,
    summary="Get requirement details",
    description="Retrieve a single compliance requirement by its UUID.",
)
def get_requirement(
    id: uuid.UUID,
    _user: AuditorDep = None,
    db: Session = Depends(get_db),
) -> RequirementResponse:
    requirement = FrameworkService.get_requirement(db, id)
    return RequirementResponse.model_validate(requirement)


@router.patch(
    "/requirements/{id}",
    response_model=RequirementResponse,
    summary="Update requirement",
    description="Update requirement fields. Requires compliance-officer role.",
)
def update_requirement(
    id: uuid.UUID,
    data: RequirementUpdate,
    _user: ComplianceOfficerDep = None,
    db: Session = Depends(get_db),
) -> RequirementResponse:
    with transactional_session(db):
        requirement = FrameworkService.update_requirement(db, id, data)
        return RequirementResponse.model_validate(requirement)
