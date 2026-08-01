import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

from app.adapters.outbound.claude_agent_sdk.response_mapper import (
    build_response,
    to_stream_events,
)
from app.domain.errors import BackendAuthError, BackendUnavailableError
from app.domain.models import ChatResponse, ChatStreamEventType, StopReason, Usage


def _result_message(**overrides) -> ResultMessage:
    defaults = dict(
        subtype="success",
        duration_ms=100,
        duration_api_ms=90,
        is_error=False,
        num_turns=1,
        session_id="sess_1",
    )
    defaults.update(overrides)
    return ResultMessage(**defaults)


def test_build_response_prefers_real_usage_from_assistant_message():
    assistant = AssistantMessage(
        content=[TextBlock(text="Hello!")],
        model="claude-opus-4-8",
        usage={"input_tokens": 12, "output_tokens": 3},
        stop_reason="end_turn",
        message_id="msg_real123",
    )
    response = build_response(
        [assistant, _result_message()],
        fallback_model="claude-sonnet-5",
        requested_max_tokens=1024,
    )

    assert response.id == "msg_real123"
    assert response.model == "claude-opus-4-8"
    assert response.text == "Hello!"
    assert response.stop_reason is StopReason.END_TURN
    assert response.usage.input_tokens == 12
    assert response.usage.output_tokens == 3
    assert response.usage.is_estimated is False


def test_build_response_falls_back_to_estimate_when_no_usage_available():
    assistant = AssistantMessage(content=[TextBlock(text="hi")], model="claude-opus-4-8")
    response = build_response(
        [assistant, _result_message()],
        fallback_model="claude-opus-4-8",
        requested_max_tokens=1024,
    )
    assert response.usage.is_estimated is True


def test_build_response_truncates_when_over_max_tokens():
    long_text = "word " * 500
    assistant = AssistantMessage(
        content=[TextBlock(text=long_text)],
        model="claude-opus-4-8",
        usage={"input_tokens": 5, "output_tokens": 500},
    )
    response = build_response(
        [assistant, _result_message()],
        fallback_model="claude-opus-4-8",
        requested_max_tokens=50,
    )
    assert response.stop_reason is StopReason.MAX_TOKENS
    assert len(response.text) < len(long_text)


def test_build_response_raises_backend_auth_error_on_authentication_failed():
    assistant = AssistantMessage(content=[], model="claude-opus-4-8", error="authentication_failed")
    with pytest.raises(BackendAuthError):
        build_response([assistant], fallback_model="claude-opus-4-8", requested_max_tokens=100)


def test_build_response_raises_backend_unavailable_when_result_is_error():
    assistant = AssistantMessage(content=[TextBlock(text="partial")], model="claude-opus-4-8")
    result = _result_message(is_error=True, subtype="error_during_execution", errors=["boom"])
    with pytest.raises(BackendUnavailableError):
        build_response(
            [assistant, result], fallback_model="claude-opus-4-8", requested_max_tokens=100
        )


def test_to_stream_events_produces_start_delta_stop_sequence():
    response = ChatResponse(
        id="msg_1",
        model="claude-opus-4-8",
        text="hi",
        stop_reason=StopReason.END_TURN,
        usage=Usage(input_tokens=1, output_tokens=1),
    )
    events = to_stream_events(response)
    assert [e.type for e in events] == [
        ChatStreamEventType.MESSAGE_START,
        ChatStreamEventType.TEXT_DELTA,
        ChatStreamEventType.MESSAGE_STOP,
    ]
    assert events[1].text == "hi"
