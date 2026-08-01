from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from typing import Any

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

from app.domain.errors import (
    BackendAuthError,
    BackendUnavailableError,
    DomainError,
    InvalidRequestError,
    RateLimitedError,
)
from app.domain.models import (
    ChatResponse,
    ChatStreamEvent,
    ChatStreamEventType,
    StopReason,
    Usage,
)

logger = logging.getLogger(__name__)

_STOP_REASON_MAP = {
    "end_turn": StopReason.END_TURN,
    "max_tokens": StopReason.MAX_TOKENS,
}

# AssistantMessage.error (confirmed via dataclasses.fields() against the
# installed SDK) is a much more reliable failure signal than stderr
# pattern-matching -- map it straight to the right domain error type.
_ASSISTANT_ERROR_MAP: dict[str, type[DomainError]] = {
    "authentication_failed": BackendAuthError,
    "rate_limit": RateLimitedError,
    "billing_error": BackendUnavailableError,
    "invalid_request": InvalidRequestError,
    "server_error": BackendUnavailableError,
    "unknown": BackendUnavailableError,
}


def build_response(
    sdk_messages: Sequence[Any],
    *,
    fallback_model: str,
    requested_max_tokens: int,
) -> ChatResponse:
    """Turn the full sequence of SDK messages from one query() call into a
    domain ChatResponse. With max_turns=1 and all tools disabled, expect
    roughly: SystemMessage(init) -> one AssistantMessage -> ResultMessage.
    """
    assistant_message = _last_assistant_message(sdk_messages)
    result_message = _last_result_message(sdk_messages)

    if assistant_message is not None and assistant_message.error:
        error_cls = _ASSISTANT_ERROR_MAP.get(assistant_message.error, BackendUnavailableError)
        raise error_cls(f"backing Claude process reported error: {assistant_message.error}")
    if result_message is not None and result_message.is_error:
        raise BackendUnavailableError(
            "backing Claude process reported an error "
            f"(subtype={result_message.subtype!r}, errors={result_message.errors!r})"
        )
    if assistant_message is None:
        raise BackendUnavailableError("backing Claude process produced no assistant response")

    text = _extract_text(assistant_message)
    usage = _extract_usage(assistant_message, result_message, text)
    stop_reason = _extract_stop_reason(assistant_message, result_message)
    text, stop_reason = _enforce_max_tokens(text, usage, requested_max_tokens, stop_reason)

    message_id = getattr(assistant_message, "message_id", None) or f"msg_{uuid.uuid4().hex}"
    model = getattr(assistant_message, "model", None) or fallback_model

    return ChatResponse(
        id=message_id,
        model=model,
        text=text,
        stop_reason=stop_reason,
        usage=usage,
    )


def to_stream_events(response: ChatResponse) -> list[ChatStreamEvent]:
    """Synthetic streaming (v1): expand a complete ChatResponse into the
    minimal domain event sequence the inbound SSE encoder needs. Not true
    incremental delivery -- the full text arrives as one TEXT_DELTA -- but
    protocol-shape-correct for any Anthropic SSE consumer.
    """
    return [
        ChatStreamEvent(
            type=ChatStreamEventType.MESSAGE_START,
            message_id=response.id,
            model=response.model,
        ),
        ChatStreamEvent(type=ChatStreamEventType.TEXT_DELTA, text=response.text),
        ChatStreamEvent(
            type=ChatStreamEventType.MESSAGE_STOP,
            stop_reason=response.stop_reason,
            usage=response.usage,
        ),
    ]


def _last_assistant_message(sdk_messages: Sequence[Any]) -> AssistantMessage | None:
    for message in reversed(sdk_messages):
        if isinstance(message, AssistantMessage):
            return message
    return None


def _last_result_message(sdk_messages: Sequence[Any]) -> ResultMessage | None:
    for message in reversed(sdk_messages):
        if isinstance(message, ResultMessage):
            return message
    return None


def _extract_text(assistant_message: AssistantMessage) -> str:
    return "".join(
        block.text for block in assistant_message.content if isinstance(block, TextBlock)
    )


def _extract_usage(
    assistant_message: AssistantMessage,
    result_message: ResultMessage | None,
    text: str,
) -> Usage:
    usage_dict = getattr(assistant_message, "usage", None)
    if not usage_dict and result_message is not None:
        usage_dict = getattr(result_message, "usage", None)

    if usage_dict and "input_tokens" in usage_dict and "output_tokens" in usage_dict:
        return Usage(
            input_tokens=int(usage_dict["input_tokens"]),
            output_tokens=int(usage_dict["output_tokens"]),
            is_estimated=False,
        )

    logger.warning(
        "no real usage data from backing Claude process; falling back to a "
        "character-count estimate (this is NOT a real token count) -- see "
        "plan Open Risk #1 (AssistantMessage.usage shape)"
    )
    return Usage(input_tokens=0, output_tokens=max(1, len(text) // 4), is_estimated=True)


def _extract_stop_reason(
    assistant_message: AssistantMessage,
    result_message: ResultMessage | None,
) -> StopReason:
    raw = getattr(assistant_message, "stop_reason", None)
    if not raw and result_message is not None:
        raw = getattr(result_message, "stop_reason", None)
    return _STOP_REASON_MAP.get(raw, StopReason.END_TURN)


def _enforce_max_tokens(
    text: str,
    usage: Usage,
    requested_max_tokens: int,
    stop_reason: StopReason,
) -> tuple[str, StopReason]:
    """ClaudeAgentOptions has no max_tokens equivalent, so this is enforced
    after the fact: if the real output token count exceeds what was
    requested, truncate proportionally and report stop_reason=max_tokens.
    A documented approximation (see README known-gaps), never applied to an
    estimated usage figure since that would compound one approximation with
    another.
    """
    if usage.is_estimated or usage.output_tokens <= requested_max_tokens:
        return text, stop_reason
    ratio = requested_max_tokens / usage.output_tokens
    truncated_length = max(1, int(len(text) * ratio))
    return text[:truncated_length], StopReason.MAX_TOKENS
