from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.adapters.inbound.http.auth import AuthenticationFailed
from app.domain.errors import (
    BackendAuthError,
    BackendTimeoutError,
    BackendUnavailableError,
    DomainError,
    InvalidRequestError,
    RateLimitedError,
    SessionNotFoundError,
)

logger = logging.getLogger(__name__)

_STATUS_AND_TYPE: dict[type[DomainError], tuple[int, str]] = {
    InvalidRequestError: (400, "invalid_request_error"),
    RateLimitedError: (429, "rate_limit_error"),
    BackendTimeoutError: (504, "api_error"),
    BackendAuthError: (500, "api_error"),
    BackendUnavailableError: (500, "api_error"),
    SessionNotFoundError: (404, "not_found_error"),
}


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AuthenticationFailed, _handle_authentication_failed)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(DomainError, _handle_domain_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)


async def _handle_authentication_failed(
    _request: Request, exc: AuthenticationFailed
) -> JSONResponse:
    # Bypasses FastAPI's default HTTPException handler, which would wrap
    # this in {"detail": ...} and break Anthropic wire compatibility.
    return _error_response(401, "authentication_error", str(exc.detail))


async def _handle_validation_error(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    return _error_response(400, "invalid_request_error", str(exc))


async def _handle_domain_error(_request: Request, exc: DomainError) -> JSONResponse:
    status_code, error_type = _STATUS_AND_TYPE.get(type(exc), (500, "api_error"))
    if status_code >= 500:
        logger.exception("domain error handling request", exc_info=exc)
    return _error_response(status_code, error_type, str(exc))


async def _handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error handling request", exc_info=exc)
    return _error_response(500, "api_error", "an unexpected error occurred")


def _error_response(status_code: int, error_type: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"type": "error", "error": {"type": error_type, "message": message}},
    )
