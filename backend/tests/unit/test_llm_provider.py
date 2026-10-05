"""
Unit tests for the LLM provider layer.

Tests do NOT hit real network endpoints — they exercise the Strategy +
Factory patterns using a stub provider subclass.  Real HTTP calls are
covered by ``tests/integration/`` (excluded from default CI runs).
"""

from __future__ import annotations

import pytest

from noesis.llm.base import BaseProvider
from noesis.llm.factory import get_provider
from noesis.types import (
    ChatMessage,
    MessageRole,
    ProviderResponse,
    ProviderType,
    TokenUsage,
)

# -------- A fake provider for strategy-level testing --------------------


class FakeProvider(BaseProvider):
    provider_id = "fake"

    def __init__(self, *, echo: bool = True, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._echo = echo
        self.calls: list[list[ChatMessage]] = []

    async def _chat_impl(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict] | None,
        tool_choice: str | dict | None,
        **override_kwargs: object,
    ) -> ProviderResponse:
        self.calls.append(messages)
        last = messages[-1]
        content = last.content or ""
        if self._echo:
            content = f"ECHO:{content}"
        usage = TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2)
        return ProviderResponse(
            provider=ProviderType.OPENAI,
            model=self.model,
            content=content,
            tool_calls=[],
            usage=usage,
            latency_ms=1.23,
            finish_reason="stop",
        )


@pytest.fixture
def fake() -> FakeProvider:
    return FakeProvider(model="fake-model", temperature=0.0, max_tokens=32)


# ---------------------------------------------------------------------------


async def test_base_provider_chat_prepends_system_prompt(fake: FakeProvider) -> None:
    msgs = [ChatMessage(role=MessageRole.USER, content="hi")]
    response = await fake.chat(msgs, system_prompt="SYSPROMPT")
    assert response.content == "ECHO:hi"
    called_with = fake.calls[0]
    assert len(called_with) == 2
    assert called_with[0].role == MessageRole.SYSTEM
    assert called_with[0].content == "SYSPROMPT"
    assert called_with[1].role == MessageRole.USER


async def test_base_provider_accumulates_usage(fake: FakeProvider) -> None:
    msgs = [ChatMessage(role=MessageRole.USER, content="hi")]
    assert fake.total_usage.total_tokens == 0
    await fake.chat(msgs)
    # One request returns usage (1,1,2); public chat() adds it once.
    assert fake.total_usage.total_tokens == 2
    await fake.chat(msgs)
    assert fake.total_usage.total_tokens == 4  # 2 * 2
    fake.reset_usage()
    assert fake.total_usage.total_tokens == 0


async def test_base_provider_chat_stream_default_impl_yields_once(fake: FakeProvider) -> None:
    msgs = [ChatMessage(role=MessageRole.USER, content="x")]
    chunks = [c async for c in fake.chat_stream(msgs)]
    assert chunks == ["ECHO:x"]


# -------- ProviderFactory validation ------------------------------------


def test_factory_errors_when_credential_missing(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Asking for OpenAI without OPENAI_API_KEY set must fail clearly."""
    monkeypatch.setenv("SECRET_KEY", "abc")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from noesis.config import get_settings

    get_settings.cache_clear()

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        get_provider("openai", model="gpt-4o-mini")


def test_factory_ollama_no_creds_needed(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("SECRET_KEY", "abc")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    from noesis.config import get_settings

    get_settings.cache_clear()

    p = get_provider("ollama", model="llama3")
    assert p.provider_id == "ollama"
    assert p.model == "llama3"
    assert hasattr(p, "_base_url")
    assert p._base_url == "http://localhost:11434"


def test_ollama_provider_url_parse_handles_trailing_slash_and_v1_suffix(
    monkeypatch,
) -> None:
    """K2/W1: Ensure base_url is normalised regardless of user formatting."""
    from noesis.llm.ollama_provider import OllamaProvider

    cases = [
        ("http://localhost:11434", "http://localhost:11434"),
        ("http://localhost:11434/", "http://localhost:11434"),
        ("http://localhost:11434/v1", "http://localhost:11434/v1"),
        ("https://ollama.internal.corp.example.com:11434/v1/", "https://ollama.internal.corp.example.com:11434/v1"),
    ]
    for raw, expected in cases:
        provider = OllamaProvider(base_url=raw, model="qwen2.5-coder:7b")
        assert provider._base_url == expected, f"OllamaProvider({raw!r})._base_url should normalise to {expected!r} but got {provider._base_url!r}"


def test_factory_anthropic_requires_credentials(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("SECRET_KEY", "abc")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from noesis.config import get_settings

    get_settings.cache_clear()

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        get_provider("anthropic", model="claude-sonnet-4")
