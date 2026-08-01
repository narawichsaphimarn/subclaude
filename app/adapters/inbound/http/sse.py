from __future__ import annotations

import json
from typing import AsyncIterator

from app.domain.models import ChatStreamEvent, ChatStreamEventType


async def encode_stream(events: AsyncIterator[ChatStreamEvent]) -> AsyncIterator[bytes]:
    """Expand the domain's minimal ChatStreamEvent sequence into the full
    Anthropic SSE event sequence: message_start -> content_block_start ->
    content_block_delta(s) -> content_block_stop -> message_delta ->
    message_stop. This wire-format expansion is deliberately kept out of the
    domain layer -- see domain/models.py's ChatStreamEvent docstring.
    """
    async for event in events:
        for chunk in _expand(event):
            yield chunk


def _sse(event_name: str, data: dict) -> bytes:
    return f"event: {event_name}\ndata: {json.dumps(data)}\n\n".encode()


def _expand(event: ChatStreamEvent) -> list[bytes]:
    if event.type is ChatStreamEventType.MESSAGE_START:
        return _expand_start(event)
    if event.type is ChatStreamEventType.TEXT_DELTA:
        return _expand_delta(event)
    return _expand_stop(event)


def _expand_start(event: ChatStreamEvent) -> list[bytes]:
    return [
        _sse(
            "message_start",
            {
                "type": "message_start",
                "message": {
                    "id": event.message_id,
                    "type": "message",
                    "role": "assistant",
                    "content": [],
                    "model": event.model,
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {"input_tokens": 0, "output_tokens": 0},
                },
            },
        ),
        _sse(
            "content_block_start",
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            },
        ),
    ]


def _expand_delta(event: ChatStreamEvent) -> list[bytes]:
    return [
        _sse(
            "content_block_delta",
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": event.text or ""},
            },
        )
    ]


def _expand_stop(event: ChatStreamEvent) -> list[bytes]:
    usage = event.usage
    return [
        _sse("content_block_stop", {"type": "content_block_stop", "index": 0}),
        _sse(
            "message_delta",
            {
                "type": "message_delta",
                "delta": {
                    "stop_reason": event.stop_reason.value if event.stop_reason else None,
                    "stop_sequence": None,
                },
                "usage": {"output_tokens": usage.output_tokens if usage else 0},
            },
        ),
        _sse("message_stop", {"type": "message_stop"}),
    ]
