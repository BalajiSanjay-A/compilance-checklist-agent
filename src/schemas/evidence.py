"""Pydantic schemas for evidence document upload and retrieval."""

from datetime import date, datetime
from typing import List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from src.database.models.enums import DocumentType, EvidenceValidity, ProcessingStatus


class EvidenceUploadResponse(BaseModel):
    """Response after successful evidence upload."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    document_type: DocumentType
    file_hash: str
    file_size_bytes: int
    uploaded_by: Optional[uuid.UUID] = None
    uploaded_at: datetime
    valid_from: Optional[date] = None
    expires_at: Optional[date] = None
    validity_status: EvidenceValidity
    processing_status: ProcessingStatus
    created_at: datetime
    updated_at: datetime


class EvidenceResponse(EvidenceUploadResponse):
    """Full evidence detail including content text and processing info."""

    content_text: Optional[str] = None
    has_content: bool = Field(False, description="Whether extracted text content is available.")
    processing_error: Optional[str] = None


class EvidenceListItem(BaseModel):
    """Lightweight evidence item for list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    document_type: DocumentType
    file_size_bytes: int
    file_hash: str
    uploaded_at: datetime
    valid_from: Optional[date] = None
    expires_at: Optional[date] = None
    validity_status: EvidenceValidity
    processing_status: ProcessingStatus


class PaginatedEvidenceResponse(BaseModel):
    """Paginated list of evidence documents."""

    items: List[EvidenceListItem]
    total: int
    page: int
    page_size: int
    pages: int
