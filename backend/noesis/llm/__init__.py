"""
Pluggable LLM provider layer.

Agents code against :class:`BaseProvider` — instantiate concrete
implementations via :func:`astra.llm.factory.get_provider`.
"""

from noesis.llm.base import BaseProvider, EmbeddingProvider
from noesis.llm.factory import get_embedding_provider, get_provider

__all__ = [
    "BaseProvider",
    "EmbeddingProvider",
    "get_embedding_provider",
    "get_provider",
]
