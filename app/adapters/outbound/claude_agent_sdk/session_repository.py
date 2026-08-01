from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from claude_agent_sdk import delete_session as sdk_delete_session

from app.domain.models import SessionSummary


class SessionUuidResolver(Protocol):
    """Adapter-local port: lets backend.py depend on a narrow structural
    type instead of the concrete JsonFileSessionRepository class."""

    async def resolve_uuid(self, label: str) -> tuple[str, bool]: ...  # (uuid, is_new)

    async def touch(self, label: str, *, uuid: str) -> None: ...


class JsonFileSessionRepository:
    """Maps caller-chosen session labels (from x-session-id) to the UUIDs
    claude_agent_sdk requires. The actual conversation transcript is NOT
    stored here -- the `claude` CLI already persists that to local disk on
    its own whenever session_id/resume is set, so this file only ever holds
    {label: {uuid, created_at, last_used_at}}.

    ponytail: this file grows by one row per distinct label ever seen and is
    never pruned automatically -- fine at personal-proxy scale, add TTL/
    cleanup if that changes.
    """

    def __init__(self, path: Path, *, session_cwd: str) -> None:
        self._path = path
        self._session_cwd = session_cwd
        self._lock = asyncio.Lock()

    async def resolve_uuid(self, label: str) -> tuple[str, bool]:
        async with self._lock:
            row = self._load().get(label)
        if row is not None:
            return row["uuid"], False
        return str(uuid.uuid4()), True

    async def touch(self, label: str, *, uuid: str) -> None:
        async with self._lock:
            data = self._load()
            now = datetime.now(timezone.utc).isoformat()
            existing = data.get(label)
            if existing is None:
                data[label] = {"uuid": uuid, "created_at": now, "last_used_at": now}
            else:
                existing["last_used_at"] = now
            self._save(data)

    async def list_sessions(self) -> list[SessionSummary]:
        async with self._lock:
            data = self._load()
        summaries = [
            SessionSummary(
                id=label,
                created_at=datetime.fromisoformat(row["created_at"]),
                last_used_at=datetime.fromisoformat(row["last_used_at"]),
            )
            for label, row in data.items()
        ]
        summaries.sort(key=lambda s: s.last_used_at, reverse=True)
        return summaries

    async def delete_session(self, session_id: str) -> bool:
        async with self._lock:
            data = self._load()
            row = data.pop(session_id, None)
            if row is None:
                return False
            self._save(data)
        try:
            await asyncio.to_thread(
                sdk_delete_session, row["uuid"], directory=self._session_cwd
            )
        except FileNotFoundError:
            pass
        return True

    def _load(self) -> dict[str, dict[str, str]]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text())
        except json.JSONDecodeError:
            return {}

    def _save(self, data: dict[str, dict[str, str]]) -> None:
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self._path)
