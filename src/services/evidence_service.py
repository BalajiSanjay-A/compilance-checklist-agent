"""Evidence ingestion, secure storage, hashing, and text extraction service."""

import hashlib
import os
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config import Settings
from src.core.exceptions import (
    DocumentExtractionException,
    EntityNotFoundException,
    StorageException,
    ValidationException,
)
from src.core.logging import get_logger
from src.database.models import (
    DocumentProcessingJob,
    DocumentType,
    EvidenceDocument,
    EvidenceValidity,
    JobStatus,
    ProcessingStatus,
)

logger = get_logger("service.evidence")

ALLOWED_EXTENSIONS: dict[str, list[str]] = {
    "application/pdf": [".pdf"],
    "text/plain": [".txt", ".text", ".log"],
    "text/markdown": [".md", ".markdown"],
    "text/csv": [".csv"],
}

ALLOWED_MIME_TYPES = set(ALLOWED_EXTENSIONS.keys())

_SAFE_FILENAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")


class EvidenceService:
    """Service handling evidence upload, storage, hashing, and text extraction."""

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize uploaded filename to prevent path traversal and injection."""
        basename = Path(filename).name
        sanitized = re.sub(r"[^a-zA-Z0-9._-]", "_", basename)
        sanitized = sanitized.strip("._-")
        if not sanitized:
            raise ValidationException(
                "Invalid filename: empty after sanitization.",
                details={"original_filename": filename},
            )
        return sanitized

    @staticmethod
    def validate_upload(filename: str, content_type: str, file_size: int, settings: Settings) -> str:
        """Validate file upload constraints. Returns sanitized filename."""
        sanitized = EvidenceService.sanitize_filename(filename)

        ext = Path(sanitized).suffix.lower()
        if content_type not in ALLOWED_MIME_TYPES:
            raise ValidationException(
                f"File type '{content_type}' is not allowed.",
                details={"allowed": sorted(ALLOWED_MIME_TYPES), "received": content_type},
            )

        allowed_exts = ALLOWED_EXTENSIONS.get(content_type, [])
        if allowed_exts and ext not in allowed_exts:
            raise ValidationException(
                f"File extension '{ext}' does not match content type '{content_type}'.",
                details={"expected_extensions": allowed_exts, "received": ext},
            )

        max_bytes = settings.max_upload_size_mb * 1024 * 1024
        if file_size > max_bytes:
            raise ValidationException(
                f"File size {file_size} bytes exceeds maximum {settings.max_upload_size_mb} MB.",
                details={"max_bytes": max_bytes, "received_bytes": file_size},
            )

        return sanitized

    @staticmethod
    def compute_file_hash(content: bytes) -> str:
        """Compute SHA-256 hash of file content."""
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def store_file(content: bytes, file_hash: str, sanitized_filename: str, settings: Settings) -> str:
        """Store file to disk with hash-based sharding and restricted permissions.

        Returns the storage path relative to settings.storage_dir.
        """
        sub_dir = Path(file_hash[:2]) / file_hash[2:4]
        storage_dir = settings.storage_dir / sub_dir
        unique_name = f"{file_hash}_{sanitized_filename}"
        abs_path = storage_dir / unique_name
        rel_path = str(sub_dir / unique_name)

        try:
            storage_dir.mkdir(parents=True, exist_ok=True)
            abs_path.write_bytes(content)
            os.chmod(abs_path, 0o600)
        except OSError as exc:
            raise StorageException(
                f"Failed to store evidence file: {exc}",
                details={"path": rel_path},
            )

        logger.info("Stored evidence file: %s (%d bytes)", rel_path, len(content))
        return rel_path

    @staticmethod
    def extract_text(file_path: Path, content_type: str) -> Optional[str]:
        """Extract text from supported document types.

        Returns extracted text or None for unsupported types.
        Raises DocumentExtractionException on failure.
        """
        if content_type == "application/pdf":
            return EvidenceService._extract_pdf_text(file_path)
        elif content_type in ("text/plain", "text/markdown", "text/csv"):
            return EvidenceService._extract_plain_text(file_path)
        return None

    @staticmethod
    def _extract_pdf_text(file_path: Path) -> str:
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            result = "\n".join(pages)
            if not result.strip():
                raise DocumentExtractionException(
                    "PDF contains no extractable text.",
                    details={"path": str(file_path)},
                )
            return result
        except DocumentExtractionException:
            raise
        except Exception as exc:
            raise DocumentExtractionException(
                f"Failed to extract text from PDF: {exc}",
                details={"path": str(file_path)},
            )

    @staticmethod
    def _extract_plain_text(file_path: Path) -> str:
        try:
            text = file_path.read_text(encoding="utf-8")
            if not text.strip():
                raise DocumentExtractionException(
                    "Document contains no text content.",
                    details={"path": str(file_path)},
                )
            return text
        except DocumentExtractionException:
            raise
        except Exception as exc:
            raise DocumentExtractionException(
                f"Failed to read text file: {exc}",
                details={"path": str(file_path)},
            )

    @staticmethod
    def compute_validity_status(
        valid_from: Optional[date],
        expires_at: Optional[date],
        warning_days: int,
    ) -> EvidenceValidity:
        """Determine evidence validity status based on dates."""
        if expires_at is None:
            return EvidenceValidity.VALID
        today = date.today()
        if expires_at < today:
            return EvidenceValidity.EXPIRED
        days_until_expiry = (expires_at - today).days
        if days_until_expiry <= warning_days:
            return EvidenceValidity.EXPIRING_SOON
        return EvidenceValidity.VALID

    @staticmethod
    def check_duplicate_hash(session: Session, file_hash: str) -> Optional[uuid.UUID]:
        """Check if a document with same hash already exists. Returns existing ID or None."""
        existing = session.scalars(
            select(EvidenceDocument.id).where(EvidenceDocument.file_hash == file_hash)
        ).first()
        return existing

    @staticmethod
    def upload_evidence(
        session: Session,
        file_content: bytes,
        filename: str,
        content_type: str,
        document_type: DocumentType,
        uploaded_by: Optional[uuid.UUID],
        valid_from: Optional[date],
        expires_at: Optional[date],
        settings: Settings,
    ) -> EvidenceDocument:
        """Process and store an evidence document upload."""
        sanitized = EvidenceService.validate_upload(filename, content_type, len(file_content), settings)
        file_hash = EvidenceService.compute_file_hash(file_content)

        existing_id = EvidenceService.check_duplicate_hash(session, file_hash)
        if existing_id:
            logger.warning("Duplicate evidence hash detected: %s (existing: %s)", file_hash, existing_id)

        storage_path = EvidenceService.store_file(file_content, file_hash, sanitized, settings)
        abs_path = settings.storage_dir / storage_path

        validity_status = EvidenceService.compute_validity_status(
            valid_from, expires_at, settings.expiration_warning_days
        )

        content_text = None
        processing_status = ProcessingStatus.UPLOADED
        processing_error = None

        try:
            extracted = EvidenceService.extract_text(abs_path, content_type)
            if extracted is not None:
                content_text = extracted
                processing_status = ProcessingStatus.PROCESSED
            else:
                processing_status = ProcessingStatus.QUEUED
        except DocumentExtractionException as exc:
            processing_status = ProcessingStatus.FAILED
            processing_error = exc.message
            logger.warning("Text extraction failed for %s: %s", sanitized, exc.message)

        evidence = EvidenceDocument(
            filename=sanitized,
            document_type=document_type,
            storage_path=storage_path,
            content_text=content_text,
            file_hash=file_hash,
            file_size_bytes=len(file_content),
            uploaded_by=uploaded_by,
            uploaded_at=datetime.now(timezone.utc),
            valid_from=valid_from,
            expires_at=expires_at,
            validity_status=validity_status,
            processing_status=processing_status,
            processing_error=processing_error,
        )
        session.add(evidence)
        session.flush()

        if processing_status == ProcessingStatus.QUEUED:
            job = DocumentProcessingJob(
                evidence_id=evidence.id,
                job_type="EXTRACT_TEXT",
                status=JobStatus.QUEUED,
            )
            session.add(job)
            session.flush()
            logger.info("Created extraction job for evidence [%s]", evidence.id)

        logger.info(
            "Uploaded evidence '%s' [%s] hash=%s status=%s",
            sanitized, evidence.id, file_hash[:12], processing_status.value,
        )
        return evidence

    @staticmethod
    def get_evidence(session: Session, evidence_id: uuid.UUID) -> EvidenceDocument:
        """Retrieve evidence document by ID."""
        doc = session.get(EvidenceDocument, evidence_id)
        if not doc:
            raise EntityNotFoundException(
                f"Evidence document with ID '{evidence_id}' not found.",
                details={"evidence_id": str(evidence_id)},
            )
        return doc

    @staticmethod
    def list_evidence(
        session: Session,
        document_type: Optional[DocumentType] = None,
        validity_status: Optional[EvidenceValidity] = None,
        processing_status: Optional[ProcessingStatus] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[EvidenceDocument], int]:
        """List evidence documents with optional filters and pagination."""
        base_stmt = select(EvidenceDocument)

        if document_type is not None:
            base_stmt = base_stmt.where(EvidenceDocument.document_type == document_type)
        if validity_status is not None:
            base_stmt = base_stmt.where(EvidenceDocument.validity_status == validity_status)
        if processing_status is not None:
            base_stmt = base_stmt.where(EvidenceDocument.processing_status == processing_status)

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = session.scalar(count_stmt) or 0

        offset = (page - 1) * page_size
        paginated = (
            base_stmt.order_by(EvidenceDocument.uploaded_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list(session.scalars(paginated).all())
        return items, total
