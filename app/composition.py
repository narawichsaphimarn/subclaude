from __future__ import annotations

from fastapi import FastAPI

from app.adapters.inbound.http.app import create_app
from app.adapters.outbound.claude_agent_sdk.backend import ClaudeAgentSdkBackend
from app.config import Settings
from app.use_cases.send_message import SendMessageUseCase


def build_app(settings: Settings | None = None) -> FastAPI:
    """Composition root: wires config -> ClaudeAgentSdkBackend ->
    SendMessageUseCase -> FastAPI app. This is the one module allowed to
    know about every layer at once -- domain, use_cases, and both adapters.
    """
    settings = settings or Settings()

    backend = ClaudeAgentSdkBackend(
        disallowed_tools=settings.disallowed_tools,
        max_concurrent_requests=settings.max_concurrent_requests,
        queue_timeout_s=settings.queue_timeout_s,
        request_timeout_s=settings.request_timeout_s,
    )
    use_case = SendMessageUseCase(backend)

    return create_app(
        use_case=use_case,
        proxy_api_keys=settings.proxy_api_keys_list,
        default_model=settings.default_model,
    )


# Entry point for `uvicorn app.composition:app`. Requires PROXY_API_KEYS to
# be set (env var or .env file) -- see .env.example.
app = build_app()
