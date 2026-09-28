"""Unit tests for EvidenceService: validation, hashing, storage, text extraction."""

import hashlib
import os
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from src.config import Settings
from src.core.exceptions import (
    DocumentExtractionException,
    EntityNotFoundException,
    StorageException,
    ValidationException,
)
from src.database.models import (
    DocumentProcessingJob,
    DocumentType,
    EvidenceDocument,
    EvidenceValidity,
    ProcessingStatus,
)
from src.services.evidence_service import EvidenceService


# ── Filename sanitization ───────────────────────────────────────────────


class TestSanitizeFilename:
    def test_normal_filename(self):
        assert EvidenceService.sanitize_filename("report.pdf") == "report.pdf"

    def test_path_traversal_stripped(self):
        assert EvidenceService.sanitize_filename("../../etc/passwd") == "passwd"

    def test_special_chars_replaced(self):
        result = EvidenceService.sanitize_filename("my file (1).pdf")
        assert result == "my_file__1_.pdf"

    def test_windows_path_sanitized(self):
        result = EvidenceService.sanitize_filename("C:\\Users\\docs\\report.pdf")
        assert ".." not in result
        assert "/" not in result
        assert "\\" not in result

    def test_empty_after_sanitization_raises(self):
        with pytest.raises(ValidationException):
            EvidenceService.sanitize_filename("...")

    def test_dot_prefix_stripped(self):
        result = EvidenceService.sanitize_filename(".hidden.pdf")
        assert not result.startswith(".")


# ── Upload validation ───────────────────────────────────────────────────


class TestValidateUpload:
    @pytest.fixture
    def settings(self, tmp_path: Path) -> Settings:
        return Settings(
            app_env="test",
            use_sqlite_fallback=True,
            sqlite_db_path=":memory:",
            storage_dir=tmp_path / "evidence",
            max_upload_size_mb=25,
        )

    def test_valid_pdf(self, settings: Settings):
        result = EvidenceService.validate_upload("report.pdf", "application/pdf", 1024, settings)
        assert result == "report.pdf"

    def test_valid_txt(self, settings: Settings):
        result = EvidenceService.validate_upload("policy.txt", "text/plain", 500, settings)
        assert result == "policy.txt"

    def test_invalid_mime_type_raises(self, settings: Settings):
        with pytest.raises(ValidationException, match="not allowed"):
            EvidenceService.validate_upload("image.png", "image/png", 100, settings)

    def test_extension_mismatch_raises(self, settings: Settings):
        with pytest.raises(ValidationException, match="does not match"):
            EvidenceService.validate_upload("fake.exe", "application/pdf", 100, settings)

    def test_file_too_large_raises(self, settings: Settings):
        max_bytes = settings.max_upload_size_mb * 1024 * 1024
        with pytest.raises(ValidationException, match="exceeds maximum"):
            EvidenceService.validate_upload("big.pdf", "application/pdf", max_bytes + 1, settings)

    def test_exactly_max_size_passes(self, settings: Settings):
        max_bytes = settings.max_upload_size_mb * 1024 * 1024
        EvidenceService.validate_upload("exact.pdf", "application/pdf", max_bytes, settings)


# ── SHA-256 hashing ─────────────────────────────────────────────────────


class TestComputeFileHash:
    def test_known_hash(self):
        content = b"test content for hashing"
        expected = hashlib.sha256(content).hexdigest()
        assert EvidenceService.compute_file_hash(content) == expected

    def test_deterministic(self):
        content = b"same input"
        assert EvidenceService.compute_file_hash(content) == EvidenceService.compute_file_hash(content)

    def test_different_content_different_hash(self):
        assert EvidenceService.compute_file_hash(b"a") != EvidenceService.compute_file_hash(b"b")


# ── File storage ────────────────────────────────────────────────────────


class TestStoreFile:
    @pytest.fixture
    def settings(self, tmp_path: Path) -> Settings:
        return Settings(
            app_env="test",
            use_sqlite_fallback=True,
            sqlite_db_path=":memory:",
            storage_dir=tmp_path / "evidence",
        )

    def test_stores_with_sharded_path(self, settings: Settings):
        content = b"test content"
        file_hash = EvidenceService.compute_file_hash(content)
        rel_path = EvidenceService.store_file(content, file_hash, "report.pdf", settings)

        assert rel_path.startswith(f"{file_hash[:2]}/{file_hash[2:4]}/")
        abs_path = settings.storage_dir / rel_path
        assert abs_path.exists()
        assert abs_path.read_bytes() == content

    def test_file_permissions(self, settings: Settings):
        content = b"secret evidence"
        file_hash = EvidenceService.compute_file_hash(content)
        rel_path = EvidenceService.store_file(content, file_hash, "secret.txt", settings)

        abs_path = settings.storage_dir / rel_path
        mode = os.stat(abs_path).st_mode & 0o777
        assert mode == 0o600


# ── Text extraction ─────────────────────────────────────────────────────


class TestExtractText:
    def test_extract_plain_text(self, tmp_path: Path):
        txt_file = tmp_path / "policy.txt"
        txt_file.write_text("Access control policy: all users must use MFA.", encoding="utf-8")
        result = EvidenceService.extract_text(txt_file, "text/plain")
        assert "MFA" in result

    def test_extract_csv(self, tmp_path: Path):
        csv_file = tmp_path / "audit.csv"
        csv_file.write_text("date,event\n2026-01-01,login\n", encoding="utf-8")
        result = EvidenceService.extract_text(csv_file, "text/csv")
        assert "login" in result

    def test_extract_markdown(self, tmp_path: Path):
        md_file = tmp_path / "policy.md"
        md_file.write_text("# Security Policy\n\nAll systems require encryption.", encoding="utf-8")
        result = EvidenceService.extract_text(md_file, "text/markdown")
        assert "encryption" in result

    def test_unsupported_type_returns_none(self, tmp_path: Path):
        doc_file = tmp_path / "doc.docx"
        doc_file.write_bytes(b"fake docx")
        result = EvidenceService.extract_text(doc_file, "application/msword")
        assert result is None

    def test_empty_text_file_raises(self, tmp_path: Path):
        empty = tmp_path / "empty.txt"
        empty.write_text("", encoding="utf-8")
        with pytest.raises(DocumentExtractionException, match="no text"):
            EvidenceService.extract_text(empty, "text/plain")

    def test_extract_pdf(self, tmp_path: Path):
        from pypdf import PdfWriter
        from io import BytesIO

        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        page = writer.pages[0]
        from pypdf.generic import ArrayObject, ContentStream, NameObject, TextStringObject
        # Create a simple PDF with text content by writing to BytesIO then back
        buf = BytesIO()
        writer.write(buf)
        buf.seek(0)

        # Use a real PDF with actual text - create via reportlab alternative:
        # Since we only have pypdf, create a minimal PDF manually
        pdf_path = tmp_path / "test.pdf"
        pdf_bytes = _create_minimal_pdf_with_text("Evidence of MFA implementation verified.")
        pdf_path.write_bytes(pdf_bytes)

        result = EvidenceService.extract_text(pdf_path, "application/pdf")
        assert "MFA" in result

    def test_corrupt_pdf_raises(self, tmp_path: Path):
        bad_pdf = tmp_path / "corrupt.pdf"
        bad_pdf.write_bytes(b"not a real pdf")
        with pytest.raises(DocumentExtractionException):
            EvidenceService.extract_text(bad_pdf, "application/pdf")


def _create_minimal_pdf_with_text(text: str) -> bytes:
    """Create a minimal valid PDF containing the given text."""
    text_escaped = text.replace("(", "\\(").replace(")", "\\)")
    content = f"BT /F1 12 Tf 100 700 Td ({text_escaped}) Tj ET"
    stream_bytes = content.encode("latin-1")
    stream_length = len(stream_bytes)

    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        + f"4 0 obj\n<< /Length {stream_length} >>\nstream\n".encode("latin-1")
        + stream_bytes
        + b"\nendstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n"
    )
    # Simplified xref - pypdf is tolerant enough
    pdf += b"0000000000 65535 f \n"
    pdf += b"0000000009 00000 n \n"
    pdf += b"0000000058 00000 n \n"
    pdf += b"0000000115 00000 n \n"
    pdf += b"0000000300 00000 n \n"
    pdf += b"0000000500 00000 n \n"
    pdf += b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n0\n%%EOF\n"
    return pdf


# ── Validity status ─────────────────────────────────────────────────────


class TestComputeValidityStatus:
    def test_no_expiry_is_valid(self):
        assert EvidenceService.compute_validity_status(None, None, 30) == EvidenceValidity.VALID

    def test_expired(self):
        yesterday = date.today() - timedelta(days=1)
        assert EvidenceService.compute_validity_status(None, yesterday, 30) == EvidenceValidity.EXPIRED

    def test_expiring_soon(self):
        soon = date.today() + timedelta(days=15)
        assert EvidenceService.compute_validity_status(None, soon, 30) == EvidenceValidity.EXPIRING_SOON

    def test_far_future_is_valid(self):
        future = date.today() + timedelta(days=365)
        assert EvidenceService.compute_validity_status(None, future, 30) == EvidenceValidity.VALID

    def test_boundary_exactly_warning_days(self):
        boundary = date.today() + timedelta(days=30)
        assert EvidenceService.compute_validity_status(None, boundary, 30) == EvidenceValidity.EXPIRING_SOON


# ── Integration: upload_evidence with db_session ────────────────────────


class TestUploadEvidenceIntegration:
    @pytest.fixture
    def settings(self, tmp_path: Path) -> Settings:
        return Settings(
            app_env="test",
            use_sqlite_fallback=True,
            sqlite_db_path=":memory:",
            storage_dir=tmp_path / "evidence",
            max_upload_size_mb=25,
            expiration_warning_days=30,
        )

    def test_upload_txt_creates_document(self, db_session: Session, settings: Settings):
        content = b"MFA implementation policy document content."
        evidence = EvidenceService.upload_evidence(
            session=db_session,
            file_content=content,
            filename="policy.txt",
            content_type="text/plain",
            document_type=DocumentType.POLICY,
            uploaded_by=None,
            valid_from=None,
            expires_at=None,
            settings=settings,
        )
        assert evidence.id is not None
        assert evidence.filename == "policy.txt"
        assert evidence.processing_status == ProcessingStatus.PROCESSED
        assert evidence.content_text is not None
        assert "MFA" in evidence.content_text

    def test_upload_with_expiration(self, db_session: Session, settings: Settings):
        content = b"Certificate content"
        expires = date.today() - timedelta(days=5)
        evidence = EvidenceService.upload_evidence(
            session=db_session,
            file_content=content,
            filename="cert.txt",
            content_type="text/plain",
            document_type=DocumentType.CERTIFICATE,
            uploaded_by=None,
            valid_from=date.today() - timedelta(days=365),
            expires_at=expires,
            settings=settings,
        )
        assert evidence.validity_status == EvidenceValidity.EXPIRED

    def test_get_evidence_not_found(self, db_session: Session):
        with pytest.raises(EntityNotFoundException):
            EvidenceService.get_evidence(db_session, uuid.uuid4())

    def test_list_evidence_empty(self, db_session: Session):
        items, total = EvidenceService.list_evidence(db_session)
        assert items == []
        assert total == 0

    def test_list_evidence_with_filter(self, db_session: Session, settings: Settings):
        for dtype, name in [(DocumentType.POLICY, "pol.txt"), (DocumentType.AUDIT_LOG, "log.txt")]:
            EvidenceService.upload_evidence(
                session=db_session,
                file_content=f"Content for {name}".encode(),
                filename=name,
                content_type="text/plain",
                document_type=dtype,
                uploaded_by=None,
                valid_from=None,
                expires_at=None,
                settings=settings,
            )

        items, total = EvidenceService.list_evidence(
            db_session, document_type=DocumentType.POLICY
        )
        assert total == 1
        assert items[0].document_type == DocumentType.POLICY
