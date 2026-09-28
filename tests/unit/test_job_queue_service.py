"""Unit tests for JobQueueService: enqueue, claim, complete, fail, retry."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from src.core.exceptions import JobQueueException
from src.database.models import (
    DocumentProcessingJob,
    DocumentType,
    EvidenceDocument,
    EvidenceValidity,
    JobStatus,
    ProcessingStatus,
)
from src.services.job_queue_service import JobQueueService


def _create_evidence(session: Session, filename: str = "test.txt") -> EvidenceDocument:
    doc = EvidenceDocument(
        filename=filename,
        document_type=DocumentType.OTHER,
        storage_path=f"ab/cd/{uuid.uuid4().hex}_{filename}",
        file_hash=uuid.uuid4().hex + uuid.uuid4().hex[:32],
        file_size_bytes=100,
        processing_status=ProcessingStatus.QUEUED,
        validity_status=EvidenceValidity.VALID,
        uploaded_at=datetime.now(timezone.utc),
    )
    session.add(doc)
    session.flush()
    return doc


class TestEnqueue:
    def test_enqueue_creates_job(self, db_session: Session):
        evidence = _create_evidence(db_session)
        job = JobQueueService.enqueue(db_session, evidence.id)
        assert job.status == JobStatus.QUEUED
        assert job.evidence_id == evidence.id
        assert job.job_type == "EXTRACT_TEXT"
        assert job.attempts == 0

    def test_enqueue_idempotent(self, db_session: Session):
        evidence = _create_evidence(db_session)
        job1 = JobQueueService.enqueue(db_session, evidence.id)
        job2 = JobQueueService.enqueue(db_session, evidence.id)
        assert job1.id == job2.id

    def test_enqueue_different_types(self, db_session: Session):
        evidence = _create_evidence(db_session)
        job1 = JobQueueService.enqueue(db_session, evidence.id, job_type="EXTRACT_TEXT")
        job2 = JobQueueService.enqueue(db_session, evidence.id, job_type="AI_MATCH")
        assert job1.id != job2.id


class TestClaimJobs:
    def test_claim_queued_jobs(self, db_session: Session):
        evidence = _create_evidence(db_session)
        JobQueueService.enqueue(db_session, evidence.id)

        claimed = JobQueueService.claim_jobs(db_session, "worker-1", batch_size=5)
        assert len(claimed) == 1
        assert claimed[0].status == JobStatus.PROCESSING
        assert claimed[0].locked_by == "worker-1"
        assert claimed[0].attempts == 1

    def test_claim_respects_batch_size(self, db_session: Session):
        for _ in range(5):
            evidence = _create_evidence(db_session, f"test_{uuid.uuid4().hex[:4]}.txt")
            JobQueueService.enqueue(db_session, evidence.id)

        claimed = JobQueueService.claim_jobs(db_session, "worker-1", batch_size=2)
        assert len(claimed) == 2

    def test_claimed_jobs_not_reclaimable(self, db_session: Session):
        evidence = _create_evidence(db_session)
        JobQueueService.enqueue(db_session, evidence.id)

        claimed1 = JobQueueService.claim_jobs(db_session, "worker-1", batch_size=5)
        assert len(claimed1) == 1

        claimed2 = JobQueueService.claim_jobs(db_session, "worker-2", batch_size=5)
        assert len(claimed2) == 0

    def test_claim_reclaims_expired_lease(self, db_session: Session):
        evidence = _create_evidence(db_session)
        job = JobQueueService.enqueue(db_session, evidence.id)

        # Simulate stale lock
        job.status = JobStatus.PROCESSING
        job.locked_at = datetime.now(timezone.utc) - timedelta(seconds=700)
        job.locked_by = "dead-worker"
        job.attempts = 1
        db_session.flush()

        claimed = JobQueueService.claim_jobs(
            db_session, "worker-2", batch_size=5, lease_timeout_seconds=600
        )
        assert len(claimed) == 1
        assert claimed[0].locked_by == "worker-2"
        assert claimed[0].attempts == 2

    def test_claim_skips_future_scheduled(self, db_session: Session):
        evidence = _create_evidence(db_session)
        job = JobQueueService.enqueue(db_session, evidence.id)
        job.scheduled_at = datetime.now(timezone.utc) + timedelta(hours=1)
        db_session.flush()

        claimed = JobQueueService.claim_jobs(db_session, "worker-1")
        assert len(claimed) == 0


class TestCompleteJob:
    def test_complete_success(self, db_session: Session):
        evidence = _create_evidence(db_session)
        JobQueueService.enqueue(db_session, evidence.id)
        claimed = JobQueueService.claim_jobs(db_session, "worker-1")
        job = claimed[0]

        completed = JobQueueService.complete_job(db_session, job.id, "worker-1")
        assert completed.status == JobStatus.COMPLETED
        assert completed.completed_at is not None

    def test_complete_wrong_worker_raises(self, db_session: Session):
        evidence = _create_evidence(db_session)
        JobQueueService.enqueue(db_session, evidence.id)
        claimed = JobQueueService.claim_jobs(db_session, "worker-1")

        with pytest.raises(JobQueueException, match="not owned"):
            JobQueueService.complete_job(db_session, claimed[0].id, "worker-2")

    def test_complete_nonexistent_raises(self, db_session: Session):
        with pytest.raises(JobQueueException, match="not found"):
            JobQueueService.complete_job(db_session, uuid.uuid4(), "worker-1")


class TestFailJob:
    def test_fail_with_retry(self, db_session: Session):
        evidence = _create_evidence(db_session)
        JobQueueService.enqueue(db_session, evidence.id, max_attempts=3)
        claimed = JobQueueService.claim_jobs(db_session, "worker-1")
        job = claimed[0]

        failed = JobQueueService.fail_job(db_session, job.id, "worker-1", "timeout")
        assert failed.status == JobStatus.QUEUED
        assert failed.locked_at is None
        assert failed.locked_by is None
        assert failed.error_message == "timeout"
        assert failed.scheduled_at > datetime.now(timezone.utc)

    def test_fail_permanently_after_max_attempts(self, db_session: Session):
        evidence = _create_evidence(db_session)
        job = JobQueueService.enqueue(db_session, evidence.id, max_attempts=1)

        claimed = JobQueueService.claim_jobs(db_session, "worker-1")
        failed = JobQueueService.fail_job(db_session, claimed[0].id, "worker-1", "crash")
        assert failed.status == JobStatus.FAILED
        assert failed.completed_at is not None

    def test_exponential_backoff(self, db_session: Session):
        evidence = _create_evidence(db_session)
        job = JobQueueService.enqueue(db_session, evidence.id, max_attempts=5)

        # Attempt 1
        claimed = JobQueueService.claim_jobs(db_session, "worker-1")
        failed1 = JobQueueService.fail_job(db_session, claimed[0].id, "worker-1", "err")
        delay1 = (failed1.scheduled_at - datetime.now(timezone.utc)).total_seconds()

        # Reset for attempt 2
        failed1.scheduled_at = datetime.now(timezone.utc)
        db_session.flush()
        claimed2 = JobQueueService.claim_jobs(db_session, "worker-1")
        failed2 = JobQueueService.fail_job(db_session, claimed2[0].id, "worker-1", "err")
        delay2 = (failed2.scheduled_at - datetime.now(timezone.utc)).total_seconds()

        assert delay2 > delay1

    def test_fail_wrong_worker_raises(self, db_session: Session):
        evidence = _create_evidence(db_session)
        JobQueueService.enqueue(db_session, evidence.id)
        claimed = JobQueueService.claim_jobs(db_session, "worker-1")

        with pytest.raises(JobQueueException, match="not owned"):
            JobQueueService.fail_job(db_session, claimed[0].id, "worker-2", "err")


class TestGetJob:
    def test_get_existing(self, db_session: Session):
        evidence = _create_evidence(db_session)
        job = JobQueueService.enqueue(db_session, evidence.id)
        found = JobQueueService.get_job(db_session, job.id)
        assert found.id == job.id

    def test_get_nonexistent_raises(self, db_session: Session):
        with pytest.raises(JobQueueException, match="not found"):
            JobQueueService.get_job(db_session, uuid.uuid4())


class TestQueueStats:
    def test_stats_with_mixed_statuses(self, db_session: Session):
        for i in range(3):
            evidence = _create_evidence(db_session, f"q_{i}.txt")
            JobQueueService.enqueue(db_session, evidence.id)

        # Complete one
        claimed = JobQueueService.claim_jobs(db_session, "w1", batch_size=1)
        JobQueueService.complete_job(db_session, claimed[0].id, "w1")

        stats = JobQueueService.get_queue_stats(db_session)
        assert stats["QUEUED"] == 2
        assert stats["COMPLETED"] == 1


class TestUpdateEvidenceStatus:
    def test_updates_status_and_content(self, db_session: Session):
        evidence = _create_evidence(db_session)
        JobQueueService.update_evidence_status(
            db_session, evidence.id, ProcessingStatus.PROCESSED,
            content_text="Extracted text here",
        )
        db_session.refresh(evidence)
        assert evidence.processing_status == ProcessingStatus.PROCESSED
        assert evidence.content_text == "Extracted text here"

    def test_updates_error(self, db_session: Session):
        evidence = _create_evidence(db_session)
        JobQueueService.update_evidence_status(
            db_session, evidence.id, ProcessingStatus.FAILED,
            error_message="PDF corrupt",
        )
        db_session.refresh(evidence)
        assert evidence.processing_status == ProcessingStatus.FAILED
        assert evidence.processing_error == "PDF corrupt"
