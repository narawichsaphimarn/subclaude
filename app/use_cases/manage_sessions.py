from __future__ import annotations

from app.domain.errors import SessionNotFoundError
from app.domain.models import SessionSummary
from app.domain.ports import SessionRepository


class SessionManagementUseCase:
    """Application layer: list/delete sessions via whichever SessionRepository
    port implementation was wired in. Knows nothing about FastAPI or
    claude_agent_sdk -- mirrors SendMessageUseCase's shape.
    """

    def __init__(self, repository: SessionRepository) -> None:
        self._repository = repository

    async def list_sessions(self) -> list[SessionSummary]:
        return await self._repository.list_sessions()

    async def delete_session(self, session_id: str) -> None:
        if not await self._repository.delete_session(session_id):
            raise SessionNotFoundError(f"no session found for id {session_id!r}")
