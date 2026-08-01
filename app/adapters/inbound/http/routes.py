from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.adapters.inbound.http.schemas import MessagesRequest, MessagesResponse
from app.adapters.inbound.http.sse import encode_stream
from app.use_cases.send_message import SendMessageUseCase

router = APIRouter()


def get_use_case(request: Request) -> SendMessageUseCase:
    return request.app.state.send_message_use_case


@router.post("/v1/messages", response_model=None)
async def create_message(
    payload: MessagesRequest,
    request: Request,
    use_case: SendMessageUseCase = Depends(get_use_case),
):
    domain_request = payload.to_domain(default_model=request.app.state.default_model)
    if domain_request.stream:
        return StreamingResponse(
            encode_stream(use_case.execute_stream(domain_request)),
            media_type="text/event-stream",
        )
    response = await use_case.execute(domain_request)
    return MessagesResponse.from_domain(response)
