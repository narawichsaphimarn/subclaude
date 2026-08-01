from typing import AsyncIterator

import pytest

from app.domain.errors import InvalidRequestError
from app.domain.models import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatStreamEvent,
    ChatStreamEventType,
    Role,
    StopReason,
    Usage,
)
from app.use_cases.send_message import SendMessageUseCase


def _default_response() -> ChatResponse:
    return ChatResponse(
        id="msg_1",
        model="claude-opus-4-8",
        text="hi",
        stop_reason=StopReason.END_TURN,
        usage=Usage(input_tokens=1, output_tokens=1),
    )


class _FakeBackend:
    """A hand-written ChatBackend, satisfying the Protocol structurally --
    no SDK, no subprocess, no HTTP."""

    def __init__(self) -> None:
        self.response = _default_response()
        self.received_requests: list[ChatRequest] = []

    async def complete(self, request: ChatRequest) -> ChatResponse:
        self.received_requests.append(request)
        return self.response

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamEvent]:
        self.received_requests.append(request)
        yield ChatStreamEvent(type=ChatStreamEventType.MESSAGE_START, message_id=self.response.id)
        yield ChatStreamEvent(type=ChatStreamEventType.TEXT_DELTA, text=self.response.text)
        yield ChatStreamEvent(
            type=ChatStreamEventType.MESSAGE_STOP, stop_reason=self.response.stop_reason
        )


def _request(**overrides) -> ChatRequest:
    defaults = dict(
        model="claude-opus-4-8",
        messages=[ChatMessage(role=Role.USER, text="hi")],
        max_tokens=100,
        system=None,
        stream=False,
        tools_requested=False,
    )
    defaults.update(overrides)
    return ChatRequest(**defaults)


async def test_execute_delegates_to_backend():
    backend = _FakeBackend()
    use_case = SendMessageUseCase(backend)
    response = await use_case.execute(_request())
    assert response is backend.response
    assert backend.received_requests == [_request()]


async def test_execute_rejects_tools_requested():
    use_case = SendMessageUseCase(_FakeBackend())
    with pytest.raises(InvalidRequestError):
        await use_case.execute(_request(tools_requested=True))


async def test_execute_rejects_empty_messages():
    use_case = SendMessageUseCase(_FakeBackend())
    with pytest.raises(InvalidRequestError):
        await use_case.execute(_request(messages=[]))


async def test_execute_rejects_last_message_not_user():
    use_case = SendMessageUseCase(_FakeBackend())
    messages = [
        ChatMessage(role=Role.USER, text="hi"),
        ChatMessage(role=Role.ASSISTANT, text="yo"),
    ]
    with pytest.raises(InvalidRequestError):
        await use_case.execute(_request(messages=messages))


async def test_execute_stream_yields_backend_events():
    use_case = SendMessageUseCase(_FakeBackend())
    events = [event async for event in use_case.execute_stream(_request())]
    assert [e.type for e in events] == [
        ChatStreamEventType.MESSAGE_START,
        ChatStreamEventType.TEXT_DELTA,
        ChatStreamEventType.MESSAGE_STOP,
    ]
