"""Pydantic schemas for aggregated compliance dashboard."""

from typing import Dict, List, Optional

from pydantic import BaseModel


class SystemOverview(BaseModel):
    """System-wide compliance overview."""

    total_frameworks: int
    total_requirements: int
    satisfied: int
    partial: int
    gap: int
    not_evaluated: int
    compliance_percentage: float
    open_gaps: int
    total_evidence: int
    expiring_evidence: int
    expired_evidence: int


class FrameworkSummaryItem(BaseModel):
    """Per-framework compliance summary."""

    framework_id: str
    framework_name: str
    framework_version: str
    total_requirements: int
    satisfied: int
    partial: int
    gap: int
    not_evaluated: int
    compliance_percentage: float


class RequirementStatusItem(BaseModel):
    """Requirement-level compliance detail within a framework."""

    requirement_id: str
    requirement_code: str
    title: str
    severity: str
    status: str
    status_reason: str
    last_evaluated_at: Optional[str] = None
    open_gaps: int


class FrameworkDetailResponse(BaseModel):
    """Detailed framework view with requirement breakdown."""

    framework_id: str
    framework_name: str
    framework_version: str
    total_requirements: int
    satisfied: int
    partial: int
    gap: int
    not_evaluated: int
    compliance_percentage: float
    requirements: List[RequirementStatusItem]


class GapSummary(BaseModel):
    """Gap report statistics."""

    total: int
    by_status: Dict[str, int]
    by_type: Dict[str, int]
    by_priority: Dict[str, int]


class EvidenceSummary(BaseModel):
    """Evidence document statistics."""

    total: int
    by_validity: Dict[str, int]
    by_processing: Dict[str, int]
