"""Anthropic (Claude) provider — tools use their native 2024 tool-use API."""

from __future__ import annotations

import time

from httpx import AsyncClient, HTTPError

from noesis.llm._retry import TRANSIENT_HTTP_STATUSES, HTTPRetryableError, with_provider_retry
from noesis.llm.base import BaseProvider
from noesis.types import (
    ChatMessage,
    MessageRole,
    ProviderResponse,
    ProviderType,
    TokenUsage,
)


def _messages_to_anthropic(messages: list[ChatMessage]) -> tuple[str, list[dict]]:
    """Split ``system`` out (Claude takes it separately) + convert roles."""
    system_parts: list[str] = []
    chat: list[dict] = []
    for m in messages:
        if m.role == MessageRole.SYSTEM and m.content:
            system_parts.append(m.content)
            continue
        # Claude roles are user/assistant.  Map tool -> user with block.
        if m.role == MessageRole.TOOL:
            chat.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.tool_call_id or "tc-missing",
                            "content": m.content or "",
                        }
                    ],
                }
            )
            continue
        role = "assistant" if m.role == MessageRole.ASSISTANT else "user"
        content: list[dict] | str
        if m.tool_calls:
            content = []
            for tc in m.tool_calls:
                fn = tc.get("function", {})
                content.append(
                    {
                        "type": "tool_use",
                        "id": tc.get("id", "tc"),
                        "name": fn.get("name", ""),
                        "input": fn.get("arguments", {}) if isinstance(fn.get("arguments"), dict) else {},
                    }
                )
            if m.content:
                content.insert(0, {"type": "text", "text": m.content})
        else:
            content = m.content or ""
        chat.append({"role": role, "content": content})
    return "\n\n".join(system_parts), chat


def _tools_to_anthropic(tools: list[dict] | None) -> list[dict] | None:
    if not tools:
        return None
    out = []
    for t in tools:
        fn = t.get("function", {})
        out.append(
            {
                "name": fn.get("name", "unnamed_tool"),
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            }
        )
    return out


class AnthropicProvider(BaseProvider):
    provider_id = "anthropic"

    def __init__(self, *, api_key: str, base_url: str | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._api_key = api_key
        self._base_url = (base_url or "https://api.anthropic.com/v1").rstrip("/")
        self._client: AsyncClient | None = None

    def _get_client(self) -> AsyncClient:
        if self._client is None:
            self._client = AsyncClient(timeout=self.timeout, http2=True)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    @with_provider_retry(max_attempts=4, max_wait_s=10)
    async def _chat_impl(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict] | None,
        tool_choice: str | dict | None,
        **override_kwargs: object,
    ) -> ProviderResponse:
        started = time.perf_counter()
        system_prompt, api_messages = _messages_to_anthropic(messages)
        body: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": api_messages,
        }
        if system_prompt:
            body["system"] = system_prompt
        anthropic_tools = _tools_to_anthropic(tools)
        if anthropic_tools:
            body["tools"] = anthropic_tools
            if tool_choice == "required":
                body["tool_choice"] = {"type": "any"}
            elif tool_choice in {"none", "auto"} or tool_choice is None:
                pass  # default = auto
            elif isinstance(tool_choice, dict):
                name = (tool_choice.get("function") or {}).get("name")
                if name:
                    body["tool_choice"] = {"type": "tool", "name": name}
        body.update(self.extra_kwargs)
        body.update(override_kwargs)

        try:
            resp = await self._get_client().post(f"{self._base_url}/messages", headers=self._headers(), json=body)
        except HTTPError as exc:
            raise HTTPRetryableError(0, str(exc)) from exc
        if resp.status_code in TRANSIENT_HTTP_STATUSES:
            raise HTTPRetryableError(resp.status_code, resp.text[:200])
        resp.raise_for_status()
        data = resp.json()

        latency_ms = (time.perf_counter() - started) * 1000

        text_chunks: list[str] = []
        tool_calls: list[dict] = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text_chunks.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    {
                        "id": block.get("id"),
                        "type": "function",
                        "function": {
                            "name": block.get("name"),
                            "arguments": block.get("input", {}),
                        },
                    }
                )

        raw_usage = data.get("usage") or {}
        usage = TokenUsage(
            prompt_tokens=int(raw_usage.get("input_tokens", 0)),
            completion_tokens=int(raw_usage.get("output_tokens", 0)),
            total_tokens=int(raw_usage.get("input_tokens", 0)) + int(raw_usage.get("output_tokens", 0)),
        )
        stop_reason = data.get("stop_reason", "unknown")
        finish_reason = "tool_calls" if stop_reason == "tool_use" else ("stop" if stop_reason == "end_turn" else "unknown")
        return ProviderResponse(
            provider=ProviderType.ANTHROPIC,
            model=self.model,
            content="".join(text_chunks),
            tool_calls=tool_calls,
            usage=usage,
            latency_ms=round(latency_ms, 2),
            finish_reason=finish_reason,
            raw=data,
        )
