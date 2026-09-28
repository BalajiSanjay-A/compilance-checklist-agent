"""Pydantic schemas for AI evidence matching structured output."""

from typing import List, Literal

from pydantic import BaseModel, Field


class EvidenceMatchResult(BaseModel):
    """Structured output from the LLM evidence evaluation."""

    status: Literal["satisfied", "partial", "gap"] = Field(
        description="Overall match status: satisfied, partial, or gap."
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Model confidence (0.0-1.0). Audit metadata only — never used for approval."
    )
    reasoning: str = Field(
        description="Detailed explanation of the evaluation decision."
    )
    supporting_evidence: List[str] = Field(
        default_factory=list,
        description="Verbatim quotes from the evidence that support compliance."
    )
    missing_evidence: List[str] = Field(
        default_factory=list,
        description="Specific controls or documentation that are absent."
    )
    requested_evidence: List[str] = Field(
        default_factory=list,
        description="Specific documents or evidence needed to achieve full compliance."
    )
    expiration_risk: Literal["none", "expiring_soon", "expired"] = Field(
        default="none",
        description="Evidence validity risk assessment."
    )
