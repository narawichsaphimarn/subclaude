from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from typing import Any, AsyncIterator

from claude_agent_sdk import (
    CLIConnectionError,
    CLIJSONDecodeError,
    CLINotFoundError,
    ProcessError,
    query,
)

from app.adapters.outbound.claude_agent_sdk.options_builder import build_options
from app.adapters.outbound.claude_agent_sdk.prompt_builder import build_prompt
from app.adapters.outbound.claude_agent_sdk.response_mapper import (
    build_response,
    to_stream_events,
)
from app.adapters.outbound.claude_agent_sdk.session_repository import SessionUuidResolver
from app.domain.errors import (
    BackendAuthError,
    BackendTimeoutError,
    BackendUnavailableError,
    RateLimitedError,
)
from app.domain.models import ChatRequest, ChatResponse, ChatStreamEvent

logger = logging.getLogger(__name__)

_AUTH_HINT_MARKERS = ("not logged in", "claude login", "unauthorized", "authentication")


class ClaudeAgentSdkBackend:
    """Outbound adapter implementing the ChatBackend port via
    claude_agent_sdk.query(). Owns subprocess concurrency limiting, working
    -directory isolation, and per-call timeouts -- none of which the domain
    or use-case layer needs to know about.
    """

    def __init__(
        self,
        *,
        disallowed_tools: list[str],
        max_concurrent_requests: int,
        queue_timeout_s: float,
        request_timeout_s: float,
        session_resolver: SessionUuidResolver | None = None,
        session_cwd: str | None = None,
    ) -> None:
        self._disallowed_tools = disallowed_tools
        self._queue_timeout_s = queue_timeout_s
        self._request_timeout_s = request_timeout_s
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)
        self._session_resolver = session_resolver
        self._session_cwd = session_cwd
        self._session_locks: dict[str, asyncio.Lock] = {}

    async def complete(self, request: ChatRequest) -> ChatResponse:
        sdk_messages = await self._run(request)
        return build_response(
            sdk_messages,
            fallback_model=request.model,
            requested_max_tokens=request.max_tokens,
        )

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamEvent]:
        # Synthetic streaming (v1): run to completion, then replay as a
        # minimal event sequence. See adapters/inbound/http/sse.py for the
        # expansion into full Anthropic SSE events.
        response = await self.complete(request)
        for event in to_stream_events(response):
            yield event

    async def _run(self, request: ChatRequest) -> list[Any]:
        await self._acquire_slot()
        try:
            return await asyncio.wait_for(
                self._dispatch(request), timeout=self._request_timeout_s
            )
        except asyncio.TimeoutError as exc:
            raise BackendTimeoutError(
                f"backing Claude process did not respond within {self._request_timeout_s}s"
            ) from exc
        finally:
            self._semaphore.release()

    async def _acquire_slot(self) -> None:
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=self._queue_timeout_s)
        except asyncio.TimeoutError as exc:
            raise RateLimitedError(
                "too many concurrent requests to the local Claude proxy; try again shortly"
            ) from exc

    async def _dispatch(self, request: ChatRequest) -> list[Any]:
        if request.session_id is None:
            return await self._run_stateless(request)
        return await self._run_session(request)

    async def _run_stateless(self, request: ChatRequest) -> list[Any]:
        cwd = tempfile.mkdtemp(prefix="subclaude-")
        try:
            options = build_options(request, cwd=cwd, disallowed_tools=self._disallowed_tools)
            prompt = build_prompt(request.messages)
            return await self._collect_messages(prompt, options)
        finally:
            shutil.rmtree(cwd, ignore_errors=True)

    async def _run_session(self, request: ChatRequest) -> list[Any]:
        if not (self._session_resolver and self._session_cwd):
            raise BackendUnavailableError("session support is not configured on this server")
        label = request.session_id
        lock = self._session_locks.setdefault(label, asyncio.Lock())
        async with lock:
            session_uuid, is_new = await self._session_resolver.resolve_uuid(label)
            message_window = request.messages if is_new else [request.messages[-1]]
            options = build_options(
                request,
                cwd=self._session_cwd,
                disallowed_tools=self._disallowed_tools,
                messages=message_window,
                session_id=session_uuid if is_new else None,
                resume=None if is_new else session_uuid,
            )
            prompt = build_prompt(message_window)
            result = await self._collect_messages(prompt, options)
            # Only committed to the label->uuid map after query() succeeds,
            # so a crash mid-first-call retries as a fresh session next time
            # instead of resuming a uuid the CLI never wrote anything for.
            await self._session_resolver.touch(label, uuid=session_uuid)
            return result

    async def _collect_messages(self, prompt: str, options: Any) -> list[Any]:
        try:
            return [message async for message in query(prompt=prompt, options=options)]
        except CLINotFoundError as exc:
            raise BackendUnavailableError(
                "the `claude` CLI was not found -- is Claude Code installed and on PATH?"
            ) from exc
        except CLIConnectionError as exc:
            raise BackendUnavailableError(
                f"could not connect to the `claude` CLI: {exc}"
            ) from exc
        except CLIJSONDecodeError as exc:
            raise BackendUnavailableError(
                f"malformed output from the `claude` CLI: {exc}"
            ) from exc
        except ProcessError as exc:
            raise self._map_process_error(exc) from exc

    def _map_process_error(self, exc: Exception) -> Exception:
        stderr = str(exc).lower()
        if any(marker in stderr for marker in _AUTH_HINT_MARKERS):
            return BackendAuthError(
                f"the `claude` CLI appears not to be authenticated -- run `claude login`. ({exc})"
            )
        return BackendUnavailableError(f"the `claude` CLI process failed: {exc}")
