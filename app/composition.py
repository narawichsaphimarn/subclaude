from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from app.adapters.inbound.http.app import create_app
from app.adapters.outbound.claude_agent_sdk.backend import ClaudeAgentSdkBackend
from app.adapters.outbound.claude_agent_sdk.session_repository import (
    JsonFileSessionRepository,
)
from app.config import Settings
from app.use_cases.manage_sessions import SessionManagementUseCase
from app.use_cases.send_message import SendMessageUseCase


def build_app(settings: Settings | None = None) -> FastAPI:
    """Composition root: wires config -> adapters -> use cases -> FastAPI
    app. This is the one module allowed to know about every layer at once --
    domain, use_cases, and both adapters.
    """
    settings = settings or Settings()

    session_cwd = Path(settings.session_cwd).expanduser()
    session_cwd.mkdir(parents=True, exist_ok=True)
    session_store_path = Path(settings.session_store_path).expanduser()
    session_store_path.parent.mkdir(parents=True, exist_ok=True)
    session_repository = JsonFileSessionRepository(
        session_store_path, session_cwd=str(session_cwd)
    )

    backend = ClaudeAgentSdkBackend(
        disallowed_tools=settings.disallowed_tools,
        max_concurrent_requests=settings.max_concurrent_requests,
        queue_timeout_s=settings.queue_timeout_s,
        request_timeout_s=settings.request_timeout_s,
        session_resolver=session_repository,
        session_cwd=str(session_cwd),
    )
    use_case = SendMessageUseCase(backend)
    session_management_use_case = SessionManagementUseCase(session_repository)

    return create_app(
        use_case=use_case,
        session_management_use_case=session_management_use_case,
        proxy_api_keys=settings.proxy_api_keys_list,
        default_model=settings.default_model,
    )


# Entry point for `uvicorn app.composition:app`. Requires PROXY_API_KEYS to
# be set (env var or .env file) -- see .env.example.
app = build_app()
