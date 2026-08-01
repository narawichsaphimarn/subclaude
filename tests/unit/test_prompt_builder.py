from app.adapters.outbound.claude_agent_sdk.prompt_builder import (
    build_prompt,
    build_system_prompt,
)
from app.domain.models import ChatMessage, Role


def test_single_user_message_is_passed_through_verbatim():
    messages = [ChatMessage(role=Role.USER, text="Hello Claude")]
    assert build_prompt(messages) == "Hello Claude"


def test_multi_turn_renders_human_assistant_transcript():
    messages = [
        ChatMessage(role=Role.USER, text="Hi"),
        ChatMessage(role=Role.ASSISTANT, text="Hello!"),
        ChatMessage(role=Role.USER, text="How are you?"),
    ]
    prompt = build_prompt(messages)
    assert prompt == "\n\nHuman: Hi\n\nAssistant: Hello!\n\nHuman: How are you?\n\nAssistant:"


def test_single_turn_system_prompt_passed_through_unchanged():
    messages = [ChatMessage(role=Role.USER, text="Hi")]
    assert build_system_prompt("Be nice.", messages) == "Be nice."
    assert build_system_prompt(None, messages) is None


def test_multi_turn_system_prompt_gets_framing_prefix():
    messages = [
        ChatMessage(role=Role.USER, text="Hi"),
        ChatMessage(role=Role.ASSISTANT, text="Hello!"),
        ChatMessage(role=Role.USER, text="Bye"),
    ]
    with_system = build_system_prompt("Be nice.", messages)
    assert with_system is not None
    assert with_system.endswith("Be nice.")
    assert "Human:/Assistant:" in with_system

    without_system = build_system_prompt(None, messages)
    assert without_system is not None
    assert "Human:/Assistant:" in without_system
