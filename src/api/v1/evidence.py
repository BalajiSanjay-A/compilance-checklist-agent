"""API v1 endpoints for evidence document upload and retrieval."""

import math
from datetime import date
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from src.api.dependencies import AuditorDep, ComplianceOfficerDep, SettingsDep
from src.database.models.enums import DocumentType, EvidenceValidity, ProcessingStatus
from src.database.session import get_db, transactional_session
from src.schemas.evidence import (
    EvidenceListItem,
    EvidenceResponse,
    EvidenceUploadResponse,
    PaginatedEvidenceResponse,
)
from src.services.evidence_service import EvidenceService

router = APIRouter(tags=["Evidence"])


@router.post(
    "/evidence/upload",
    response_model=EvidenceUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload evidence document",
    description="Upload a compliance evidence document for processing. Requires compliance-officer role.",
)
def upload_evidence(
    file: UploadFile = File(...),
    document_type: DocumentType = Form(DocumentType.OTHER),
    valid_from: Optional[date] = Form(None),
    expires_at: Optional[date] = Form(None),
    user: ComplianceOfficerDep = None,
    db: Session = Depends(get_db),
    settings: SettingsDep = None,
) -> EvidenceUploadResponse:
    content = file.file.read()

    with transactional_session(db):
        evidence = EvidenceService.upload_evidence(
            session=db,
            file_content=content,
            filename=file.filename or "unnamed",
            content_type=file.content_type or "application/octet-stream",
            document_type=document_type,
            uploaded_by=user.user_id if user else None,
            valid_from=valid_from,
            expires_at=expires_at,
            settings=settings,
        )
        return EvidenceUploadResponse.model_validate(evidence)


@router.get(
    "/evidence/{id}",
    response_model=EvidenceResponse,
    summary="Get evidence document metadata",
    description="Retrieve full metadata for an evidence document by UUID.",
)
def get_evidence(
    id: uuid.UUID,
    _user: AuditorDep = None,
    db: Session = Depends(get_db),
) -> EvidenceResponse:
    doc = EvidenceService.get_evidence(db, id)
    resp = EvidenceResponse.model_validate(doc)
    resp.has_content = doc.content_text is not None
    return resp


@router.get(
    "/evidence",
    response_model=PaginatedEvidenceResponse,
    summary="List evidence documents",
    description="Retrieve paginated list of evidence documents with optional filters.",
)
def list_evidence(
    document_type: Optional[DocumentType] = Query(None, description="Filter by document type"),
    validity_status: Optional[EvidenceValidity] = Query(None, description="Filter by validity status"),
    processing_status: Optional[ProcessingStatus] = Query(None, description="Filter by processing status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    _user: AuditorDep = None,
    db: Session = Depends(get_db),
) -> PaginatedEvidenceResponse:
    items, total = EvidenceService.list_evidence(
        db,
        document_type=document_type,
        validity_status=validity_status,
        processing_status=processing_status,
        page=page,
        page_size=page_size,
    )
    pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginatedEvidenceResponse(
        items=[EvidenceListItem.model_validate(doc) for doc in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )
