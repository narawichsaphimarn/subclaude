from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.responses import StreamingResponse

from app.adapters.inbound.http.schemas import (
    MessagesRequest,
    MessagesResponse,
    SessionListResponse,
)
from app.adapters.inbound.http.sse import encode_stream
from app.use_cases.manage_sessions import SessionManagementUseCase
from app.use_cases.send_message import SendMessageUseCase

router = APIRouter()


def get_use_case(request: Request) -> SendMessageUseCase:
    return request.app.state.send_message_use_case


def get_session_use_case(request: Request) -> SessionManagementUseCase:
    return request.app.state.session_management_use_case


@router.post("/v1/messages", response_model=None)
async def create_message(
    payload: MessagesRequest,
    request: Request,
    use_case: SendMessageUseCase = Depends(get_use_case),
    x_session_id: str | None = Header(default=None, alias="x-session-id"),
):
    domain_request = payload.to_domain(
        default_model=request.app.state.default_model, session_id=x_session_id
    )
    if domain_request.stream:
        return StreamingResponse(
            encode_stream(use_case.execute_stream(domain_request)),
            media_type="text/event-stream",
        )
    response = await use_case.execute(domain_request)
    return MessagesResponse.from_domain(response)


@router.get("/v1/sessions", response_model=SessionListResponse)
async def list_sessions(
    use_case: SessionManagementUseCase = Depends(get_session_use_case),
):
    return SessionListResponse.from_domain(await use_case.list_sessions())


@router.delete("/v1/sessions/{session_id}", status_code=204, response_model=None)
async def delete_session(
    session_id: str,
    use_case: SessionManagementUseCase = Depends(get_session_use_case),
):
    await use_case.delete_session(session_id)
    return Response(status_code=204)
