import asyncio

from app.adapters.outbound.claude_agent_sdk.backend import ClaudeAgentSdkBackend
from app.domain.models import ChatMessage, ChatRequest, Role


def _request(**overrides) -> ChatRequest:
    defaults = dict(
        model="claude-opus-4-8",
        messages=[ChatMessage(role=Role.USER, text="Hi")],
        max_tokens=256,
        system=None,
        stream=False,
        tools_requested=False,
        session_id=None,
    )
    defaults.update(overrides)
    return ChatRequest(**defaults)


class _FakeResolver:
    """Fakes SessionUuidResolver: known labels are pre-seeded, new labels get
    a deterministic incrementing uuid so assertions are easy to write."""

    def __init__(self, known: dict[str, str] | None = None):
        self._known = dict(known or {})
        self._next = 0
        self.touched: list[tuple[str, str]] = []
        self.resolve_delay_s = 0.0

    async def resolve_uuid(self, label: str) -> tuple[str, bool]:
        if self.resolve_delay_s:
            await asyncio.sleep(self.resolve_delay_s)
        if label in self._known:
            return self._known[label], False
        self._next += 1
        return f"new-uuid-{self._next}", True

    async def touch(self, label: str, *, uuid: str) -> None:
        self.touched.append((label, uuid))
        self._known[label] = uuid


def _backend(resolver, session_cwd="/tmp/fake-session-cwd") -> ClaudeAgentSdkBackend:
    return ClaudeAgentSdkBackend(
        disallowed_tools=[],
        max_concurrent_requests=2,
        queue_timeout_s=1,
        request_timeout_s=5,
        session_resolver=resolver,
        session_cwd=session_cwd,
    )


def _capture_collect_messages(backend, calls):
    async def fake_collect(prompt, options):
        calls.append((prompt, options))
        return []

    backend._collect_messages = fake_collect


async def test_new_session_label_sets_session_id_not_resume():
    resolver = _FakeResolver()
    backend = _backend(resolver)
    calls = []
    _capture_collect_messages(backend, calls)

    await backend._run_session(_request(session_id="demo-1"))

    (_, options), = calls
    assert options.session_id == "new-uuid-1"
    assert options.resume is None
    assert resolver.touched == [("demo-1", "new-uuid-1")]


async def test_known_session_label_sets_resume_and_uses_only_latest_message():
    resolver = _FakeResolver(known={"demo-1": "existing-uuid"})
    backend = _backend(resolver)
    calls = []
    _capture_collect_messages(backend, calls)

    request = _request(
        session_id="demo-1",
        messages=[
            ChatMessage(role=Role.USER, text="earlier turn, should be dropped"),
            ChatMessage(role=Role.ASSISTANT, text="reply"),
            ChatMessage(role=Role.USER, text="latest question"),
        ],
    )
    await backend._run_session(request)

    (prompt, options), = calls
    assert options.resume == "existing-uuid"
    assert options.session_id is None
    assert prompt == "latest question"


async def test_stateless_path_unaffected_by_session_support():
    backend = _backend(resolver=None, session_cwd=None)
    calls = []
    _capture_collect_messages(backend, calls)

    await backend._dispatch(_request(session_id=None))

    (_, options), = calls
    assert options.session_id is None
    assert options.resume is None
    assert "subclaude-" in str(options.cwd)


async def test_per_session_lock_serializes_concurrent_calls_to_same_label():
    resolver = _FakeResolver()
    resolver.resolve_delay_s = 0.02
    backend = _backend(resolver)
    order: list[str] = []

    async def fake_collect(prompt, options):
        order.append(f"start:{prompt}")
        await asyncio.sleep(0.01)
        order.append(f"end:{prompt}")
        return []

    backend._collect_messages = fake_collect

    request_a = _request(session_id="shared", messages=[ChatMessage(role=Role.USER, text="a")])
    request_b = _request(session_id="shared", messages=[ChatMessage(role=Role.USER, text="b")])
    await asyncio.gather(
        backend._run_session(request_a),
        backend._run_session(request_b),
    )

    # Serialized: one call's start+end must both appear before the other's start.
    assert order in (
        ["start:a", "end:a", "start:b", "end:b"],
        ["start:b", "end:b", "start:a", "end:a"],
    )
