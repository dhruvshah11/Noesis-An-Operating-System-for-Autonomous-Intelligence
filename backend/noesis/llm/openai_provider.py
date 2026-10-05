"""OpenAI + Azure-compatible chat + embedding provider."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from httpx import AsyncClient, HTTPError
from tenacity import RetryError

from noesis.llm._retry import TRANSIENT_HTTP_STATUSES, HTTPRetryableError, with_provider_retry
from noesis.llm.base import BaseProvider, EmbeddingProvider
from noesis.types import (
    ChatMessage,
    Embedding,
    MessageRole,
    ProviderResponse,
    ProviderType,
    TokenUsage,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


def _message_to_openai(msg: ChatMessage) -> dict:
    """Convert our internal :class:`ChatMessage` to the OpenAI wire format."""
    payload: dict = {"role": str(msg.role)}
    if msg.content is not None:
        payload["content"] = msg.content
    if msg.name:
        payload["name"] = msg.name
    if msg.tool_call_id:
        payload["tool_call_id"] = msg.tool_call_id
    if msg.tool_calls:
        payload["tool_calls"] = msg.tool_calls
    return payload


def _tool_choice_to_openai(tool_choice: str | dict | None) -> str | dict | None:
    if tool_choice in ("auto", "none", "required"):
        return tool_choice
    if isinstance(tool_choice, dict):
        return tool_choice
    return None


class OpenAIProvider(BaseProvider):
    provider_id = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str | None = None,
        org_id: str | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._api_key = api_key
        self._base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self._org_id = org_id
        # One shared AsyncClient per provider instance: enables HTTP/2 connection
        # pooling across calls (10–30% latency win on successive calls).
        # Created lazily on first use so unit tests that only instantiate the
        # provider never open sockets.
        self._client: AsyncClient | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _get_client(self) -> AsyncClient:
        if self._client is None:
            # ``http2=True`` is safe fallback: httpx falls back to HTTP/1.1
            # gracefully for older endpoints.
            self._client = AsyncClient(timeout=self.timeout, http2=True)
        return self._client

    async def aclose(self) -> None:
        """Explicit close hook; wired into FastAPI lifespan shutdown in M0.2+."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Request helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        h = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if self._org_id:
            h["OpenAI-Organization"] = self._org_id
        return h

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
        body: dict = {
            "model": self.model,
            "messages": [_message_to_openai(m) for m in messages],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            body["tools"] = tools
            tc = _tool_choice_to_openai(tool_choice)
            if tc is not None:
                body["tool_choice"] = tc
        body.update(self.extra_kwargs)
        body.update(override_kwargs)

        try:
            resp = await self._get_client().post(f"{self._base_url}/chat/completions", headers=self._headers(), json=body)
        except HTTPError as exc:
            raise HTTPRetryableError(0, str(exc)) from exc

        if resp.status_code in TRANSIENT_HTTP_STATUSES:
            raise HTTPRetryableError(resp.status_code, resp.text[:200])
        resp.raise_for_status()
        data = resp.json()

        latency_ms = (time.perf_counter() - started) * 1000
        choice = data["choices"][0]
        msg = choice.get("message", {})
        raw_usage = data.get("usage") or {}
        usage = TokenUsage(
            prompt_tokens=int(raw_usage.get("prompt_tokens", 0)),
            completion_tokens=int(raw_usage.get("completion_tokens", 0)),
            total_tokens=int(raw_usage.get("total_tokens", 0)),
        )
        finish_reason = choice.get("finish_reason", "unknown")
        if finish_reason not in {"stop", "length", "tool_calls", "error"}:
            finish_reason = "unknown"
        return ProviderResponse(
            provider=ProviderType.OPENAI,
            model=self.model,
            content=msg.get("content") or "",
            tool_calls=msg.get("tool_calls") or [],
            usage=usage,
            latency_ms=round(latency_ms, 2),
            finish_reason=finish_reason,
            raw=data,
        )


class OpenAIEmbeddingProvider(EmbeddingProvider):
    provider_id = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._api_key = api_key
        self._base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
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
    async def embed(self, texts: Sequence[str]) -> list[Embedding]:
        if not texts:
            return []
        body = {"model": self.model, "input": list(texts), "encoding_format": "float"}
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            resp = await self._get_client().post(f"{self._base_url}/embeddings", headers=headers, json=body)
        except HTTPError as exc:
            raise HTTPRetryableError(0, str(exc)) from exc
        if resp.status_code in TRANSIENT_HTTP_STATUSES:
            raise HTTPRetryableError(resp.status_code, resp.text[:200])
        resp.raise_for_status()
        data = resp.json()

        items = sorted(data["data"], key=lambda d: d["index"])
        usage = TokenUsage(
            prompt_tokens=int((data.get("usage") or {}).get("prompt_tokens", 0)),
            total_tokens=int((data.get("usage") or {}).get("total_tokens", 0)),
        )
        self._total_usage += usage
        result: list[Embedding] = []
        for idx, _text in enumerate(texts):
            vec = items[idx]["embedding"] if idx < len(items) else [0.0] * self.dimensions
            result.append(
                Embedding(
                    provider=ProviderType.OPENAI,
                    model=self.model,
                    vector=vec[: self.dimensions],
                    dimensions=self.dimensions,
                    usage=usage,
                )
            )
        return result


# Re-export enums / error types so other providers (e.g. Anthropic, Gemini) can
# import them from this file without creating import cycles.
__all__ = [
    "TRANSIENT_HTTP_STATUSES",
    "HTTPRetryableError",
    "OpenAIEmbeddingProvider",
    "OpenAIProvider",
    "RetryError",
]

# Keep MessageRole imported so callers testing message maps don't fail.
_ = MessageRole
