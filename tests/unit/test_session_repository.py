from app.adapters.outbound.claude_agent_sdk.session_repository import (
    JsonFileSessionRepository,
)


def _repo(tmp_path):
    return JsonFileSessionRepository(
        tmp_path / "sessions.json", session_cwd=str(tmp_path / "cwd")
    )


async def test_resolve_uuid_returns_new_uuid_for_unknown_label(tmp_path):
    repo = _repo(tmp_path)
    uuid, is_new = await repo.resolve_uuid("demo-1")
    assert is_new is True
    assert uuid


async def test_resolve_uuid_is_stable_after_touch(tmp_path):
    repo = _repo(tmp_path)
    uuid, _ = await repo.resolve_uuid("demo-1")
    await repo.touch("demo-1", uuid=uuid)

    second_uuid, is_new = await repo.resolve_uuid("demo-1")
    assert is_new is False
    assert second_uuid == uuid


async def test_resolve_uuid_does_not_persist_until_touched(tmp_path):
    repo = _repo(tmp_path)
    await repo.resolve_uuid("demo-1")  # never touched -- simulates a crash mid-first-call

    _, is_new = await repo.resolve_uuid("demo-1")
    assert is_new is True  # still treated as brand new


async def test_touch_updates_last_used_at(tmp_path):
    repo = _repo(tmp_path)
    uuid, _ = await repo.resolve_uuid("demo-1")
    await repo.touch("demo-1", uuid=uuid)
    [first] = await repo.list_sessions()

    await repo.touch("demo-1", uuid=uuid)
    [second] = await repo.list_sessions()

    assert second.last_used_at >= first.last_used_at
    assert second.created_at == first.created_at


async def test_list_sessions_empty_by_default(tmp_path):
    repo = _repo(tmp_path)
    assert await repo.list_sessions() == []


async def test_delete_session_returns_false_for_unknown_label(tmp_path):
    repo = _repo(tmp_path)
    assert await repo.delete_session("nope") is False


async def test_delete_session_removes_known_label(tmp_path):
    repo = _repo(tmp_path)
    uuid, _ = await repo.resolve_uuid("demo-1")
    await repo.touch("demo-1", uuid=uuid)

    assert await repo.delete_session("demo-1") is True
    assert await repo.list_sessions() == []
