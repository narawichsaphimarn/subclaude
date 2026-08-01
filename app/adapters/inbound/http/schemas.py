from __future__ import annotations

from typing import Any, Literal, Union

from pydantic import BaseModel, Field

from app.domain.errors import InvalidRequestError
from app.domain.models import ChatMessage, ChatRequest, ChatResponse, Role

# --- Request DTOs (Anthropic /v1/messages wire shape) --------------------


class MessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: Union[str, list[dict[str, Any]]]


class MessagesRequest(BaseModel):
    # Optional (unlike the real Anthropic API, which requires it) purely so
    # a server-configured DEFAULT_MODEL can fill it in for convenience (e.g.
    # ad hoc curl testing); real SDK clients always send it anyway.
    model: str | None = None
    max_tokens: int = Field(gt=0)
    messages: list[MessageIn]
    system: str | None = None
    stream: bool = False
    # Accepted so real Anthropic SDK clients don't fail to *send* these
    # fields; presence is rejected by SendMessageUseCase (v1 is chat-only).
    tools: list[dict[str, Any]] | None = None
    tool_choice: dict[str, Any] | None = None

    def to_domain(self, *, default_model: str | None = None) -> ChatRequest:
        model = self.model or default_model
        if not model:
            raise InvalidRequestError("`model` is required")
        return ChatRequest(
            model=model,
            messages=[_message_to_domain(message) for message in self.messages],
            max_tokens=self.max_tokens,
            system=self.system,
            stream=self.stream,
            tools_requested=bool(self.tools or self.tool_choice),
        )


def _message_to_domain(message: MessageIn) -> ChatMessage:
    return ChatMessage(role=Role(message.role), text=_extract_text(message.content))


def _extract_text(content: str | list[dict[str, Any]]) -> str:
    if isinstance(content, str):
        return content
    texts: list[str] = []
    for block in content:
        if block.get("type") != "text":
            raise InvalidRequestError(
                f'unsupported content block type "{block.get("type")}" -- this proxy '
                "is text-only chat for v1"
            )
        texts.append(block.get("text", ""))
    return "".join(texts)


# --- Response DTOs ---------------------------------------------------------


class ContentBlockOut(BaseModel):
    type: Literal["text"] = "text"
    text: str


class UsageOut(BaseModel):
    input_tokens: int
    output_tokens: int


class MessagesResponse(BaseModel):
    id: str
    type: Literal["message"] = "message"
    role: Literal["assistant"] = "assistant"
    content: list[ContentBlockOut]
    model: str
    stop_reason: str
    stop_sequence: str | None = None
    usage: UsageOut

    @classmethod
    def from_domain(cls, response: ChatResponse) -> "MessagesResponse":
        return cls(
            id=response.id,
            content=[ContentBlockOut(text=response.text)],
            model=response.model,
            stop_reason=response.stop_reason.value,
            usage=UsageOut(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            ),
        )
