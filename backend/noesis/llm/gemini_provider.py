"""Google Gemini provider via REST (minimal dependency footprint)."""

from __future__ import annotations

import json
import time
from urllib.parse import urlencode

from httpx import AsyncClient, HTTPError

from noesis.llm._retry import TRANSIENT_HTTP_STATUSES, HTTPRetryableError, with_provider_retry
from noesis.llm.base import BaseProvider
from noesis.types import ChatMessage, MessageRole, ProviderResponse, ProviderType, TokenUsage


def _part_for(message: ChatMessage) -> dict:
    if message.role == MessageRole.TOOL:
        return {
            "functionResponse": {
                "name": message.name or "tool_response",
                "response": {"name": message.name or "tool_response", "content": message.content or ""},
            }
        }
    if message.tool_calls:
        parts = []
        if message.content:
            parts.append({"text": message.content})
        for tc in message.tool_calls:
            fn = tc.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (ValueError, TypeError):
                    args = {"raw": args}
            parts.append({"functionCall": {"name": fn.get("name", "fn"), "args": args}})
        return {"parts": parts}
    return {"parts": [{"text": message.content or ""}]}


def _messages_to_gemini(messages: list[ChatMessage]) -> list[dict]:
    out: list[dict] = []
    for m in messages:
        if m.role == MessageRole.SYSTEM:
            # Gemini supports a top-level systemInstruction; we fold system
            # content into the next user message if multiple exist.
            continue
        role = "model" if m.role == MessageRole.ASSISTANT else "user"
        part = _part_for(m)
        out.append({"role": role, **part})
    return out


def _tools_to_gemini(tools: list[dict] | None) -> dict | None:
    if not tools:
        return None
    fns = []
    for t in tools:
        fn = t.get("function", {})
        fns.append(
            {
                "name": fn.get("name", "fn"),
                "description": fn.get("description", ""),
                "parameters": fn.get("parameters", {"type": "object", "properties": {}}),
            }
        )
    return {"functionDeclarations": fns}


class GeminiProvider(BaseProvider):
    provider_id = "gemini"

    def __init__(self, *, api_key: str, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._api_key = api_key
        self._client: AsyncClient | None = None

    def _get_client(self) -> AsyncClient:
        if self._client is None:
            self._client = AsyncClient(timeout=self.timeout, http2=True)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

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

        system_parts = [m.content for m in messages if m.role == MessageRole.SYSTEM and m.content]
        api_messages = _messages_to_gemini(messages)
        qs = urlencode({"key": self._api_key})
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?{qs}"

        body: dict = {
            "contents": api_messages,
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
            },
        }
        if system_parts:
            body["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
        decls = _tools_to_gemini(tools)
        if decls:
            body["tools"] = [decls]
            if tool_choice == "required":
                body["toolConfig"] = {"functionCallingConfig": {"mode": "ANY"}}
            elif tool_choice == "none":
                body["toolConfig"] = {"functionCallingConfig": {"mode": "NONE"}}
            elif isinstance(tool_choice, dict):
                name = (tool_choice.get("function") or {}).get("name")
                if name:
                    body["toolConfig"] = {"functionCallingConfig": {"mode": "ANY", "allowedFunctionNames": [name]}}
        body.update(self.extra_kwargs)
        body.update(override_kwargs)

        try:
            resp = await self._get_client().post(url, json=body)
        except HTTPError as exc:
            raise HTTPRetryableError(0, str(exc)) from exc
        if resp.status_code in TRANSIENT_HTTP_STATUSES:
            raise HTTPRetryableError(resp.status_code, resp.text[:200])
        resp.raise_for_status()
        data = resp.json()

        latency_ms = (time.perf_counter() - started) * 1000
        candidates = data.get("candidates") or []
        candidate = candidates[0] if candidates else {}
        content = candidate.get("content", {})
        parts = content.get("parts", []) or []
        text_chunks: list[str] = []
        tool_calls: list[dict] = []
        for p in parts:
            if "text" in p:
                text_chunks.append(p["text"])
            if "functionCall" in p:
                fc = p["functionCall"]
                tool_calls.append(
                    {
                        "id": f"tc_{len(tool_calls)}",
                        "type": "function",
                        "function": {"name": fc.get("name"), "arguments": fc.get("args", {})},
                    }
                )

        usage = TokenUsage()
        raw_usage = data.get("usageMetadata") or {}
        if raw_usage:
            usage = TokenUsage(
                prompt_tokens=int(raw_usage.get("promptTokenCount", 0)),
                completion_tokens=int(raw_usage.get("candidatesTokenCount", 0)),
                total_tokens=int(raw_usage.get("totalTokenCount", 0)),
            )
        finish = (candidate.get("finishReason") or "").lower()
        finish_reason = "stop" if finish == "stop" else ("length" if finish == "max_tokens" else ("tool_calls" if tool_calls else "unknown"))
        return ProviderResponse(
            provider=ProviderType.GEMINI,
            model=self.model,
            content="".join(text_chunks),
            tool_calls=tool_calls,
            usage=usage,
            latency_ms=round(latency_ms, 2),
            finish_reason=finish_reason,
            raw=data,
        )
