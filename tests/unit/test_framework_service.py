"""Unit tests for FrameworkService business logic."""

import uuid

import pytest
from sqlalchemy.orm import Session

from src.core.exceptions import DuplicateEntityException, EntityNotFoundException
from src.database.models import ComplianceFramework, ComplianceStatus, ComplianceStatusRecord, Requirement, Severity
from src.schemas.framework import FrameworkCreate, FrameworkUpdate, RequirementCreate, RequirementUpdate
from src.services.framework_service import FrameworkService


class TestFrameworkCRUD:
    def test_create_framework(self, db_session: Session):
        data = FrameworkCreate(name="SOC 2", version="2023", description="Security framework")
        fw = FrameworkService.create_framework(db_session, data)
        assert fw.name == "SOC 2"
        assert fw.version == "2023"
        assert fw.id is not None

    def test_create_framework_duplicate_raises(self, db_session: Session):
        data = FrameworkCreate(name="Dup", version="1.0")
        FrameworkService.create_framework(db_session, data)
        with pytest.raises(DuplicateEntityException):
            FrameworkService.create_framework(db_session, data)

    def test_get_framework(self, db_session: Session):
        data = FrameworkCreate(name="Get-Test", version="1")
        fw = FrameworkService.create_framework(db_session, data)
        result, count = FrameworkService.get_framework(db_session, fw.id)
        assert result.id == fw.id
        assert count == 0

    def test_get_framework_not_found(self, db_session: Session):
        with pytest.raises(EntityNotFoundException):
            FrameworkService.get_framework(db_session, uuid.uuid4())

    def test_list_frameworks_empty(self, db_session: Session):
        results = FrameworkService.list_frameworks(db_session)
        assert results == []

    def test_list_frameworks_with_requirement_counts(self, db_session: Session):
        data = FrameworkCreate(name="Counted", version="1")
        fw = FrameworkService.create_framework(db_session, data)
        req_data = RequirementCreate(
            requirement_code="R-1", title="Req 1", description="Desc"
        )
        FrameworkService.create_requirement(db_session, fw.id, req_data)

        results = FrameworkService.list_frameworks(db_session)
        assert len(results) == 1
        _, count = results[0]
        assert count == 1

    def test_list_frameworks_active_filter(self, db_session: Session):
        FrameworkService.create_framework(db_session, FrameworkCreate(name="Active", version="1"))
        fw_inactive = ComplianceFramework(name="Inactive", version="1", is_active=False)
        db_session.add(fw_inactive)
        db_session.flush()

        active = FrameworkService.list_frameworks(db_session, is_active=True)
        inactive = FrameworkService.list_frameworks(db_session, is_active=False)
        assert len(active) == 1
        assert active[0][0].name == "Active"
        assert len(inactive) == 1

    def test_update_framework(self, db_session: Session):
        fw = FrameworkService.create_framework(db_session, FrameworkCreate(name="Old", version="1"))
        updated = FrameworkService.update_framework(
            db_session, fw.id, FrameworkUpdate(name="New")
        )
        assert updated.name == "New"
        assert updated.version == "1"

    def test_update_framework_not_found(self, db_session: Session):
        with pytest.raises(EntityNotFoundException):
            FrameworkService.update_framework(
                db_session, uuid.uuid4(), FrameworkUpdate(name="X")
            )


class TestRequirementCRUD:
    def _create_framework(self, session: Session) -> ComplianceFramework:
        return FrameworkService.create_framework(
            session, FrameworkCreate(name="TestFW", version="1")
        )

    def test_create_requirement(self, db_session: Session):
        fw = self._create_framework(db_session)
        data = RequirementCreate(
            requirement_code="CC6.1", title="Access Control", description="Control access."
        )
        req = FrameworkService.create_requirement(db_session, fw.id, data)
        assert req.requirement_code == "CC6.1"
        assert req.framework_id == fw.id

    def test_create_requirement_initializes_gap_status(self, db_session: Session):
        fw = self._create_framework(db_session)
        data = RequirementCreate(
            requirement_code="CC6.2", title="Test", description="Desc"
        )
        req = FrameworkService.create_requirement(db_session, fw.id, data)

        status_record = (
            db_session.query(ComplianceStatusRecord)
            .filter_by(requirement_id=req.id)
            .first()
        )
        assert status_record is not None
        assert status_record.status == ComplianceStatus.GAP

    def test_create_requirement_duplicate_raises(self, db_session: Session):
        fw = self._create_framework(db_session)
        data = RequirementCreate(
            requirement_code="DUP", title="Dup", description="Desc"
        )
        FrameworkService.create_requirement(db_session, fw.id, data)
        with pytest.raises(DuplicateEntityException):
            FrameworkService.create_requirement(db_session, fw.id, data)

    def test_create_requirement_framework_not_found(self, db_session: Session):
        data = RequirementCreate(
            requirement_code="X", title="X", description="X"
        )
        with pytest.raises(EntityNotFoundException):
            FrameworkService.create_requirement(db_session, uuid.uuid4(), data)

    def test_get_requirement(self, db_session: Session):
        fw = self._create_framework(db_session)
        data = RequirementCreate(
            requirement_code="R-1", title="Req", description="Desc"
        )
        req = FrameworkService.create_requirement(db_session, fw.id, data)
        result = FrameworkService.get_requirement(db_session, req.id)
        assert result.id == req.id

    def test_get_requirement_not_found(self, db_session: Session):
        with pytest.raises(EntityNotFoundException):
            FrameworkService.get_requirement(db_session, uuid.uuid4())

    def test_list_requirements_pagination(self, db_session: Session):
        fw = self._create_framework(db_session)
        for i in range(10):
            FrameworkService.create_requirement(
                db_session,
                fw.id,
                RequirementCreate(
                    requirement_code=f"R-{i:02d}", title=f"Req {i}", description="Desc"
                ),
            )

        items, total = FrameworkService.list_requirements(
            db_session, fw.id, page=2, page_size=3
        )
        assert total == 10
        assert len(items) == 3
        assert items[0].requirement_code == "R-03"

    def test_list_requirements_severity_filter(self, db_session: Session):
        fw = self._create_framework(db_session)
        FrameworkService.create_requirement(
            db_session, fw.id,
            RequirementCreate(requirement_code="H-1", title="High", description="D", severity=Severity.HIGH),
        )
        FrameworkService.create_requirement(
            db_session, fw.id,
            RequirementCreate(requirement_code="L-1", title="Low", description="D", severity=Severity.LOW),
        )

        items, total = FrameworkService.list_requirements(
            db_session, fw.id, severity=Severity.HIGH
        )
        assert total == 1
        assert items[0].requirement_code == "H-1"

    def test_update_requirement(self, db_session: Session):
        fw = self._create_framework(db_session)
        req = FrameworkService.create_requirement(
            db_session, fw.id,
            RequirementCreate(requirement_code="R-1", title="Old", description="Desc"),
        )
        updated = FrameworkService.update_requirement(
            db_session, req.id, RequirementUpdate(title="New")
        )
        assert updated.title == "New"
        assert updated.requirement_code == "R-1"

    def test_update_requirement_not_found(self, db_session: Session):
        with pytest.raises(EntityNotFoundException):
            FrameworkService.update_requirement(
                db_session, uuid.uuid4(), RequirementUpdate(title="X")
            )
