"""Background worker for processing document extraction jobs."""

import signal
import time
import uuid
from pathlib import Path
from typing import Callable, Dict, Optional

from sqlalchemy.orm import Session

from src.config import Settings, get_settings
from src.core.logging import get_logger
from src.database.models import DocumentProcessingJob, ProcessingStatus
from src.database.session import get_session_factory, transactional_session
from src.services.evidence_service import EvidenceService
from src.services.job_queue_service import JobQueueService

logger = get_logger("worker.document")


JobHandler = Callable[[Session, DocumentProcessingJob, Settings], None]


def handle_extract_text(session: Session, job: DocumentProcessingJob, settings: Settings) -> None:
    """Process an EXTRACT_TEXT job: extract text from the stored evidence file."""
    evidence = job.evidence
    if not evidence:
        raise RuntimeError(f"No evidence document found for job {job.id}")

    abs_path = settings.storage_dir / evidence.storage_path
    if not abs_path.exists():
        raise FileNotFoundError(f"Evidence file not found: {evidence.storage_path}")

    content_type_map = {
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".text": "text/plain",
        ".log": "text/plain",
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".csv": "text/csv",
    }

    ext = Path(evidence.filename).suffix.lower()
    content_type = content_type_map.get(ext)

    if content_type is None:
        JobQueueService.update_evidence_status(
            session, evidence.id, ProcessingStatus.UPLOADED,
            error_message=f"Unsupported file type for text extraction: {ext}",
        )
        return

    text = EvidenceService.extract_text(abs_path, content_type)

    if text:
        JobQueueService.update_evidence_status(
            session, evidence.id, ProcessingStatus.PROCESSED, content_text=text,
        )
    else:
        JobQueueService.update_evidence_status(
            session, evidence.id, ProcessingStatus.UPLOADED,
            error_message="Text extraction returned no content.",
        )


JOB_HANDLERS: Dict[str, JobHandler] = {
    "EXTRACT_TEXT": handle_extract_text,
}


class DocumentWorker:
    """Background worker that polls and processes document extraction jobs."""

    def __init__(
        self,
        worker_id: Optional[str] = None,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or get_settings()
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self._running = False
        self._session_factory = get_session_factory()

    def process_single_job(self, session: Session, job: DocumentProcessingJob) -> bool:
        """Process one job. Returns True on success, False on failure."""
        handler = JOB_HANDLERS.get(job.job_type)
        if not handler:
            JobQueueService.fail_job(
                session, job.id, self.worker_id,
                f"Unknown job type: {job.job_type}",
            )
            return False

        try:
            handler(session, job, self.settings)
            JobQueueService.complete_job(session, job.id, self.worker_id)
            return True
        except Exception as exc:
            logger.exception("Job [%s] processing error", job.id)
            JobQueueService.fail_job(session, job.id, self.worker_id, str(exc))
            return False

    def poll_and_process(self) -> int:
        """Poll for jobs and process them. Returns number of jobs processed."""
        session = self._session_factory()
        try:
            jobs = JobQueueService.claim_jobs(
                session,
                worker_id=self.worker_id,
                batch_size=self.settings.worker_batch_size,
                lease_timeout_seconds=self.settings.worker_lease_timeout_seconds,
            )
            session.commit()

            processed = 0
            for job in jobs:
                session.refresh(job)
                with transactional_session(session):
                    if self.process_single_job(session, job):
                        processed += 1

            return processed
        except Exception:
            session.rollback()
            logger.exception("Worker poll cycle error")
            return 0
        finally:
            session.close()

    def run(self, max_iterations: Optional[int] = None) -> None:
        """Run the worker loop. Polls indefinitely unless max_iterations is set."""
        self._running = True
        iteration = 0

        def _stop(signum, frame):
            logger.info("Worker %s received signal %d, stopping...", self.worker_id, signum)
            self._running = False

        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)

        logger.info(
            "Worker %s starting (poll=%ds, batch=%d, lease=%ds)",
            self.worker_id,
            self.settings.worker_poll_interval_seconds,
            self.settings.worker_batch_size,
            self.settings.worker_lease_timeout_seconds,
        )

        while self._running:
            if max_iterations is not None and iteration >= max_iterations:
                break

            processed = self.poll_and_process()
            iteration += 1

            if processed == 0 and self._running:
                time.sleep(self.settings.worker_poll_interval_seconds)

        logger.info("Worker %s stopped after %d iterations", self.worker_id, iteration)

    def stop(self) -> None:
        """Signal the worker to stop."""
        self._running = False
