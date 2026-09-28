# Security Model & Threat Mitigations

## 1. Threat Modeling (STRIDE)
- **Prompt Injection**: Mitigated by strict system/payload boundary tags, non-executable context, and deterministic quote verification. The LLM has zero direct database write permissions.
- **Path Traversal & Malicious Files**: Files are validated by MIME type and size ceiling (25 MB max). Basenames are sanitized using `pathlib.Path(name).name` with strict character set filtering. Files are saved in isolated storage with non-executable permissions (`0600`).
- **Data Tampering**: SHA-256 integrity hashing on upload.
- **Improper Authorization**: Early authentication boundaries; role-based access control (`compliance-officer`, `admin`, `auditor`) enforced via FastAPI dependency injection.
- **Credential Stuffing**: Constant-time rejection for nonexistent users (dummy bcrypt hash is verified to prevent timing side channels).
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

## 4. Authentication & JWT Flow (Module 8)
- **Login**: `POST /auth/login` accepts username/password, verifies credentials against bcrypt-hashed passwords in the database, and returns a signed HS256 JWT.
- **Token payload**: `sub` (username), `role`, `user_id`, `exp` (configurable expiry, default 60 minutes).
- **Stateless verification**: `get_current_user` dependency decodes and validates the JWT on each request. No per-request database lookup (standard stateless JWT pattern).
- **Dev/test bypass**: In `development` or `test` mode, `X-Dev-Role` and `X-Dev-User` headers are accepted for fast integration testing without token issuance.
- **RBAC enforcement**: `require_role()` dependency factory checks the user's role from the token against allowed roles. Three roles: `compliance-officer` (writes), `auditor` (reads), `admin` (user management).
- **Password security**: bcrypt hashing with auto-generated salt, input truncated to 72 bytes (bcrypt limit). Minimum 8-character password policy enforced at creation and change.
- **Constant-time rejection**: Authentication of nonexistent users still performs a dummy bcrypt verification to prevent timing-based username enumeration.

## 5. CORS Policy (Module 10 Hardening)
- **Production**: Origins restricted to `CORS_ALLOWED_ORIGINS` environment variable (comma-separated). Credentials only allowed when explicit origins are configured.
- **Dev/test**: Wildcard `*` origins with `allow_credentials=False` — browsers will not send cookies or auth headers cross-origin in dev mode.
- **Rationale**: The combination of `allow_origins=["*"]` + `allow_credentials=True` is explicitly forbidden by the CORS specification and was corrected in Module 10.

## 6. E2E Security Verification (Module 10)
- End-to-end test confirms unauthenticated requests are rejected (401) across all protected endpoint categories.
- RBAC enforcement verified: auditor cannot trigger evaluations (403), only officer/admin can write.
- Expired evidence always resolves to GAP regardless of LLM output — deterministic override verified in E2E test.
- No secrets tracked in git (verified: `.env`, `*.db`, `storage/` all excluded by `.gitignore`).
