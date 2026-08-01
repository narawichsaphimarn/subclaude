from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    text: str


@dataclass(frozen=True)
class ChatRequest:
    model: str
    messages: list[ChatMessage]
    max_tokens: int
    system: str | None = None
    stream: bool = False
    # True if the caller's wire request included `tools` and/or `tool_choice`.
    # This proxy is chat-only for v1; the use case rejects such requests.
    tools_requested: bool = False


class StopReason(str, Enum):
    END_TURN = "end_turn"
    MAX_TOKENS = "max_tokens"


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int
    # True when input/output_tokens are a character-count estimate rather than
    # a real count from the backing Claude process. Logged loudly by the
    # outbound adapter so an estimate is never silently mistaken for a real count.
    is_estimated: bool = False


@dataclass(frozen=True)
class ChatResponse:
    id: str
    model: str
    text: str
    stop_reason: StopReason
    usage: Usage


class ChatStreamEventType(str, Enum):
    MESSAGE_START = "message_start"
    TEXT_DELTA = "text_delta"
    MESSAGE_STOP = "message_stop"


@dataclass(frozen=True)
class ChatStreamEvent:
    """A minimal, transport-agnostic streaming event.

    The inbound HTTP adapter (adapters/inbound/http/sse.py) is responsible for
    expanding this into the full Anthropic SSE event sequence
    (message_start / content_block_start / content_block_delta /
    content_block_stop / message_delta / message_stop) — that expansion is a
    wire-format concern, not a domain concern.
    """

    type: ChatStreamEventType
    message_id: str | None = None
    model: str | None = None
    text: str | None = None
    stop_reason: StopReason | None = None
    usage: Usage | None = None
