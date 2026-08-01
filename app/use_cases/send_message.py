from __future__ import annotations

from typing import AsyncIterator

from app.domain.errors import InvalidRequestError
from app.domain.models import ChatRequest, ChatResponse, ChatStreamEvent, Role
from app.domain.ports import ChatBackend


class SendMessageUseCase:
    """Application layer: validates business rules on a ChatRequest, then
    delegates to whichever ChatBackend port implementation was wired in.
    Knows nothing about FastAPI, SSE, or claude_agent_sdk -- that isolation
    is the point of the hexagonal split.
    """

    def __init__(self, backend: ChatBackend) -> None:
        self._backend = backend

    async def execute(self, request: ChatRequest) -> ChatResponse:
        self._validate(request)
        return await self._backend.complete(request)

    async def execute_stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamEvent]:
        self._validate(request)
        async for event in self._backend.stream(request):
            yield event

    @staticmethod
    def _validate(request: ChatRequest) -> None:
        if request.tools_requested:
            raise InvalidRequestError(
                "this proxy does not support tool use; remove `tools`/`tool_choice` "
                "from the request"
            )
        if not request.messages:
            raise InvalidRequestError("`messages` must contain at least one message")
        if request.messages[-1].role is not Role.USER:
            raise InvalidRequestError('the last message must have role "user"')
