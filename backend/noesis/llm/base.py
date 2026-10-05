"""
Provider abstract base classes.

Design notes
------------
We deliberately keep the surface area small:

* :meth:`BaseProvider.chat` — conversation / tool-calling entry point.
* :meth:`BaseProvider.chat_stream` — streaming variant of chat.
* :meth:`EmbeddingProvider.embed` — produce a list of embedding vectors.

Every provider implementation must convert its native response shape into
the standard :class:`ProviderResponse` / :class:`Embedding` types from
:mod:`astra.types`. This keeps the rest of the system completely
provider-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from noesis.types import ChatMessage, Embedding, ProviderResponse, TokenUsage

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence


class BaseProvider(ABC):
    """Abstract base class for all chat-completion providers."""

    provider_id: str = "base"

    def __init__(
        self,
        *,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout: float = 120.0,
        **kwargs: object,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.extra_kwargs = kwargs
        self._total_usage = TokenUsage()

    # ---- Public API ---------------------------------------------------

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
        system_prompt: str | None = None,
        **override_kwargs: object,
    ) -> ProviderResponse:
        """Send a chat request and return a :class:`ProviderResponse`.

        Parameters
        ----------
        messages:
            Conversation history. ``system_prompt`` is prepended as a
            system message if provided — avoids mutating the input list.
        tools:
            JSONSchema-style tool definitions.  Shape matches the OpenAI
            spec; providers translate to their own representation.
        tool_choice:
            ``"auto"``, ``"required"``, ``"none"``, or
            ``{"type": "function", "function": {"name": …}}``.
        system_prompt:
            Optional leading system message.
        override_kwargs:
            Any provider-specific kwarg (e.g. ``top_p``, ``stop``).
        """
        effective_messages = list(messages)
        if system_prompt:
            from noesis.types import MessageRole

            effective_messages.insert(0, ChatMessage(role=MessageRole.SYSTEM, content=system_prompt))
        response = await self._chat_impl(
            effective_messages,
            tools=tools,
            tool_choice=tool_choice,
            **override_kwargs,
        )
        self._total_usage += response.usage
        return response

    async def chat_stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: list[dict] | None = None,
        system_prompt: str | None = None,
        **override_kwargs: object,
    ) -> AsyncIterator[str]:
        """Streaming chat — yields partial delta strings.

        The default implementation calls :meth:`chat` and yields the
        full content in one chunk; providers override with native SSE /
        streaming HTTP transports for true incremental output.
        """
        response = await self.chat(
            messages,
            tools=tools,
            system_prompt=system_prompt,
            **override_kwargs,
        )
        if response.content:
            yield response.content

    @property
    def total_usage(self) -> TokenUsage:
        """Cumulative tokens used by this provider instance."""
        return self._total_usage

    def reset_usage(self) -> None:
        self._total_usage = TokenUsage()

    # ---- Hook for subclasses -----------------------------------------

    @abstractmethod
    async def _chat_impl(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict] | None,
        tool_choice: str | dict | None,
        **override_kwargs: object,
    ) -> ProviderResponse:
        """Provider-specific chat-completion implementation."""
        raise NotImplementedError


class EmbeddingProvider(ABC):
    """Abstract base class for text-embedding providers."""

    provider_id: str = "base"

    def __init__(self, *, model: str, dimensions: int, timeout: float = 120.0) -> None:
        self.model = model
        self.dimensions = dimensions
        self.timeout = timeout
        self._total_usage = TokenUsage()

    @abstractmethod
    async def embed(self, texts: Sequence[str]) -> list[Embedding]:
        """Embed one or more text strings.  Must match ``self.dimensions``."""
        raise NotImplementedError

    @property
    def total_usage(self) -> TokenUsage:
        return self._total_usage

    def reset_usage(self) -> None:
        self._total_usage = TokenUsage()
