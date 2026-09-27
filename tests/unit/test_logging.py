"""Unit tests for secret scrubbing in structured logging."""

import logging
from src.core.logging import SecretScrubbingFilter, configure_logging, get_logger


def test_secret_scrubbing_filter():
    """Verify passwords, tokens, and xAI keys are scrubbed."""
    msg = "User logged in with password='super_secret' and token=abc123xyz"
    scrubbed = SecretScrubbingFilter.scrub_text(msg)
    assert "super_secret" not in scrubbed
    assert "[REDACTED]" in scrubbed

    bearer_msg = "Request Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    scrubbed_bearer = SecretScrubbingFilter.scrub_text(bearer_msg)
    assert "Bearer [REDACTED]" in scrubbed_bearer

    xai_msg = "Connecting to xAI with key xai-1234567890abcdef1234567890"
    scrubbed_xai = SecretScrubbingFilter.scrub_text(xai_msg)
    assert "xai-[REDACTED]" in scrubbed_xai


def test_secret_scrubbing_record_filter():
    """Verify SecretScrubbingFilter on actual logging records and args."""
    log_filter = SecretScrubbingFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Secret token is token=%s",
        args=("sensitive_val",),
        exc_info=None,
    )
    assert log_filter.filter(record) is True
    assert "[REDACTED]" in record.msg or any("[REDACTED]" in str(a) for a in record.args)


def test_configure_logging_and_get_logger():
    """Verify configure_logging and get_logger add scrubbing filters."""
    configure_logging(level=logging.DEBUG)
    logger = get_logger("test_module")
    assert any(isinstance(f, SecretScrubbingFilter) for f in logger.filters)
