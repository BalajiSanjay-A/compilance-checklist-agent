# Security Model & Threat Mitigations

## 1. Threat Modeling (STRIDE)
- **Prompt Injection**: Mitigated by strict system/payload boundary tags, non-executable context, and deterministic quote verification. The LLM has zero direct database write permissions.
- **Path Traversal & Malicious Files**: Files are validated by MIME type and size ceiling (25 MB max). Basenames are sanitized using `pathlib.Path(name).name` with strict character set filtering. Files are saved in isolated storage with non-executable permissions (`0600`).
- **Data Tampering**: SHA-256 integrity hashing on upload.
- **Improper Authorization**: Early authentication boundaries; role-based access control (`compliance-officer`, `admin`, `auditor`) enforced via FastAPI dependency injection.
- **Secret Leakage**: Automatic scrubbing filter in application logger masks API keys, passwords, and sensitive tokens.

## 2. Evidence Upload Security (Module 3)
- **MIME allowlist**: `application/pdf`, `text/plain`, `text/markdown`, `text/csv`. Rejections return HTTP 422.
- **Extension cross-validation**: File extension must match the declared MIME type.
- **Size limit**: `max_upload_size_mb` (default 25 MB) enforced before processing.
- **Filename sanitization**: `pathlib.Path(name).name` strips directory components; regex `[^a-zA-Z0-9._-]` replaces unsafe characters; leading dots stripped; empty result rejected.
- **Hash-based storage**: Files stored at `{storage_dir}/{hash[:2]}/{hash[2:4]}/{hash}_{sanitized_name}` — no user-controlled paths reach the filesystem.
- **File permissions**: `0600` via `os.chmod()` on stored files.
- **SHA-256 integrity**: Hash computed from raw bytes on upload, stored for deduplication and integrity verification.
- **Duplicate detection**: Existing hash logged as warning; does not block upload (same document may apply to different requirements/timeframes).

## 3. Evidence Expiration & Life-Cycle
- Separately models evidence validity (`VALID`, `EXPIRING_SOON`, `EXPIRED`) from compliance status (`SATISFIED`, `PARTIAL`, `GAP`).
- Configurable warning window: `EXPIRATION_WARNING_DAYS=30`.
- Deterministic expiration engine prevents stale evidence from satisfying compliance controls.
