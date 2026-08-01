import httpx
from httpx import ASGITransport

from app.adapters.inbound.http.app import create_app
from app.domain.errors import BackendAuthError
from app.domain.models import (
    ChatResponse,
    ChatStreamEvent,
    ChatStreamEventType,
    StopReason,
    Usage,
)
from app.use_cases.send_message import SendMessageUseCase


def _default_response() -> ChatResponse:
    return ChatResponse(
        id="msg_123",
        model="claude-opus-4-8",
        text="Hello there!",
        stop_reason=StopReason.END_TURN,
        usage=Usage(input_tokens=5, output_tokens=3),
    )


class _FakeBackend:
    """Fakes the ChatBackend port at the HTTP boundary -- no SDK, no
    subprocess. Verifies routing, auth, error-envelope shape, and streaming
    vs. non-streaming branching only."""

    def __init__(self, response: ChatResponse | None = None, error: Exception | None = None):
        self._response = response
        self._error = error

    async def complete(self, request):
        if self._error:
            raise self._error
        return self._response

    async def stream(self, request):
        if self._error:
            raise self._error
        response = self._response
        yield ChatStreamEvent(
            type=ChatStreamEventType.MESSAGE_START, message_id=response.id, model=response.model
        )
        yield ChatStreamEvent(type=ChatStreamEventType.TEXT_DELTA, text=response.text)
        yield ChatStreamEvent(
            type=ChatStreamEventType.MESSAGE_STOP,
            stop_reason=response.stop_reason,
            usage=response.usage,
        )


def _make_client(backend) -> httpx.AsyncClient:
    app = create_app(
        use_case=SendMessageUseCase(backend),
        proxy_api_keys=["test-key"],
        default_model="claude-opus-4-8",
    )
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


_VALID_BODY = {
    "model": "claude-opus-4-8",
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "hi"}],
}


async def test_missing_api_key_returns_401():
    async with _make_client(_FakeBackend(_default_response())) as client:
        resp = await client.post("/v1/messages", json=_VALID_BODY)
    assert resp.status_code == 401
    assert resp.json()["error"]["type"] == "authentication_error"


async def test_valid_request_returns_anthropic_shaped_response():
    async with _make_client(_FakeBackend(_default_response())) as client:
        resp = await client.post(
            "/v1/messages", headers={"x-api-key": "test-key"}, json=_VALID_BODY
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "message"
    assert body["role"] == "assistant"
    assert body["content"] == [{"type": "text", "text": "Hello there!"}]
    assert body["stop_reason"] == "end_turn"
    assert body["usage"] == {"input_tokens": 5, "output_tokens": 3}


async def test_tools_in_request_returns_400_invalid_request_error():
    body = {**_VALID_BODY, "tools": [{"name": "get_weather"}]}
    async with _make_client(_FakeBackend(_default_response())) as client:
        resp = await client.post("/v1/messages", headers={"x-api-key": "test-key"}, json=body)
    assert resp.status_code == 400
    assert resp.json()["error"]["type"] == "invalid_request_error"


async def test_missing_required_field_returns_400_not_422():
    body = {"messages": [{"role": "user", "content": "hi"}]}  # no max_tokens
    async with _make_client(_FakeBackend(_default_response())) as client:
        resp = await client.post("/v1/messages", headers={"x-api-key": "test-key"}, json=body)
    assert resp.status_code == 400
    assert resp.json()["error"]["type"] == "invalid_request_error"


async def test_streaming_request_returns_anthropic_sse_sequence():
    body = {**_VALID_BODY, "stream": True}
    async with _make_client(_FakeBackend(_default_response())) as client:
        async with client.stream(
            "POST", "/v1/messages", headers={"x-api-key": "test-key"}, json=body
        ) as resp:
            assert resp.status_code == 200
            raw = b""
            async for chunk in resp.aiter_bytes():
                raw += chunk
    text = raw.decode()
    assert "event: message_start" in text
    assert "event: content_block_delta" in text
    assert "event: message_stop" in text
    assert text.index("event: message_start") < text.index("event: content_block_delta")
    assert text.index("event: content_block_delta") < text.index("event: message_stop")


async def test_backend_auth_error_maps_to_500_api_error():
    async with _make_client(_FakeBackend(error=BackendAuthError("not logged in"))) as client:
        resp = await client.post(
            "/v1/messages", headers={"x-api-key": "test-key"}, json=_VALID_BODY
        )
    assert resp.status_code == 500
    assert resp.json()["error"]["type"] == "api_error"
