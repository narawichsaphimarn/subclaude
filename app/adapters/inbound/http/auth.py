from __future__ import annotations

import secrets
from typing import Callable, Coroutine

from fastapi import Header, HTTPException


class AuthenticationFailed(HTTPException):
    """Raised by verify_api_key on a missing/invalid key. Deliberately a
    distinct class (not a bare HTTPException) so error_handlers.py can
    register a specific handler that returns the Anthropic-shaped error
    envelope directly -- FastAPI's default HTTPException handler wraps
    `detail` inside `{"detail": ...}`, which would break wire compatibility.
    """

    def __init__(self) -> None:
        super().__init__(status_code=401, detail="invalid or missing API key")


def make_verify_api_key(valid_keys: list[str]) -> Callable[..., Coroutine[None, None, None]]:
    """Build a FastAPI dependency bound to this app's configured API keys.

    Accepts either the `x-api-key` header (so any Anthropic SDK client works
    against this proxy with zero code changes -- just set ANTHROPIC_BASE_URL
    + ANTHROPIC_API_KEY) or a standard `Authorization: Bearer <token>`
    header for callers that prefer that convention.
    """

    async def verify_api_key(
        x_api_key: str | None = Header(default=None, alias="x-api-key"),
        authorization: str | None = Header(default=None),
    ) -> None:
        provided = x_api_key or _bearer_token(authorization)
        if provided is None or not _is_valid(provided, valid_keys):
            raise AuthenticationFailed()

    return verify_api_key


def _bearer_token(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[len("bearer "):].strip()
    return None


def _is_valid(provided: str, valid_keys: list[str]) -> bool:
    return any(secrets.compare_digest(provided, key) for key in valid_keys)
