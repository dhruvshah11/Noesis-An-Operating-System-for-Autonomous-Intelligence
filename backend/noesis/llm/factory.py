"""
Provider factory — the single entry point for instantiating providers.

Usage::

    from noesis.llm import get_provider
    provider = get_provider("openai", model="gpt-4o-mini")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from httpx import HTTPStatusError

from noesis.config import get_settings
from noesis.llm._retry import HTTPRetryableError
from noesis.llm.base import BaseProvider
from noesis.logging import get_logger
from noesis.types import ChatMessage, ProviderResponse, ProviderType

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Sequence

    from noesis.llm.base import EmbeddingProvider

log = get_logger(__name__)

_FAILOVER_EXCEPTIONS = (ConnectionError, HTTPRetryableError)


def _is_http_5xx(exc: BaseException) -> bool:
    if isinstance(exc, HTTPRetryableError):
        return 500 <= exc.status_code <= 599
    if isinstance(exc, HTTPStatusError):
        return 500 <= exc.response.status_code <= 599
    return False


def _require_credentials(provider: str, key_value: str | None, env_var: str) -> None:
    """Raise a helpful error if a required credential is missing."""
    if not key_value:
        raise RuntimeError(f"Cannot create {provider!r} provider: credential {env_var} is not set. Add it to your `.env` file or environment.")


class FailoverProvider(BaseProvider):
    """Wraps a primary + fallback provider; retries on ConnectionError / HTTP 5xx."""

    provider_id = "failover"

    def __init__(self, primary: BaseProvider, fallback: BaseProvider, **kwargs: object) -> None:
        super().__init__(model=primary.model, **{k: v for k, v in kwargs.items() if k not in {"model"}})
        self._primary = primary
        self._fallback = fallback
        self.fallback_triggered = False
        self.last_fallback_reason: str | None = None

    async def _chat_impl(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict] | None,
        tool_choice: str | dict | None,
        **override_kwargs: object,
    ) -> ProviderResponse:
        try:
            return await self._primary._chat_impl(messages, tools=tools, tool_choice=tool_choice, **override_kwargs)
        except Exception as exc:
            is_failover_case = isinstance(exc, _FAILOVER_EXCEPTIONS) or _is_http_5xx(exc)
            if not is_failover_case:
                raise
            reason = f"{type(exc).__name__}: {exc!s:.200}"
            log.warning(
                "llm.failover",
                primary=self._primary.provider_id,
                fallback=self._fallback.provider_id,
                reason=reason,
            )
            self.fallback_triggered = True
            self.last_fallback_reason = reason
            return await self._fallback._chat_impl(messages, tools=tools, tool_choice=tool_choice, **override_kwargs)

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
        system_prompt: str | None = None,
        **override_kwargs: object,
    ) -> ProviderResponse:
        try:
            return await super().chat(
                messages,
                tools=tools,
                tool_choice=tool_choice,
                system_prompt=system_prompt,
                **override_kwargs,
            )
        except Exception as exc:
            is_failover_case = isinstance(exc, _FAILOVER_EXCEPTIONS) or _is_http_5xx(exc)
            if not is_failover_case:
                raise
            reason = f"{type(exc).__name__}: {exc!s:.200}"
            log.warning(
                "llm.failover",
                primary=self._primary.provider_id,
                fallback=self._fallback.provider_id,
                reason=reason,
            )
            self.fallback_triggered = True
            self.last_fallback_reason = reason
            effective = list(messages)
            if system_prompt:
                from noesis.types import MessageRole

                effective.insert(0, ChatMessage(role=MessageRole.SYSTEM, content=system_prompt))
            resp = await self._fallback._chat_impl(effective, tools=tools, tool_choice=tool_choice, **override_kwargs)
            self._total_usage += resp.usage
            return resp

    async def chat_stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: list[dict] | None = None,
        system_prompt: str | None = None,
        **override_kwargs: object,
    ) -> object:
        try:
            async for chunk in self._primary.chat_stream(
                messages,
                tools=tools,
                system_prompt=system_prompt,
                **override_kwargs,
            ):
                yield chunk
            return
        except Exception as exc:
            is_failover_case = isinstance(exc, _FAILOVER_EXCEPTIONS) or _is_http_5xx(exc)
            if not is_failover_case:
                raise
            reason = f"{type(exc).__name__}: {exc!s:.200}"
            log.warning("llm.failover_stream", primary=self._primary.provider_id, fallback=self._fallback.provider_id, reason=reason)
            self.fallback_triggered = True
            self.last_fallback_reason = reason
            async for chunk in self._fallback.chat_stream(
                messages,
                tools=tools,
                system_prompt=system_prompt,
                **override_kwargs,
            ):
                yield chunk

    async def aclose(self) -> None:
        for p in (self._primary, self._fallback):
            close = getattr(p, "aclose", None)
            if callable(close):
                try:
                    await close()
                except Exception:
                    pass


def _build_raw_provider(
    provider: str | ProviderType | None = None,
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    **kwargs: object,
) -> BaseProvider:
    """Instantiate a concrete :class:`BaseProvider` by name (no failover wrapper)."""
    settings = get_settings()
    provider_type = ProviderType(provider or settings.default_provider)
    effective_model = model or settings.default_model
    effective_temperature = settings.temperature if temperature is None else temperature
    effective_max_tokens = settings.max_tokens if max_tokens is None else max_tokens
    timeout = settings.timeout

    if provider_type is ProviderType.OPENAI:
        from noesis.llm.openai_provider import OpenAIProvider

        _require_credentials("openai", settings.openai_api_key and settings.openai_api_key.get_secret_value(), "OPENAI_API_KEY")
        return OpenAIProvider(
            model=effective_model,
            temperature=effective_temperature,
            max_tokens=effective_max_tokens,
            timeout=timeout,
            api_key=settings.openai_api_key.get_secret_value() if settings.openai_api_key else None,
            base_url=str(settings.openai_base_url) if settings.openai_base_url else None,
            org_id=settings.openai_org_id,
            **kwargs,
        )

    if provider_type is ProviderType.ANTHROPIC:
        from noesis.llm.anthropic_provider import AnthropicProvider

        _require_credentials("anthropic", settings.anthropic_api_key and settings.anthropic_api_key.get_secret_value(), "ANTHROPIC_API_KEY")
        return AnthropicProvider(
            model=effective_model,
            temperature=effective_temperature,
            max_tokens=effective_max_tokens,
            timeout=timeout,
            api_key=settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None,
            base_url=str(settings.anthropic_base_url) if settings.anthropic_base_url else None,
            **kwargs,
        )

    if provider_type is ProviderType.GEMINI:
        from noesis.llm.gemini_provider import GeminiProvider

        _require_credentials("gemini", settings.google_api_key and settings.google_api_key.get_secret_value(), "GOOGLE_API_KEY")
        return GeminiProvider(
            model=effective_model,
            temperature=effective_temperature,
            max_tokens=effective_max_tokens,
            timeout=timeout,
            api_key=settings.google_api_key.get_secret_value() if settings.google_api_key else None,
            **kwargs,
        )

    if provider_type is ProviderType.OLLAMA:
        from noesis.llm.ollama_provider import OllamaProvider

        return OllamaProvider(
            model=effective_model,
            temperature=effective_temperature,
            max_tokens=effective_max_tokens,
            timeout=timeout,
            base_url=str(settings.ollama_base_url),
            **kwargs,
        )

    if provider_type is ProviderType.OPENROUTER:
        from noesis.llm.openrouter_provider import OpenRouterProvider

        _require_credentials("openrouter", settings.openrouter_api_key and settings.openrouter_api_key.get_secret_value(), "OPENROUTER_API_KEY")
        return OpenRouterProvider(
            model=effective_model,
            temperature=effective_temperature,
            max_tokens=effective_max_tokens,
            timeout=timeout,
            api_key=settings.openrouter_api_key.get_secret_value() if settings.openrouter_api_key else None,
            base_url=str(settings.openrouter_base_url),
            **kwargs,
        )

    if provider_type is ProviderType.LLAMACPP:
        from noesis.llm.openai_provider import OpenAIProvider

        return OpenAIProvider(
            model=effective_model,
            temperature=effective_temperature,
            max_tokens=effective_max_tokens,
            timeout=timeout,
            api_key="llamacpp-no-key-required",
            base_url=str(settings.llamacpp_base_url),
            **kwargs,
        )

    raise AssertionError(f"Unhandled provider {provider_type!r}")  # pragma: no cover


def get_provider(
    provider: str | ProviderType | None = None,
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    use_fallback: bool = True,
    **kwargs: object,
) -> BaseProvider:
    """Instantiate a concrete :class:`BaseProvider` by name with failover support.

    If ``use_fallback`` is True (default) and the configured ``fallback_provider``
    differs from the primary, the returned provider wraps both and transparently
    retries on ConnectionError / HTTP 5xx.
    """
    settings = get_settings()
    primary = _build_raw_provider(provider, model=model, temperature=temperature, max_tokens=max_tokens, **kwargs)
    if not use_fallback:
        return primary
    primary_type = ProviderType(provider or settings.default_provider)
    fallback_type = ProviderType(settings.fallback_provider)
    if fallback_type == primary_type:
        return primary
    try:
        fallback = _build_raw_provider(fallback_type, model=model, temperature=temperature, max_tokens=max_tokens, **kwargs)
    except Exception as exc:
        log.warning("llm.fallback_build_failed", fallback=fallback_type.value, error=str(exc)[:200])
        return primary
    return FailoverProvider(primary, fallback)


def get_embedding_provider(
    provider: str | ProviderType | None = None,
    *,
    model: str | None = None,
    dimensions: int | None = None,
) -> EmbeddingProvider:
    """Instantiate an :class:`EmbeddingProvider` for semantic search / RAG."""
    settings = get_settings()
    provider_type = ProviderType(provider or settings.embedding_provider)
    effective_model = model or settings.embedding_model
    effective_dims = dimensions or settings.embedding_dimensions

    if provider_type is ProviderType.OPENAI:
        from noesis.llm.openai_provider import OpenAIEmbeddingProvider

        _require_credentials("openai", settings.openai_api_key and settings.openai_api_key.get_secret_value(), "OPENAI_API_KEY")
        return OpenAIEmbeddingProvider(
            model=effective_model,
            dimensions=effective_dims,
            timeout=settings.timeout,
            api_key=settings.openai_api_key.get_secret_value() if settings.openai_api_key else None,
            base_url=str(settings.openai_base_url) if settings.openai_base_url else None,
        )

    if provider_type is ProviderType.OLLAMA:
        from noesis.llm.ollama_provider import OllamaEmbeddingProvider

        return OllamaEmbeddingProvider(
            model=effective_model,
            dimensions=effective_dims,
            timeout=settings.timeout,
            base_url=str(settings.ollama_base_url),
        )

    raise ValueError(f"Embedding provider {provider_type!r} is not supported. Use 'openai' or 'ollama'.")
