"""Domain exception hierarchy for the compliance automation agent."""

from typing import Any, Optional


class ComplianceException(Exception):
    """Base domain exception for all compliance agent errors."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class EntityNotFoundException(ComplianceException):
    """Raised when a requested resource is not found."""


class DuplicateEntityException(ComplianceException):
    """Raised when an entity violates uniqueness constraints."""


class ValidationException(ComplianceException):
    """Raised when domain or schema validation fails."""


class AuthenticationException(ComplianceException):
    """Raised when credentials or tokens are invalid or missing."""


class AuthorizationException(ComplianceException):
    """Raised when an authenticated user lacks required permissions or role."""


class StorageException(ComplianceException):
    """Raised when file storage or retrieval operations fail."""


class DocumentExtractionException(ComplianceException):
    """Raised when parsing or extracting text from a document fails."""


class AIProviderException(ComplianceException):
    """Raised when calls to the LLM provider encounter an error."""


class JobQueueException(ComplianceException):
    """Raised when job queueing or lease locking fails."""
