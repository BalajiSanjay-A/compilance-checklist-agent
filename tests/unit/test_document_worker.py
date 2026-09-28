"""Unit tests for DocumentWorker: job processing, retry, error handling."""

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from src.config import Settings
from src.database.models import (
    DocumentProcessingJob,
    DocumentType,
    EvidenceDocument,
    EvidenceValidity,
    JobStatus,
    ProcessingStatus,
)
from src.services.job_queue_service import JobQueueService
from src.workers.document_worker import DocumentWorker, handle_extract_text


def _create_evidence_with_file(
    session: Session, tmp_path: Path, filename: str = "test.txt", content: str = "Evidence content here."
) -> EvidenceDocument:
    file_hash = uuid.uuid4().hex + uuid.uuid4().hex[:32]
    storage_subpath = f"ab/cd/{file_hash}_{filename}"

    storage_dir = tmp_path / "evidence"
    abs_path = storage_dir / storage_subpath
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(content, encoding="utf-8")

    doc = EvidenceDocument(
        filename=filename,
        document_type=DocumentType.POLICY,
        storage_path=storage_subpath,
        file_hash=file_hash,
        file_size_bytes=len(content.encode()),
        processing_status=ProcessingStatus.QUEUED,
        validity_status=EvidenceValidity.VALID,
        uploaded_at=datetime.now(timezone.utc),
    )
    session.add(doc)
    session.flush()
    return doc


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        use_sqlite_fallback=True,
        sqlite_db_path=":memory:",
        storage_dir=tmp_path / "evidence",
        worker_poll_interval_seconds=0,
        worker_batch_size=5,
        worker_lease_timeout_seconds=600,
    )


class TestHandleExtractText:
    def test_extracts_txt(self, db_session: Session, tmp_path: Path, settings: Settings):
        evidence = _create_evidence_with_file(db_session, tmp_path, "policy.txt", "MFA required for all users.")
        job = JobQueueService.enqueue(db_session, evidence.id)
        claimed = JobQueueService.claim_jobs(db_session, "w1")

        handle_extract_text(db_session, claimed[0], settings)

        db_session.refresh(evidence)
        assert evidence.processing_status == ProcessingStatus.PROCESSED
        assert "MFA" in evidence.content_text

    def test_handles_missing_file(self, db_session: Session, tmp_path: Path, settings: Settings):
        evidence = _create_evidence_with_file(db_session, tmp_path, "policy.txt")
        # Delete the file
        abs_path = settings.storage_dir / evidence.storage_path
        abs_path.unlink()

        job = JobQueueService.enqueue(db_session, evidence.id)
        claimed = JobQueueService.claim_jobs(db_session, "w1")

        with pytest.raises(FileNotFoundError):
            handle_extract_text(db_session, claimed[0], settings)

    def test_unsupported_extension(self, db_session: Session, tmp_path: Path, settings: Settings):
        evidence = _create_evidence_with_file(db_session, tmp_path, "report.docx", "fake docx")
        job = JobQueueService.enqueue(db_session, evidence.id)
        claimed = JobQueueService.claim_jobs(db_session, "w1")

        handle_extract_text(db_session, claimed[0], settings)

        db_session.refresh(evidence)
        assert evidence.processing_status == ProcessingStatus.UPLOADED


class TestDocumentWorkerProcessing:
    def test_process_single_job_success(self, db_session: Session, tmp_path: Path, settings: Settings):
        evidence = _create_evidence_with_file(db_session, tmp_path, "policy.txt", "Encryption enforced.")
        job = JobQueueService.enqueue(db_session, evidence.id)
        claimed = JobQueueService.claim_jobs(db_session, "w1")

        worker = DocumentWorker(worker_id="w1", settings=settings)
        result = worker.process_single_job(db_session, claimed[0])

        assert result is True
        db_session.refresh(claimed[0])
        assert claimed[0].status == JobStatus.COMPLETED

    def test_process_single_job_failure(self, db_session: Session, tmp_path: Path, settings: Settings):
        evidence = _create_evidence_with_file(db_session, tmp_path, "bad.txt", "content")
        # Delete file to cause error
        abs_path = settings.storage_dir / evidence.storage_path
        abs_path.unlink()

        job = JobQueueService.enqueue(db_session, evidence.id, max_attempts=3)
        claimed = JobQueueService.claim_jobs(db_session, "w1")

        worker = DocumentWorker(worker_id="w1", settings=settings)
        result = worker.process_single_job(db_session, claimed[0])

        assert result is False
        db_session.refresh(claimed[0])
        # Should be requeued for retry since max_attempts=3 and only attempt 1
        assert claimed[0].status == JobStatus.QUEUED

    def test_process_unknown_job_type(self, db_session: Session, tmp_path: Path, settings: Settings):
        evidence = _create_evidence_with_file(db_session, tmp_path)
        job = JobQueueService.enqueue(db_session, evidence.id, job_type="UNKNOWN_TYPE")
        # Manually set job_type to bypass idempotency check
        job.job_type = "UNKNOWN_TYPE"
        db_session.flush()

        claimed = JobQueueService.claim_jobs(db_session, "w1")
        worker = DocumentWorker(worker_id="w1", settings=settings)
        result = worker.process_single_job(db_session, claimed[0])

        assert result is False
