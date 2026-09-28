"""Framework and requirement management business logic service."""

import math
from typing import List, Optional, Tuple
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.exceptions import DuplicateEntityException, EntityNotFoundException
from src.core.logging import get_logger
from src.database.models import (
    ComplianceFramework,
    ComplianceStatus,
    ComplianceStatusRecord,
    Requirement,
    Severity,
)
from src.schemas.framework import (
    FrameworkCreate,
    FrameworkUpdate,
    RequirementCreate,
    RequirementUpdate,
)

logger = get_logger("service.framework")


class FrameworkService:
    """Service handling framework and requirement lifecycle and queries."""

    @staticmethod
    def list_frameworks(
        session: Session,
        is_active: Optional[bool] = None,
    ) -> List[Tuple[ComplianceFramework, int]]:
        """
        List compliance frameworks with requirement counts, optionally filtered by active state.
        """
        # Count requirements per framework
        req_count_subq = (
            select(
                Requirement.framework_id,
                func.count(Requirement.id).label("req_count"),
            )
            .group_by(Requirement.framework_id)
            .subquery()
        )

        stmt = (
            select(
                ComplianceFramework,
                func.coalesce(req_count_subq.c.req_count, 0).label("requirement_count"),
            )
            .outerjoin(req_count_subq, ComplianceFramework.id == req_count_subq.c.framework_id)
            .order_by(ComplianceFramework.name, ComplianceFramework.version)
        )

        if is_active is not None:
            stmt = stmt.where(ComplianceFramework.is_active == is_active)

        results = session.execute(stmt).all()
        return [(row[0], row[1]) for row in results]

    @staticmethod
    def get_framework(session: Session, framework_id: uuid.UUID) -> Tuple[ComplianceFramework, int]:
        """Retrieve single framework by ID with requirement count."""
        req_count_stmt = select(func.count(Requirement.id)).where(Requirement.framework_id == framework_id)
        req_count = session.scalar(req_count_stmt) or 0

        framework = session.get(ComplianceFramework, framework_id)
        if not framework:
            raise EntityNotFoundException(
                f"Compliance framework with ID '{framework_id}' not found.",
                details={"framework_id": str(framework_id)},
            )
        return framework, req_count

    @staticmethod
    def create_framework(session: Session, data: FrameworkCreate) -> ComplianceFramework:
        """Register a new compliance framework enforcing unique (name, version)."""
        # Pre-check for duplicate
        existing = session.scalars(
            select(ComplianceFramework).where(
                ComplianceFramework.name == data.name,
                ComplianceFramework.version == data.version,
            )
        ).first()

        if existing:
            raise DuplicateEntityException(
                f"Framework '{data.name}' with version '{data.version}' already exists.",
                details={"name": data.name, "version": data.version},
            )

        framework = ComplianceFramework(
            name=data.name,
            version=data.version,
            description=data.description,
            is_active=data.is_active,
        )
        session.add(framework)
        try:
            session.flush()
        except IntegrityError as exc:
            session.rollback()
            raise DuplicateEntityException(
                f"Framework '{data.name}' version '{data.version}' violates uniqueness constraint.",
                details={"error": str(exc)},
            )

        logger.info("Created framework: %s (v%s) [%s]", framework.name, framework.version, framework.id)
        return framework

    @staticmethod
    def update_framework(
        session: Session,
        framework_id: uuid.UUID,
        data: FrameworkUpdate,
    ) -> ComplianceFramework:
        """Update existing framework metadata."""
        framework, _ = FrameworkService.get_framework(session, framework_id)

        update_dict = data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(framework, key, value)

        try:
            session.flush()
        except IntegrityError as exc:
            session.rollback()
            raise DuplicateEntityException(
                f"Update violates uniqueness constraints for framework '{framework_id}'.",
                details={"error": str(exc)},
            )

        logger.info("Updated framework [%s]", framework.id)
        return framework

    @staticmethod
    def list_requirements(
        session: Session,
        framework_id: uuid.UUID,
        is_active: Optional[bool] = None,
        severity: Optional[Severity] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Requirement], int]:
        """
        List paginated requirements for a given framework with optional filtering.
        """
        # Verify framework exists first
        FrameworkService.get_framework(session, framework_id)

        base_stmt = select(Requirement).where(Requirement.framework_id == framework_id)

        if is_active is not None:
            base_stmt = base_stmt.where(Requirement.is_active == is_active)
        if severity is not None:
            base_stmt = base_stmt.where(Requirement.severity == severity)

        # Count total
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = session.scalar(count_stmt) or 0

        # Paginate
        offset = (page - 1) * page_size
        paginated_stmt = (
            base_stmt.order_by(Requirement.requirement_code)
            .offset(offset)
            .limit(page_size)
        )
        items = list(session.scalars(paginated_stmt).all())
        return items, total

    @staticmethod
    def get_requirement(session: Session, requirement_id: uuid.UUID) -> Requirement:
        """Retrieve single requirement by ID."""
        requirement = session.get(Requirement, requirement_id)
        if not requirement:
            raise EntityNotFoundException(
                f"Requirement with ID '{requirement_id}' not found.",
                details={"requirement_id": str(requirement_id)},
            )
        return requirement

    @staticmethod
    def create_requirement(
        session: Session,
        framework_id: uuid.UUID,
        data: RequirementCreate,
    ) -> Requirement:
        """
        Add a requirement to a framework and automatically initialize baseline GAP status.
        """
        # Ensure framework exists
        FrameworkService.get_framework(session, framework_id)

        # Check for duplicate code under this framework
        existing = session.scalars(
            select(Requirement).where(
                Requirement.framework_id == framework_id,
                Requirement.requirement_code == data.requirement_code,
            )
        ).first()

        if existing:
            raise DuplicateEntityException(
                f"Requirement code '{data.requirement_code}' already exists under framework '{framework_id}'.",
                details={"framework_id": str(framework_id), "requirement_code": data.requirement_code},
            )

        requirement = Requirement(
            framework_id=framework_id,
            requirement_code=data.requirement_code,
            title=data.title,
            description=data.description,
            severity=data.severity,
            is_active=data.is_active,
        )
        session.add(requirement)
        try:
            session.flush()
        except IntegrityError as exc:
            session.rollback()
            raise DuplicateEntityException(
                f"Requirement creation violates uniqueness constraint: {str(exc)}",
            )

        # Automatically initialize baseline compliance status snapshot as GAP
        initial_status = ComplianceStatusRecord(
            requirement_id=requirement.id,
            status=ComplianceStatus.GAP,
            status_reason="Unassessed: requirement created, awaiting evidence evaluation.",
        )
        session.add(initial_status)
        session.flush()

        logger.info(
            "Created requirement '%s' [%s] under framework [%s]",
            requirement.requirement_code,
            requirement.id,
            framework_id,
        )
        return requirement

    @staticmethod
    def update_requirement(
        session: Session,
        requirement_id: uuid.UUID,
        data: RequirementUpdate,
    ) -> Requirement:
        """Update existing requirement attributes."""
        requirement = FrameworkService.get_requirement(session, requirement_id)

        update_dict = data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(requirement, key, value)

        session.flush()
        logger.info("Updated requirement '%s' [%s]", requirement.requirement_code, requirement.id)
        return requirement
