"""Durable database-backed job queue service with lease-based locking."""

import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.config import Settings
from src.core.exceptions import JobQueueException
from src.core.logging import get_logger
from src.database.models import (
    DocumentProcessingJob,
    EvidenceDocument,
    JobStatus,
    ProcessingStatus,
)

logger = get_logger("service.job_queue")


class JobQueueService:
    """Service managing the durable document processing job queue."""

    @staticmethod
    def enqueue(
        session: Session,
        evidence_id: uuid.UUID,
        job_type: str = "EXTRACT_TEXT",
        max_attempts: int = 3,
    ) -> DocumentProcessingJob:
        """Create a new job in QUEUED state."""
        existing = session.scalars(
            select(DocumentProcessingJob).where(
                DocumentProcessingJob.evidence_id == evidence_id,
                DocumentProcessingJob.job_type == job_type,
                DocumentProcessingJob.status.in_([JobStatus.QUEUED, JobStatus.PROCESSING]),
            )
        ).first()

        if existing:
            logger.info("Active job already exists for evidence [%s] type=%s", evidence_id, job_type)
            return existing

        job = DocumentProcessingJob(
            evidence_id=evidence_id,
            job_type=job_type,
            status=JobStatus.QUEUED,
            max_attempts=max_attempts,
        )
        session.add(job)
        session.flush()
        logger.info("Enqueued job [%s] type=%s for evidence [%s]", job.id, job_type, evidence_id)
        return job

    @staticmethod
    def claim_jobs(
        session: Session,
        worker_id: str,
        batch_size: int = 5,
        lease_timeout_seconds: int = 600,
    ) -> List[DocumentProcessingJob]:
        """Claim up to batch_size QUEUED jobs using lease-based locking.

        Also reclaims expired leases from stale workers.
        """
        now = datetime.now(timezone.utc)
        lease_expiry = now - timedelta(seconds=lease_timeout_seconds)

        # For SQLite compatibility, use a two-step approach:
        # 1. Select eligible jobs (QUEUED, or stale PROCESSING)
        # 2. Update them atomically
        stmt = (
            select(DocumentProcessingJob)
            .where(
                (
                    (DocumentProcessingJob.status == JobStatus.QUEUED)
                    | (
                        (DocumentProcessingJob.status == JobStatus.PROCESSING)
                        & (DocumentProcessingJob.locked_at < lease_expiry)
                    )
                ),
                DocumentProcessingJob.scheduled_at <= now,
            )
            .order_by(DocumentProcessingJob.scheduled_at)
            .limit(batch_size)
        )

        # Use with_for_update for PostgreSQL; SQLite ignores it gracefully
        try:
            stmt = stmt.with_for_update(skip_locked=True)
        except Exception:
            pass

        jobs = list(session.scalars(stmt).all())

        for job in jobs:
            job.status = JobStatus.PROCESSING
            job.locked_at = now
            job.locked_by = worker_id
            job.attempts += 1

        if jobs:
            session.flush()
            logger.info("Worker %s claimed %d jobs", worker_id, len(jobs))

        return jobs

    @staticmethod
    def complete_job(
        session: Session,
        job_id: uuid.UUID,
        worker_id: str,
    ) -> DocumentProcessingJob:
        """Mark a job as COMPLETED."""
        job = session.get(DocumentProcessingJob, job_id)
        if not job:
            raise JobQueueException(f"Job {job_id} not found")
        if job.locked_by != worker_id:
            raise JobQueueException(
                f"Job {job_id} is not owned by worker {worker_id}",
                details={"locked_by": job.locked_by, "worker_id": worker_id},
            )

        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)
        session.flush()

        logger.info("Job [%s] completed by worker %s", job_id, worker_id)
        return job

    @staticmethod
    def fail_job(
        session: Session,
        job_id: uuid.UUID,
        worker_id: str,
        error_message: str,
    ) -> DocumentProcessingJob:
        """Mark a job as FAILED or re-queue for retry with exponential backoff."""
        job = session.get(DocumentProcessingJob, job_id)
        if not job:
            raise JobQueueException(f"Job {job_id} not found")
        if job.locked_by != worker_id:
            raise JobQueueException(
                f"Job {job_id} is not owned by worker {worker_id}",
                details={"locked_by": job.locked_by, "worker_id": worker_id},
            )

        job.error_message = error_message

        if job.attempts < job.max_attempts:
            backoff_seconds = min(60 * (2 ** (job.attempts - 1)), 3600)
            job.status = JobStatus.QUEUED
            job.locked_at = None
            job.locked_by = None
            job.scheduled_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
            logger.warning(
                "Job [%s] failed (attempt %d/%d), retry in %ds: %s",
                job_id, job.attempts, job.max_attempts, backoff_seconds, error_message,
            )
        else:
            job.status = JobStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)
            logger.error(
                "Job [%s] permanently failed after %d attempts: %s",
                job_id, job.attempts, error_message,
            )

        session.flush()
        return job

    @staticmethod
    def get_job(session: Session, job_id: uuid.UUID) -> DocumentProcessingJob:
        """Retrieve a job by ID."""
        job = session.get(DocumentProcessingJob, job_id)
        if not job:
            raise JobQueueException(f"Job {job_id} not found")
        return job

    @staticmethod
    def get_queue_stats(session: Session) -> Dict[str, int]:
        """Get counts of jobs by status."""
        from sqlalchemy import func
        rows = session.execute(
            select(DocumentProcessingJob.status, func.count(DocumentProcessingJob.id))
            .group_by(DocumentProcessingJob.status)
        ).all()
        stats = {s.value: 0 for s in JobStatus}
        for status, count in rows:
            stats[status.value if hasattr(status, 'value') else status] = count
        return stats

    @staticmethod
    def update_evidence_status(
        session: Session,
        evidence_id: uuid.UUID,
        processing_status: ProcessingStatus,
        content_text: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Update evidence document processing status after job completion."""
        evidence = session.get(EvidenceDocument, evidence_id)
        if evidence:
            evidence.processing_status = processing_status
            if content_text is not None:
                evidence.content_text = content_text
            if error_message is not None:
                evidence.processing_error = error_message
            session.flush()
