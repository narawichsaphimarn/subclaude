from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

# Built-in Claude Code tool names this proxy always disables so the backing
# process behaves as a plain, tool-less chat completion. Confirmed by
# `strings`-searching the installed `claude` 2.1.212 CLI binary for quoted
# tool-name literals (resolves plan Open Risk #3) -- if the CLI is upgraded
# and this ever needs re-verifying:
#   strings -a "$(readlink -f "$(which claude)")" | grep -Eo \
#     '"(Bash|Read|Write|Edit|Glob|Grep|WebFetch|WebSearch|NotebookEdit|Task|
#        TodoWrite|BashOutput|KillShell|MultiEdit|ExitPlanMode)"' | sort -u
# Missing an entry here is a real safety gap, not cosmetic.
DEFAULT_DISALLOWED_TOOLS = [
    "Bash",
    "BashOutput",
    "Edit",
    "ExitPlanMode",
    "Glob",
    "Grep",
    "KillShell",
    "MultiEdit",
    "NotebookEdit",
    "Read",
    "Task",
    "TodoWrite",
    "WebFetch",
    "WebSearch",
    "Write",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Comma-separated list of keys this proxy accepts on x-api-key / Bearer.
    proxy_api_keys: str

    host: str = "127.0.0.1"
    port: int = 8000

    default_model: str | None = None
    max_concurrent_requests: int = 2
    queue_timeout_s: float = 30.0
    request_timeout_s: float = 120.0
    # "synthetic" (v1, implemented) | "passthrough" (stretch goal, see plan
    # Open Risk #2 -- not implemented yet).
    streaming_mode: str = "synthetic"

    disallowed_tools: list[str] = DEFAULT_DISALLOWED_TOOLS

    @property
    def proxy_api_keys_list(self) -> list[str]:
        return [key.strip() for key in self.proxy_api_keys.split(",") if key.strip()]
