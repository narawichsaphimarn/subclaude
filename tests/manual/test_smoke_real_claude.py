"""Real end-to-end smoke test against the actual `claude` CLI subprocess.

This is the ONE test in the suite that consumes real Claude subscription
quota, so it is excluded from the default `pytest` run (see the `manual`
marker in pyproject.toml). Run it explicitly after `claude login`:

    RUN_MANUAL_CLAUDE_TEST=1 pytest -m manual tests/manual/test_smoke_real_claude.py -v -s

It also prints the real AssistantMessage.usage / message_id it received,
which is the empirical check for plan Open Risk #1 (the response mapper's
`usage.is_estimated` assertion below fails loudly if that assumption was
wrong).
"""

import os

import pytest

from app.adapters.outbound.claude_agent_sdk.backend import ClaudeAgentSdkBackend
from app.config import DEFAULT_DISALLOWED_TOOLS
from app.domain.models import ChatMessage, ChatRequest, Role

pytestmark = pytest.mark.manual


@pytest.fixture(autouse=True)
def _require_opt_in():
    if os.environ.get("RUN_MANUAL_CLAUDE_TEST") != "1":
        pytest.skip(
            "set RUN_MANUAL_CLAUDE_TEST=1 to run this real end-to-end test "
            "against the actual `claude` CLI (consumes subscription quota)"
        )


async def test_real_end_to_end_chat_completion():
    backend = ClaudeAgentSdkBackend(
        disallowed_tools=DEFAULT_DISALLOWED_TOOLS,
        max_concurrent_requests=1,
        queue_timeout_s=30,
        request_timeout_s=120,
    )
    request = ChatRequest(
        model="claude-opus-4-8",
        messages=[ChatMessage(role=Role.USER, text="Reply with exactly the word: pong")],
        max_tokens=50,
    )

    response = await backend.complete(request)

    print(f"\n[manual smoke test] response = {response!r}")
    assert response.text.strip()
    assert response.usage.is_estimated is False, (
        "expected a REAL token count from AssistantMessage.usage -- if this "
        "fails, the estimate fallback is being hit; re-check Open Risk #1"
    )
