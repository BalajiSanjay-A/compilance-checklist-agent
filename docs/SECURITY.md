# Security Model & Threat Mitigations

## 1. Threat Modeling (STRIDE)
- **Prompt Injection**: Mitigated by strict system/payload boundary tags, non-executable context, and deterministic quote verification. The LLM has zero direct database write permissions.
- **Path Traversal & Malicious Files**: Files are validated by MIME type and size ceiling (25 MB max). Basenames are sanitized using `pathlib.Path(name).name` with strict character set filtering. Files are saved in isolated storage with non-executable permissions (`0600`).
- **Data Tampering**: SHA-256 integrity hashing on upload.
- **Improper Authorization**: Early authentication boundaries; role-based access control (`compliance-officer`, `admin`, `auditor`) enforced via FastAPI dependency injection.
- **Secret Leakage**: Automatic scrubbing filter in application logger masks API keys, passwords, and sensitive tokens.

## 2. Evidence Expiration & Life-Cycle
- Separately models evidence validity (`VALID`, `EXPIRING_SOON`, `EXPIRED`) from compliance status (`SATISFIED`, `PARTIAL`, `GAP`).
- Configurable warning window: `EXPIRATION_WARNING_DAYS=30`.
- Deterministic expiration engine prevents stale evidence from satisfying compliance controls.
