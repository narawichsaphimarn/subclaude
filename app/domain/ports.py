from __future__ import annotations

from typing import AsyncIterator, Protocol

from app.domain.models import ChatRequest, ChatResponse, ChatStreamEvent, SessionSummary


class ChatBackend(Protocol):
    """Driven port: anything that can turn a validated ChatRequest into a
    ChatResponse (or a stream of ChatStreamEvents). Implemented by the
    claude_agent_sdk outbound adapter; consumed by SendMessageUseCase.
    """

    async def complete(self, request: ChatRequest) -> ChatResponse: ...

    def stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamEvent]: ...


class SessionRepository(Protocol):
    """Driven port: label-keyed session lifecycle management for the
    /v1/sessions endpoints. Distinct from ChatBackend, which handles chat-turn
    dispatch -- this only lists/deletes.
    """

    async def list_sessions(self) -> list[SessionSummary]: ...

    async def delete_session(self, session_id: str) -> bool:
        """Returns False if session_id is an unknown label."""
        ...
