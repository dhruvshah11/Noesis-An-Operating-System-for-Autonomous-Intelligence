"""Unit tests for LLM factory + fallback failover behaviour.

Tests do NOT hit real network endpoints — they exercise the factory +
FailoverProvider wrapper using stub providers and monkeypatched env vars.
"""

from __future__ import annotations

import pytest

from noesis.llm._retry import HTTPRetryableError
from noesis.llm.base import BaseProvider
from noesis.llm.factory import FailoverProvider, _build_raw_provider, get_provider
from noesis.types import (
    ChatMessage,
    MessageRole,
    ProviderResponse,
    ProviderType,
    TokenUsage,
)


class _BrokenPrimary(BaseProvider):
    """Provider that unconditionally raises ConnectionError from _chat_impl."""

    provider_id = "broken_primary"

    def __init__(self, *, error_type: str = "connection", **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._error_type = error_type
        self.calls: int = 0

    async def _chat_impl(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict] | None,
        tool_choice: str | dict | None,
        **override_kwargs: object,
    ) -> ProviderResponse:
        self.calls += 1
        if self._error_type == "connection":
            raise ConnectionError("simulated TCP reset — peer unreachable")
        if self._error_type == "http500":
            raise HTTPRetryableError(500, "simulated upstream 500 Internal Server Error")
        if self._error_type == "http503":
            raise HTTPRetryableError(503, "simulated upstream 503 Service Unavailable")
        raise ValueError("unexpected error type")


class _WorkingFallback(BaseProvider):
    """Provider that always returns a valid parseable ProviderResponse."""

    provider_id = "working_fallback"

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.calls: int = 0

    async def _chat_impl(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict] | None,
        tool_choice: str | dict | None,
        **override_kwargs: object,
    ) -> ProviderResponse:
        self.calls += 1
        usage = TokenUsage(prompt_tokens=4, completion_tokens=4, total_tokens=8)
        return ProviderResponse(
            provider=ProviderType.OLLAMA,
            model=self.model,
            content='{"ok":true,"from":"fallback"}',
            tool_calls=[],
            usage=usage,
            latency_ms=1.5,
            finish_reason="stop",
            raw=None,
        )


def test_factory_ollama_env_returns_ollama_provider(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """(a) When env configures OLLAMA, factory MUST return an OllamaProvider instance."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DEFAULT_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("FALLBACK_PROVIDER", "ollama")  # same as primary → no Failover wrapper
    from noesis.config import get_settings

    get_settings.cache_clear()

    from noesis.llm.ollama_provider import OllamaProvider

    p = get_provider(model="llama3:8b", use_fallback=True)
    assert isinstance(p, OllamaProvider), f"expected OllamaProvider but got {type(p).__name__}"
    assert p.provider_id == "ollama"
    assert p.model == "llama3:8b"
    assert getattr(p, "_base_url", None) == "http://localhost:11434"

    raw = _build_raw_provider("ollama", model="qwen2.5-coder")
    assert isinstance(raw, OllamaProvider)
    assert raw.model == "qwen2.5-coder"


@pytest.mark.asyncio
async def test_factory_fallback_kicks_in_when_primary_raises(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """(b) When primary raises ConnectionError / HTTP 5xx, FailoverProvider must transparently use fallback."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-2")
    from noesis.config import get_settings

    get_settings.cache_clear()

    primary_conn = _BrokenPrimary(error_type="connection", model="broken-connection-model")
    primary_500 = _BrokenPrimary(error_type="http500", model="broken-500-model")
    primary_503 = _BrokenPrimary(error_type="http503", model="broken-503-model")
    fallback = _WorkingFallback(model="working-fallback-model")

    msgs = [ChatMessage(role=MessageRole.USER, content="hi")]

    for primary, label in [(primary_conn, "ConnectionError"), (primary_500, "HTTP 500"), (primary_503, "HTTP 503")]:
        fo = FailoverProvider(primary, fallback)
        resp = await fo.chat(msgs)
        assert primary.calls == 1, f"primary should be called exactly once before failover ({label})"
        assert fo.fallback_triggered is True, f"fallback_triggered must be True for {label}"
        assert fo.last_fallback_reason is not None and len(fo.last_fallback_reason) > 0
        ProviderResponse.model_validate(resp.model_dump(mode="python"))
        assert resp.content == '{"ok":true,"from":"fallback"}'
        assert resp.provider == ProviderType.OLLAMA

    primary_not_failover = _BrokenPrimary(error_type="connection", model="other")
    fo_no = FailoverProvider(primary_not_failover, _WorkingFallback(model="fb"))
    primary_not_failover._error_type = "value"  # non-failover error
    with pytest.raises(ValueError, match="unexpected error type"):
        await fo_no.chat(msgs)
    assert fo_no.fallback_triggered is False, "non-failover exceptions must NOT trigger fallback"
