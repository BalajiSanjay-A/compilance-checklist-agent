"""Integration tests for Alembic database migration upgrade and downgrade lifecycle."""

from pathlib import Path
import tempfile
import pytest
from sqlalchemy import create_engine, inspect

from alembic.config import Config
from alembic import command


def test_alembic_upgrade_and_downgrade():
    """Verify that Alembic runs upgrade to head and downgrade to base on a clean database."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp_db:
        db_url = f"sqlite:///{tmp_db.name}"

        # Setup Alembic Config pointing to project root
        project_root = Path(__file__).parent.parent.parent
        alembic_cfg = Config(str(project_root / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(project_root / "alembic"))
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)

        # 1. Upgrade to head
        command.upgrade(alembic_cfg, "head")

        engine = create_engine(db_url)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        expected_tables = {
            "compliance_frameworks",
            "requirements",
            "evidence_documents",
            "document_processing_jobs",
            "evidence_matches",
            "compliance_status",
            "compliance_status_history",
            "gap_reports",
            "users",
            "alembic_version",
        }
        for expected in expected_tables:
            assert expected in tables, f"Expected table '{expected}' missing after migration upgrade."

        # 2. Downgrade to base
        command.downgrade(alembic_cfg, "base")

        inspector_after = inspect(engine)
        remaining_tables = set(inspector_after.get_table_names())
        # All domain tables must be dropped (alembic_version may remain empty)
        remaining_domain_tables = remaining_tables - {"alembic_version"}
        assert len(remaining_domain_tables) == 0, f"Domain tables remained after downgrade: {remaining_domain_tables}"

        engine.dispose()
