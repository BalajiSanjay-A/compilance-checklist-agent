"""Pydantic schemas for evidence matching API requests and responses."""

from datetime import datetime
from typing import List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from src.database.models.enums import ComplianceStatus


class EvaluateEvidenceRequest(BaseModel):
    """Request to evaluate evidence against a requirement."""

    evidence_id: uuid.UUID = Field(..., description="UUID of the uploaded evidence document.")
    requirement_id: uuid.UUID = Field(..., description="UUID of the compliance requirement.")


class EvidenceMatchResponse(BaseModel):
    """Response containing the result of an evidence evaluation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    evidence_id: uuid.UUID
    requirement_id: uuid.UUID
    status: ComplianceStatus
    confidence: float = Field(description="Model confidence (audit metadata only).")
    reasoning: str
    supporting_evidence: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    requested_evidence: List[str] = Field(default_factory=list)
    citation_verified: bool = Field(False, description="Whether citations have been deterministically verified.")
    model_name: str
    prompt_version: str
    evaluated_at: datetime
    created_at: datetime
    updated_at: datetime


class EvidenceMatchListItem(BaseModel):
    """Lightweight match item for listing."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    evidence_id: uuid.UUID
    requirement_id: uuid.UUID
    status: ComplianceStatus
    confidence: float
    citation_verified: bool
    model_name: str
    evaluated_at: datetime


class PaginatedMatchesResponse(BaseModel):
    """Paginated list of evidence match results."""

    items: List[EvidenceMatchListItem]
    total: int
    page: int
    page_size: int
    pages: int
