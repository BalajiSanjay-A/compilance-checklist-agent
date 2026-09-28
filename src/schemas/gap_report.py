"""Pydantic schemas for gap report endpoints."""

from datetime import datetime
from typing import Any, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from src.database.models.enums import GapStatus, GapType, Severity


class GapReportResponse(BaseModel):
    """Full gap report details."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requirement_id: uuid.UUID
    evidence_match_id: Optional[uuid.UUID] = None
    gap_type: GapType
    description: str
    requested_evidence: List[Any] = Field(default_factory=list)
    priority: Severity
    status: GapStatus
    detected_at: datetime
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class GapReportListItem(BaseModel):
    """Lightweight gap report for list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requirement_id: uuid.UUID
    gap_type: GapType
    description: str
    priority: Severity
    status: GapStatus
    detected_at: datetime
    resolved_at: Optional[datetime] = None


class PaginatedGapReportsResponse(BaseModel):
    """Paginated list of gap reports."""

    items: List[GapReportListItem]
    total: int
    page: int
    page_size: int
    pages: int


class GapStatusUpdateRequest(BaseModel):
    """Request to update gap report status."""

    status: GapStatus = Field(..., description="New gap status.")
    resolution_notes: Optional[str] = Field(None, description="Notes about the resolution or status change.")
