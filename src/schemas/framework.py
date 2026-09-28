"""Pydantic schemas for compliance frameworks and requirements."""

from datetime import datetime
from typing import List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from src.database.models.enums import Severity


class FrameworkBase(BaseModel):
    """Base schema for compliance frameworks."""

    name: str = Field(..., min_length=1, max_length=255, description="Framework name (e.g. SOC 2 Type II).")
    version: str = Field(..., min_length=1, max_length=50, description="Framework version or release year.")
    description: Optional[str] = Field(None, description="Detailed description of framework scope.")
    is_active: bool = Field(True, description="Whether the framework is active.")


class FrameworkCreate(FrameworkBase):
    """Schema for registering a new compliance framework."""
    pass


class FrameworkUpdate(BaseModel):
    """Schema for updating an existing compliance framework."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    version: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class FrameworkResponse(FrameworkBase):
    """Response schema for a compliance framework."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    requirement_count: Optional[int] = Field(0, description="Total number of requirements registered.")


class RequirementBase(BaseModel):
    """Base schema for compliance requirements."""

    requirement_code: str = Field(..., min_length=1, max_length=100, description="Control ID (e.g. CC6.1).")
    title: str = Field(..., min_length=1, max_length=255, description="Short title of the control.")
    description: str = Field(..., min_length=1, description="Complete description of the control requirement.")
    severity: Severity = Field(Severity.MEDIUM, description="Risk severity level.")
    is_active: bool = Field(True, description="Whether the requirement is active.")


class RequirementCreate(RequirementBase):
    """Schema for creating a new requirement under a framework."""
    pass


class RequirementUpdate(BaseModel):
    """Schema for updating an existing requirement."""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, min_length=1)
    severity: Optional[Severity] = None
    is_active: Optional[bool] = None


class RequirementResponse(RequirementBase):
    """Response schema for a single requirement."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    framework_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class PaginatedRequirementsResponse(BaseModel):
    """Paginated list of requirements."""

    items: List[RequirementResponse]
    total: int
    page: int
    page_size: int
    pages: int
