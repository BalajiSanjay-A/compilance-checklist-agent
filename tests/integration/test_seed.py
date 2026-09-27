"""Integration tests for database seeding and idempotency."""

from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.security import Role, verify_password
from src.database.models import (
    ComplianceFramework,
    ComplianceStatus,
    ComplianceStatusRecord,
    Requirement,
    User,
)
from src.database.seed import seed_database


def test_seed_database_loads_frameworks_and_requirements(db_session: Session):
    """Verify seed_database seeds SOC 2 and ISO 27001 with baseline GAP status."""
    seed_database(session=db_session)

    # Verify frameworks
    frameworks = db_session.scalars(select(ComplianceFramework)).all()
    framework_names = {f.name for f in frameworks}
    assert "SOC 2 Type II" in framework_names
    assert "ISO/IEC 27001" in framework_names

    # Verify SOC 2 requirements
    soc2 = db_session.scalars(
        select(ComplianceFramework).where(ComplianceFramework.name == "SOC 2 Type II")
    ).one()
    soc2_codes = {r.requirement_code for r in soc2.requirements}
    assert "CC6.1" in soc2_codes
    assert "CC7.2" in soc2_codes
    assert "CC8.1" in soc2_codes
    assert len(soc2.requirements) >= 9

    # Verify every requirement has an initial baseline GAP status
    for req in soc2.requirements:
        status_rec = db_session.scalars(
            select(ComplianceStatusRecord).where(ComplianceStatusRecord.requirement_id == req.id)
        ).one()
        assert status_rec.status == ComplianceStatus.GAP
        assert "Unassessed" in status_rec.status_reason

    # Verify default compliance officer user
    admin_user = db_session.scalars(select(User).where(User.username == "compliance_admin")).first()
    assert admin_user is not None
    assert admin_user.role == Role.COMPLIANCE_OFFICER
    assert verify_password("change_this_password_immediately", admin_user.hashed_password) is True


def test_seed_database_idempotency(db_session: Session):
    """Verify calling seed_database multiple times does not duplicate records."""
    seed_database(session=db_session)
    count_fw_1 = len(db_session.scalars(select(ComplianceFramework)).all())
    count_req_1 = len(db_session.scalars(select(Requirement)).all())
    count_users_1 = len(db_session.scalars(select(User)).all())

    # Second pass
    seed_database(session=db_session)
    count_fw_2 = len(db_session.scalars(select(ComplianceFramework)).all())
    count_req_2 = len(db_session.scalars(select(Requirement)).all())
    count_users_2 = len(db_session.scalars(select(User)).all())

    assert count_fw_1 == count_fw_2
    assert count_req_1 == count_req_2
    assert count_users_1 == count_users_2
