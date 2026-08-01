from __future__ import annotations

from fastapi import Depends, FastAPI

from app.adapters.inbound.http.auth import make_verify_api_key
from app.adapters.inbound.http.error_handlers import register_error_handlers
from app.adapters.inbound.http.routes import router
from app.use_cases.manage_sessions import SessionManagementUseCase
from app.use_cases.send_message import SendMessageUseCase


def create_app(
    *,
    use_case: SendMessageUseCase,
    session_management_use_case: SessionManagementUseCase,
    proxy_api_keys: list[str],
    default_model: str | None = None,
) -> FastAPI:
    """Inbound adapter composition: wires already-constructed use cases, the
    proxy's own API-key list, and a fallback model id into a FastAPI app.
    All are stashed on app.state so route handlers can reach them without a
    global; see app/composition.py for how these dependencies get built.
    """
    app = FastAPI(title="subclaude", version="0.1.0")
    app.state.send_message_use_case = use_case
    app.state.session_management_use_case = session_management_use_case
    app.state.default_model = default_model

    verify_api_key = make_verify_api_key(proxy_api_keys)
    app.include_router(router, dependencies=[Depends(verify_api_key)])

    register_error_handlers(app)
    return app
