from __future__ import annotations

from claude_agent_sdk import ClaudeAgentOptions

from app.adapters.outbound.claude_agent_sdk.prompt_builder import build_system_prompt
from app.domain.models import ChatMessage, ChatRequest


def build_options(
    request: ChatRequest,
    *,
    cwd: str,
    disallowed_tools: list[str],
    messages: list[ChatMessage] | None = None,
    resume: str | None = None,
    session_id: str | None = None,
) -> ClaudeAgentOptions:
    """Map a validated ChatRequest to ClaudeAgentOptions for a single,
    single-shot query() call. Every option here exists to make the backing
    `claude` process behave like a plain, tool-less chat completion:

    - disallowed_tools blocks every built-in tool -- this is the real safety
      boundary. `allowed_tools` alone is only a permission auto-approve
      allowlist and does NOT restrict which tools are available.
    - permission_mode="bypassPermissions" avoids ever blocking on
      interactive approval input, since this subprocess is headless.
    - setting_sources=[] disables loading any user/project/local settings or
      CLAUDE.md, so the spawned process cannot pick up unrelated local
      instructions from this machine.
    - max_turns=1 enforces a single response with no tool-use loop.
    - cwd is either a fresh, isolated temp directory (stateless requests) or
      the fixed session cwd (session-bound requests) managed by the caller
      (ClaudeAgentSdkBackend) -- defense in depth, so even a tool that
      somehow ran could not touch the real project tree.
    - resume/session_id are mutually exclusive: set on session-bound
      requests only (resume to continue an existing session, session_id to
      mint a specific new one); both None for stateless requests.
    - messages overrides request.messages for prompt/system framing only --
      used by session-bound continuation turns, where only the latest
      message should decide framing even though request.messages may carry
      more (see ClaudeAgentSdkBackend._run_session).
    """
    effective_messages = messages if messages is not None else request.messages
    return ClaudeAgentOptions(
        system_prompt=build_system_prompt(request.system, effective_messages),
        model=request.model,
        disallowed_tools=disallowed_tools,
        permission_mode="bypassPermissions",
        setting_sources=[],
        max_turns=1,
        cwd=cwd,
        resume=resume,
        session_id=session_id,
    )
