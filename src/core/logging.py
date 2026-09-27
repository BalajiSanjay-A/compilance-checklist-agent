"""Structured logging with automated secret and credential scrubbing."""

import logging
import re
import sys
from typing import Any

# Sensitive regex patterns to scrub from log messages
SCRUB_PATTERNS = [
    # Bearer tokens
    (re.compile(r"Bearer\s+([A-Za-z0-9\-_\.=]+)", re.IGNORECASE), "Bearer [REDACTED]"),
    # xAI API keys
    (re.compile(r"xai-[a-zA-Z0-9]{20,}", re.IGNORECASE), "xai-[REDACTED]"),
    # Generic password / secret / token key-value pairs
    (re.compile(r"(?i)\b(password|secret|token|api_key)\s*[:=]\s*['\"]?([^'\"\s,]+)['\"]?"), r"\1=[REDACTED]"),
]


class SecretScrubbingFilter(logging.Filter):
    """Log filter that intercepts and sanitizes sensitive credentials in records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.scrub_text(record.msg)
        if record.args:
            scrubbed_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    scrubbed_args.append(self.scrub_text(arg))
                else:
                    scrubbed_args.append(arg)
            record.args = tuple(scrubbed_args)
        return True

    @staticmethod
    def scrub_text(text: str) -> str:
        scrubbed = text
        for pattern, replacement in SCRUB_PATTERNS:
            scrubbed = pattern.sub(replacement, scrubbed)
        return scrubbed


def configure_logging(level: int = logging.INFO) -> None:
    """Configure system root logger with scrubbing filter and standardized format."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid duplicate handlers if already initialized
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        handler.setFormatter(formatter)
        handler.addFilter(SecretScrubbingFilter())
        root_logger.addHandler(handler)
    else:
        for handler in root_logger.handlers:
            handler.addFilter(SecretScrubbingFilter())


def get_logger(name: str) -> logging.Logger:
    """Return a named logger with security scrubbing filter applied."""
    logger = logging.getLogger(name)
    logger.addFilter(SecretScrubbingFilter())
    return logger
