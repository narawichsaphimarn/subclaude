from __future__ import annotations

from app.domain.models import ChatMessage, Role

_TRANSCRIPT_FRAMING = (
    "What follows is a relayed transcript of a prior conversation, using "
    "Human:/Assistant: turn labels. Continue only the final Human turn. "
    "Respond with your answer text only — no turn labels, no "
    "meta-commentary, no repeating earlier turns."
)


def is_multi_turn(messages: list[ChatMessage]) -> bool:
    return not (len(messages) == 1 and messages[0].role is Role.USER)


def build_prompt(messages: list[ChatMessage]) -> str:
    """Render the caller's message history into a single prompt string for
    one fresh claude_agent_sdk.query() call (there is no server-side session
    store -- statelessness is reconstructed here, matching how the real
    Anthropic API works: the caller owns history).

    Fast path: a single user-only message is passed through verbatim (the
    common single-turn case, no transcript overhead). Otherwise renders a
    Human:/Assistant: transcript ending with a final "Assistant:" cue.

    Known limitation: this is a plain-text transcript format, so a user
    message whose literal text contains "\\n\\nHuman:" could in principle
    confuse the model about where a turn starts. Acceptable for v1 since
    callers are the operator's own trusted client apps -- documented in the
    README, not silently ignored.
    """
    if not is_multi_turn(messages):
        return messages[0].text

    lines: list[str] = []
    for message in messages:
        speaker = "Human" if message.role is Role.USER else "Assistant"
        lines.append(f"\n\n{speaker}: {message.text}")
    lines.append("\n\nAssistant:")
    return "".join(lines)


def build_system_prompt(system: str | None, messages: list[ChatMessage]) -> str | None:
    """Prefix the caller's system prompt with the transcript-framing note
    whenever build_prompt() will render a multi-turn transcript, so the
    model knows how to interpret the Human:/Assistant: labels. Single-turn
    requests pass the caller's system prompt through unchanged.
    """
    if not is_multi_turn(messages):
        return system
    if system:
        return f"{_TRANSCRIPT_FRAMING}\n\n{system}"
    return _TRANSCRIPT_FRAMING
