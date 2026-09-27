"""Database seeder for compliance frameworks, requirements, and default admin user."""

import json
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.core.logging import get_logger
from src.core.security import Role, get_password_hash
from src.database.models import (
    ComplianceFramework,
    ComplianceStatus,
    ComplianceStatusRecord,
    Requirement,
    Severity,
    User,
)
from src.database.session import get_engine, get_session_factory, transactional_session

logger = get_logger("database.seed")


def seed_framework_from_file(session: Session, file_path: Path) -> ComplianceFramework:
    """Load and persist a compliance framework and its requirements from a JSON file."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    name = data["name"]
    version = data["version"]
    description = data.get("description", "")
    requirements_data = data.get("requirements", [])

    # Check for existing framework
    stmt = select(ComplianceFramework).where(
        ComplianceFramework.name == name,
        ComplianceFramework.version == version,
    )
    framework = session.scalars(stmt).first()

    if not framework:
        framework = ComplianceFramework(
            name=name,
            version=version,
            description=description,
            is_active=True,
        )
        session.add(framework)
        session.flush()
        logger.info("Created framework: %s (v%s)", name, version)
    else:
        logger.info("Framework already exists: %s (v%s)", name, version)

    # Seed requirements
    for req_dict in requirements_data:
        code = req_dict["requirement_code"]
        req_stmt = select(Requirement).where(
            Requirement.framework_id == framework.id,
            Requirement.requirement_code == code,
        )
        existing_req = session.scalars(req_stmt).first()

        if not existing_req:
            severity = Severity(req_dict.get("severity", "MEDIUM"))
            req = Requirement(
                framework_id=framework.id,
                requirement_code=code,
                title=req_dict["title"],
                description=req_dict["description"],
                severity=severity,
                is_active=True,
            )
            session.add(req)
            session.flush()

            # Initialize baseline compliance status snapshot as GAP
            initial_status = ComplianceStatusRecord(
                requirement_id=req.id,
                status=ComplianceStatus.GAP,
                status_reason="Unassessed: requirement seeded, awaiting evidence evaluation.",
            )
            session.add(initial_status)
            logger.info("  Seeded requirement %s: %s", code, req.title)

    return framework


def seed_default_user(session: Session) -> User:
    """Idempotently seed default compliance officer user."""
    settings = get_settings()
    username = settings.default_admin_username
    email = settings.default_admin_email
    password = settings.default_admin_password

    stmt = select(User).where(User.username == username)
    user = session.scalars(stmt).first()

    if not user:
        user = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            role=Role.COMPLIANCE_OFFICER,
            is_active=True,
        )
        session.add(user)
        session.flush()
        logger.info("Created default user: %s (role: %s)", username, Role.COMPLIANCE_OFFICER.value)
    else:
        logger.info("Default user already exists: %s", username)

    return user


def seed_database(session: Optional[Session] = None, seed_dir: Optional[Path] = None) -> None:
    """Execute complete database seeding for frameworks and default user."""
    seed_path = seed_dir or (Path(__file__).parent.parent.parent / "seed" / "frameworks")

    def _execute(sess: Session):
        # 1. Seed frameworks
        if seed_path.exists():
            for json_file in sorted(seed_path.glob("*.json")):
                logger.info("Seeding from %s...", json_file.name)
                seed_framework_from_file(sess, json_file)
        else:
            logger.warning("Seed directory not found at: %s", seed_path)

        # 2. Seed default compliance officer
        seed_default_user(sess)

    if session is not None:
        _execute(session)
    else:
        engine = get_engine()
        factory = get_session_factory(engine)
        with factory() as sess:
            with transactional_session(sess):
                _execute(sess)


if __name__ == "__main__":
    from src.database.session import init_db
    init_db()
    seed_database()
    logger.info("Database seeding complete.")
