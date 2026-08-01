from __future__ import annotations

from typing import AsyncIterator, Protocol

from app.domain.models import ChatRequest, ChatResponse, ChatStreamEvent


class ChatBackend(Protocol):
    """Driven port: anything that can turn a validated ChatRequest into a
    ChatResponse (or a stream of ChatStreamEvents). Implemented by the
    claude_agent_sdk outbound adapter; consumed by SendMessageUseCase.
    """

    async def complete(self, request: ChatRequest) -> ChatResponse: ...

    def stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamEvent]: ...
