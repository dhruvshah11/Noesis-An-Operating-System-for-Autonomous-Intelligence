"""Ollama — local, open-source LLM and embedding provider."""

from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING

from httpx import AsyncClient, HTTPError

from noesis.llm._retry import TRANSIENT_HTTP_STATUSES, HTTPRetryableError, with_provider_retry
from noesis.llm.base import BaseProvider, EmbeddingProvider
from noesis.types import ChatMessage, Embedding, MessageRole, ProviderResponse, ProviderType, TokenUsage

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence


def _messages_to_ollama(messages: list[ChatMessage]) -> list[dict]:
    out: list[dict] = []
    for m in messages:
        if m.role == MessageRole.TOOL:
            # Ollama's chat API doesn't model tool results natively; encode
            # them as a user block with a sentinel prefix so the model sees them.
            out.append(
                {
                    "role": "user",
                    "content": f"[TOOL RESULT id={m.tool_call_id or '?'}]\n{m.content or ''}\n[/TOOL RESULT]",
                }
            )
            continue
        role = "assistant" if m.role == MessageRole.ASSISTANT else ((m.role == "system" and "system") or "user")
        out.append({"role": str(role), "content": m.content or ""})
    return out


class OllamaProvider(BaseProvider):
    provider_id = "ollama"

    def __init__(self, *, base_url: str, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._base_url = base_url.rstrip("/")
        self._client: AsyncClient | None = None

    def _get_client(self) -> AsyncClient:
        if self._client is None:
            self._client = AsyncClient(timeout=self.timeout, http2=True)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @with_provider_retry(max_attempts=3, max_wait_s=5)
    async def _chat_impl(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict] | None,
        tool_choice: str | dict | None,
        **override_kwargs: object,
    ) -> ProviderResponse:
        started = time.perf_counter()
        body: dict = {
            "model": self.model,
            "messages": _messages_to_ollama(messages),
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }
        # Ollama supports native tool-calling since v0.3.x — passthrough
        # when provided (format = OpenAI JSONSchema -> Ollama format).
        if tools:
            ollama_tools = []
            for t in tools:
                fn = t.get("function", {})
                ollama_tools.append({"type": "function", "function": fn} if "function" in t else {"type": "function", "function": t})
            body["tools"] = ollama_tools
        _ = tool_choice  # Ollama has no tool_choice knobs today; consumed for signature parity.
        body.update(self.extra_kwargs)
        body.update(override_kwargs)

        try:
            resp = await self._get_client().post(f"{self._base_url}/api/chat", json=body)
        except HTTPError as exc:
            raise HTTPRetryableError(0, str(exc)) from exc
        if resp.status_code in TRANSIENT_HTTP_STATUSES:
            raise HTTPRetryableError(resp.status_code, resp.text[:200])
        resp.raise_for_status()
        data = resp.json()

        latency_ms = (time.perf_counter() - started) * 1000
        msg = data.get("message", {})
        content = msg.get("content") or ""
        tool_calls = msg.get("tool_calls") or []
        # Normalise tool_calls to OpenAI shape if Ollama gives us a different one.
        normalised: list[dict] = []
        for tc in tool_calls:
            if "function" in tc:
                normalised.append(tc)
            else:
                normalised.append({"id": tc.get("id", f"tc{len(normalised)}"), "type": "function", "function": tc})
        usage = TokenUsage(
            prompt_tokens=int(data.get("prompt_eval_count", 0)),
            completion_tokens=int(data.get("eval_count", 0)),
            total_tokens=int(data.get("prompt_eval_count", 0)) + int(data.get("eval_count", 0)),
        )
        finish_reason = "tool_calls" if normalised else ("stop" if data.get("done") else "unknown")
        return ProviderResponse(
            provider=ProviderType.OLLAMA,
            model=self.model,
            content=content,
            tool_calls=normalised,
            usage=usage,
            latency_ms=round(latency_ms, 2),
            finish_reason=finish_reason,
            raw=data,
        )

    async def chat_stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: list[dict] | None = None,
        system_prompt: str | None = None,
        **override_kwargs: object,
    ) -> AsyncIterator[str]:
        effective = list(messages)
        if system_prompt:
            effective.insert(0, ChatMessage(role=MessageRole.SYSTEM, content=system_prompt))
        body: dict = {
            "model": self.model,
            "messages": _messages_to_ollama(effective),
            "stream": True,
            "options": {"temperature": self.temperature, "num_predict": self.max_tokens},
        }
        if tools:
            body["tools"] = tools
        async with AsyncClient(timeout=self.timeout) as client, client.stream("POST", f"{self._base_url}/api/chat", json=body) as r:
            async for line in r.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except ValueError:
                    continue
                token = (chunk.get("message") or {}).get("content")
                if token:
                    yield token


class OllamaEmbeddingProvider(EmbeddingProvider):
    provider_id = "ollama"

    def __init__(self, *, base_url: str, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._base_url = base_url.rstrip("/")
        self._client: AsyncClient | None = None

    def _get_client(self) -> AsyncClient:
        if self._client is None:
            self._client = AsyncClient(timeout=self.timeout, http2=True)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @with_provider_retry(max_attempts=3, max_wait_s=5)
    async def embed(self, texts: Sequence[str]) -> list[Embedding]:
        if not texts:
            return []
        results: list[Embedding] = []
        client = self._get_client()
        for idx, text in enumerate(texts):
            started = time.perf_counter()
            try:
                resp = await client.post(
                    f"{self._base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
            except HTTPError as exc:
                raise HTTPRetryableError(0, str(exc)) from exc
            if resp.status_code in TRANSIENT_HTTP_STATUSES:
                raise HTTPRetryableError(resp.status_code, resp.text[:200])
            resp.raise_for_status()
            data = resp.json()
            vec = data.get("embedding") or []
            # Truncate or pad to configured dimensions so downstream Qdrant
            # collections don't break on inconsistent vector sizes.
            if len(vec) > self.dimensions:
                vec = vec[: self.dimensions]
            elif len(vec) < self.dimensions:
                vec = vec + [0.0] * (self.dimensions - len(vec))
            usage = TokenUsage(total_tokens=len(text.split()))
            results.append(
                Embedding(
                    provider=ProviderType.OLLAMA,
                    model=self.model,
                    vector=vec,
                    dimensions=self.dimensions,
                    usage=usage,
                )
            )
            self._total_usage += usage
            # Tiny yield to event loop so we don't block if hundreds of texts.
            # Only skip on the last iteration since there's no next work.
            if idx != len(texts) - 1:
                await asyncio.sleep(0)
            _ = started  # keep perf counter referenced for future timing hooks
        return results
