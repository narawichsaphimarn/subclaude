from app.adapters.outbound.claude_agent_sdk.options_builder import build_options
from app.domain.models import ChatMessage, ChatRequest, Role


def _request(**overrides) -> ChatRequest:
    defaults = dict(
        model="claude-opus-4-8",
        messages=[ChatMessage(role=Role.USER, text="Hi")],
        max_tokens=256,
        system=None,
        stream=False,
        tools_requested=False,
    )
    defaults.update(overrides)
    return ChatRequest(**defaults)


def test_build_options_maps_model_and_forces_chat_only_safety_settings():
    options = build_options(_request(), cwd="/tmp/fake", disallowed_tools=["Bash", "Read"])

    assert options.model == "claude-opus-4-8"
    assert options.disallowed_tools == ["Bash", "Read"]
    assert options.permission_mode == "bypassPermissions"
    assert options.setting_sources == []
    assert options.max_turns == 1
    assert str(options.cwd) == "/tmp/fake"


def test_build_options_passes_system_prompt_through_for_single_turn():
    options = build_options(
        _request(system="Be concise."), cwd="/tmp/fake", disallowed_tools=[]
    )
    assert options.system_prompt == "Be concise."


def test_build_options_defaults_resume_and_session_id_to_none():
    options = build_options(_request(), cwd="/tmp/fake", disallowed_tools=[])
    assert options.resume is None
    assert options.session_id is None


def test_build_options_passes_resume_and_session_id_through():
    options = build_options(
        _request(), cwd="/tmp/fake", disallowed_tools=[], resume="abc-123"
    )
    assert options.resume == "abc-123"
    assert options.session_id is None

    options = build_options(
        _request(), cwd="/tmp/fake", disallowed_tools=[], session_id="new-uuid"
    )
    assert options.session_id == "new-uuid"
    assert options.resume is None


def test_build_options_messages_override_decides_framing_independently():
    # request.messages is multi-turn, but the `messages=` override is a
    # single user message -- framing must follow the override, not the
    # request's own (possibly stale) full array.
    request = _request(
        messages=[
            ChatMessage(role=Role.USER, text="first"),
            ChatMessage(role=Role.ASSISTANT, text="second"),
            ChatMessage(role=Role.USER, text="latest"),
        ],
        system="Be concise.",
    )
    options = build_options(
        request,
        cwd="/tmp/fake",
        disallowed_tools=[],
        messages=[ChatMessage(role=Role.USER, text="latest")],
    )
    assert options.system_prompt == "Be concise."
