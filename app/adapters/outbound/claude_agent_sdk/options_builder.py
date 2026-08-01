from __future__ import annotations

from claude_agent_sdk import ClaudeAgentOptions

from app.adapters.outbound.claude_agent_sdk.prompt_builder import build_system_prompt
from app.domain.models import ChatRequest


def build_options(
    request: ChatRequest,
    *,
    cwd: str,
    disallowed_tools: list[str],
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
    - cwd is a fresh, isolated temp directory managed by the caller
      (ClaudeAgentSdkBackend) -- defense in depth, so even a tool that
      somehow ran could not touch the real project tree.
    """
    return ClaudeAgentOptions(
        system_prompt=build_system_prompt(request.system, request.messages),
        model=request.model,
        disallowed_tools=disallowed_tools,
        permission_mode="bypassPermissions",
        setting_sources=[],
        max_turns=1,
        cwd=cwd,
    )
