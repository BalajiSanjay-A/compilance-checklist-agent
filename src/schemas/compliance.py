"""Pydantic schemas for compliance status and evaluation endpoints."""

from datetime import date, datetime
from typing import List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from src.database.models.enums import ComplianceStatus


class ComplianceStatusResponse(BaseModel):
    """Current compliance status for a requirement."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requirement_id: uuid.UUID
    current_match_id: Optional[uuid.UUID] = None
    status: ComplianceStatus
    status_reason: str
    effective_from: Optional[date] = None
    effective_until: Optional[date] = None
    last_evaluated_at: Optional[datetime] = None
    next_review_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ComplianceHistoryItem(BaseModel):
    """Single compliance status transition record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requirement_id: uuid.UUID
    previous_status: Optional[ComplianceStatus] = None
    new_status: ComplianceStatus
    evidence_match_id: Optional[uuid.UUID] = None
    changed_by: str
    change_reason: str
    recorded_at: datetime


class PaginatedHistoryResponse(BaseModel):
    """Paginated list of compliance status history."""

    items: List[ComplianceHistoryItem]
    total: int
    page: int
    page_size: int
    pages: int


class FrameworkComplianceSummary(BaseModel):
    """Aggregated compliance scorecard for a framework."""

    framework_id: str
    framework_name: str
    framework_version: str
    total_requirements: int
    satisfied: int
    partial: int
    gap: int
    not_evaluated: int
    compliance_percentage: float


class EvaluateAndResolveRequest(BaseModel):
    """Request to evaluate evidence and run the full compliance resolution pipeline."""

    evidence_id: uuid.UUID = Field(..., description="UUID of the uploaded evidence document.")
    requirement_id: uuid.UUID = Field(..., description="UUID of the compliance requirement.")
