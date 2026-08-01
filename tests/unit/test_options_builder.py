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
