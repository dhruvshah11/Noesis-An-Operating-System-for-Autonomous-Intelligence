"""
Hexagonal architecture — *ports* (abstract boundaries, driven side).

Every persistence / network / system touchpoint in Noesis is accessed
through an abstract ABC declared in this module.  This is what lets us:

* swap providers in integration tests (``FakeChatPort`` instead of hitting
  OpenAI for the 900th time in CI)
* swap persistence layers (SQLite -> Postgres -> Spanner) without touching
  the agent / service layer
* audit the dependency graph — the ``astra.core`` package never imports
  ``astra.llm.openai_provider`` or ``astra.database.sql``
* load plugins via pluggy and wire them through DI without changing service
  constructors

Adapters live next to the concrete technology they wrap (e.g.
``astra.adapters.db.sql_repo``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Literal, TypeVar
from uuid import UUID

from noesis.types import (
    Artifact,
    ChatMessage,
    Conversation,
    Document,
    Embedding,
    KnowledgeObject,
    Memory,
    Message,
    Page,
    PageParams,
    ProviderResponse,
    TaskExecution,
    User,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterable, Sequence
    from datetime import datetime

# ---------------------------------------------------------------------------
# LLM provider ports
# ---------------------------------------------------------------------------


class ChatPort(ABC):
    """Turn-taking chat with an LLM — possibly with tool-calling support."""

    provider_id: str
    model: str
    temperature: float
    max_tokens: int

    @abstractmethod
    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
        system_prompt: str | None = None,
        **override_kwargs: object,
    ) -> ProviderResponse: ...

    async def chat_stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: list[dict] | None = None,
        system_prompt: str | None = None,
        **override_kwargs: object,
    ) -> Iterable[str]:
        """Optional streaming override — default yields content in one chunk."""
        response = await self.chat(messages, tools=tools, system_prompt=system_prompt, **override_kwargs)
        if response.content:
            yield response.content


class EmbeddingPort(ABC):
    """Produce dense embeddings for semantic search / RAG."""

    provider_id: str
    model: str
    dimensions: int

    @abstractmethod
    async def embed(self, texts: Sequence[str]) -> list[Embedding]: ...


# ---------------------------------------------------------------------------
# Repository ports (persistence, CRUD + paginated reads)
# ---------------------------------------------------------------------------

_KT = TypeVar("_KT")  # primary key type, usually UUID
_T = TypeVar("_T")


class RepositoryPort[T, KT](ABC):
    """Minimal pure-CRUD interface; domain repos extend with custom finders."""

    @abstractmethod
    async def get(self, id: _KT) -> _T | None: ...
    @abstractmethod
    async def create(self, entity: _T) -> _T: ...
    @abstractmethod
    async def update(self, entity: _T) -> _T: ...
    @abstractmethod
    async def delete(self, id: _KT) -> bool: ...
    @abstractmethod
    async def list(self, params: PageParams) -> Page[_T]: ...


class UserRepositoryPort(RepositoryPort[User, UUID]):
    @abstractmethod
    async def get_by_email(self, email: str) -> User | None: ...
    @abstractmethod
    async def get_by_sub(self, auth0_sub: str) -> User | None: ...


class ConversationRepositoryPort(RepositoryPort[Conversation, UUID]):
    @abstractmethod
    async def list_for_user(self, user_id: UUID, params: PageParams) -> Page[Conversation]: ...


class MessageRepositoryPort(RepositoryPort[Message, UUID]):
    @abstractmethod
    async def list_for_conversation(self, conversation_id: UUID, params: PageParams) -> Page[Message]: ...


class MemoryRepositoryPort(RepositoryPort[Memory, UUID]):
    @abstractmethod
    async def list_for_scope(
        self,
        *,
        scope: Literal["user", "project", "team", "system"],
        scope_id: str | None,
        params: PageParams,
    ) -> Page[Memory]: ...
    @abstractmethod
    async def search_by_similarity(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 10,
        scope: str | None = None,
    ) -> list[Memory]: ...


class DocumentRepositoryPort(RepositoryPort[Document, UUID]):
    @abstractmethod
    async def search_by_similarity(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 10,
        namespace: str | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[Document, float]]: ...


class TaskExecutionRepositoryPort(RepositoryPort[TaskExecution, UUID]):
    @abstractmethod
    async def list_for_run(self, run_id: UUID, params: PageParams) -> Page[TaskExecution]: ...


class ArtifactRepositoryPort(RepositoryPort[Artifact, UUID]):
    """Persist UAP / task artifacts with content-addressable (sha256) lookup."""

    @abstractmethod
    async def list_for_task(self, task_id: UUID, params: PageParams) -> Page[Artifact]: ...
    @abstractmethod
    async def find_by_sha256(self, sha256: str) -> Artifact | None: ...


class KnowledgeObjectRepositoryPort(RepositoryPort[KnowledgeObject, UUID]):
    """The filesystem-analogue of Noesis — first-class Knowledge Objects."""

    @abstractmethod
    async def list_for_workspace(
        self,
        workspace_id: UUID,
        params: PageParams,
        *,
        kind: str | None = None,
    ) -> Page[KnowledgeObject]: ...
    @abstractmethod
    async def search_by_tag(
        self,
        tags: list[str],
        params: PageParams,
        *,
        workspace_id: UUID | None = None,
    ) -> Page[KnowledgeObject]: ...
    @abstractmethod
    async def list_versions(self, parent_id: UUID, params: PageParams) -> Page[KnowledgeObject]: ...


# ---------------------------------------------------------------------------
# Vector store port (Qdrant / pgvector / Milvus adapter lives in adapters/)
# ---------------------------------------------------------------------------


class VectorStorePort(ABC):
    """Embedding-index: upsert / search with metadata filtering."""

    @abstractmethod
    async def upsert(
        self,
        *,
        collection: str,
        ids: list[str],
        embeddings: list[list[float]],
        payloads: list[dict[str, Any]] | None = None,
    ) -> None: ...
    @abstractmethod
    async def search(
        self,
        *,
        collection: str,
        query_embedding: list[float],
        top_k: int,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...
    @abstractmethod
    async def delete(self, *, collection: str, ids: list[str]) -> None: ...


# ---------------------------------------------------------------------------
# Cache port (Redis / DiskCache / memory)
# ---------------------------------------------------------------------------


class CachePort(ABC):
    """String-keyed cache with optional TTL."""

    @abstractmethod
    async def get(self, key: str) -> bytes | None: ...
    @abstractmethod
    async def set(self, key: str, value: bytes, ttl_s: int | None = None) -> None: ...
    @abstractmethod
    async def delete(self, key: str) -> bool: ...
    @abstractmethod
    async def clear(self) -> None: ...


# ---------------------------------------------------------------------------
# Clock + IdGenerator (make services deterministic in tests)
# ---------------------------------------------------------------------------


class ClockPort(ABC):
    """Time source — swapped to a deterministic clock in unit tests."""

    @abstractmethod
    def now(self) -> datetime: ...


class IdGenPort(ABC):
    """ID source — swapped to predictable values in snapshot tests."""

    @abstractmethod
    def new(self) -> UUID: ...


# ---------------------------------------------------------------------------
# Event bus — CQRS writes publish here, read projections / async workers subscribe
# ---------------------------------------------------------------------------

DomainEventPayload = dict[str, Any]


class EventHandler:
    """Subscriber signature: ``fn(event_name, payload) -> Awaitable[None]``."""

    __slots__ = ()


class EventBusPort(ABC):
    @abstractmethod
    async def publish(self, event_name: str, payload: DomainEventPayload) -> None: ...
    @abstractmethod
    def subscribe(self, event_name: str, handler: Callable[[DomainEventPayload], Awaitable[None]]) -> None: ...
