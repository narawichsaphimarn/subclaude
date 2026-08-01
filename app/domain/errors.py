class DomainError(Exception):
    """Base class for all domain-level errors."""


class InvalidRequestError(DomainError):
    """The caller's request violates a business rule (e.g. asked for tool use,
    sent an unsupported content block type, or an otherwise malformed
    conversation)."""


class BackendUnavailableError(DomainError):
    """The backing Claude process/subprocess failed to run or returned an
    error result."""


class BackendAuthError(DomainError):
    """The backing `claude` CLI is not authenticated — the user likely needs
    to run `claude login`."""


class BackendTimeoutError(DomainError):
    """The backing Claude call did not complete within the configured
    timeout."""


class RateLimitedError(DomainError):
    """Too many concurrent requests are already in flight against the
    backend."""


class SessionNotFoundError(DomainError):
    """No session exists for the given caller-chosen session id."""
