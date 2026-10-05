"""
In-memory implementations of every RepositoryPort ABC.

Purpose:
  * Unit tests that don't need SQLAlchemy (fast, deterministic, no DB lock issues).
  * Standalone kernel bootstrapping in tests without a database.
  * Fast-fake implementations used by PluginManager isolation tests.

Every ``InMemoryXRepository`` implements the exact same ABC as its SQL
sibling so callers receive LSP-compliant behaviour.  Keyset pagination
uses numeric offsets translated from UUID cursors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal
from uuid import UUID

from noesis.core.ports import (
    ArtifactRepositoryPort,
    ConversationRepositoryPort,
    DocumentRepositoryPort,
    KnowledgeObjectRepositoryPort,
    MemoryRepositoryPort,
    MessageRepositoryPort,
    Page,
    PageParams,
    RepositoryPort,
    TaskExecutionRepositoryPort,
    UserRepositoryPort,
)
from noesis.types import (
    Artifact,
    Conversation,
    Document,
    KnowledgeObject,
    Memory,
    Message,
    TaskExecution,
    User,
)

if TYPE_CHECKING:
    from collections.abc import Callable

_T = object
_ID = object


def _page[T](rows: list[T], params: PageParams, *, key: Callable[[T], UUID]) -> Page[T]:
    """Python-side keyset pagination using UUID ordering."""
    sorted_rows = sorted(rows, key=lambda r: str(key(r)))
    start_idx = 0
    if params.cursor:
        try:
            cursor = UUID(params.cursor)
        except ValueError:
            cursor = None
        if cursor is not None:
            cursor_str = str(cursor)
            start_idx = next(
                (i for i, r in enumerate(sorted_rows) if str(key(r)) > cursor_str),
                len(sorted_rows),
            )
    window = sorted_rows[start_idx : start_idx + params.limit + 1]
    has_more = len(window) > params.limit
    if has_more:
        window = window[: params.limit]
    next_cursor: str | None = None
    if has_more and window:
        next_cursor = str(key(window[-1]))
    return Page(
        items=window,
        total=len(sorted_rows),
        next_cursor=next_cursor,
        has_more=has_more,
    )


class _BaseInMemoryRepo[T, I](RepositoryPort[T, I]):
    """Shared implementation for the common CRUD/Page skeleton."""

    def __init__(self) -> None:
        self._rows: dict[UUID, T] = {}
        self._pk_attr: str = "id"

    async def get(self, id: I) -> T | None:  # type: ignore[override]
        return self._rows.get(UUID(str(id)))

    async def create(self, entity: T) -> T:  # type: ignore[override]
        pk = getattr(entity, self._pk_attr)
        self._rows[UUID(str(pk))] = entity
        return entity

    async def update(self, entity: T) -> T:  # type: ignore[override]
        pk = UUID(str(getattr(entity, self._pk_attr)))
        if pk not in self._rows:
            raise KeyError(f"{type(entity).__name__} {pk} not found")
        self._rows[pk] = entity
        return entity

    async def delete(self, id: I) -> bool:  # type: ignore[override]
        return bool(self._rows.pop(UUID(str(id)), None))

    async def list(self, params: PageParams) -> Page[T]:  # type: ignore[override]
        rows = list(self._rows.values())
        return _page(rows, params, key=lambda r: UUID(str(getattr(r, self._pk_attr))))


class InMemoryUserRepository(_BaseInMemoryRepo[User, UUID], UserRepositoryPort):
    async def get_by_email(self, email: str) -> User | None:
        needle = email.lower()
        for u in self._rows.values():
            if u.email.lower() == needle:
                return u
        return None

    async def get_by_sub(self, auth0_sub: str) -> User | None:
        for u in self._rows.values():
            if u.external_id == auth0_sub:
                return u
        return None


class InMemoryConversationRepository(_BaseInMemoryRepo[Conversation, UUID], ConversationRepositoryPort):
    async def list_for_user(self, user_id: UUID, params: PageParams) -> Page[Conversation]:  # type: ignore[override]
        rows = [c for c in self._rows.values() if c.user_id == str(user_id)]
        return _page(rows, params, key=lambda r: r.id)


class InMemoryMessageRepository(_BaseInMemoryRepo[Message, UUID], MessageRepositoryPort):
    async def list_for_conversation(self, conversation_id: UUID, params: PageParams) -> Page[Message]:  # type: ignore[override]
        rows = [m for m in self._rows.values() if m.conversation_id == conversation_id]
        return _page(rows, params, key=lambda r: r.id)


class InMemoryMemoryRepository(_BaseInMemoryRepo[Memory, UUID], MemoryRepositoryPort):
    async def list_for_scope(
        self,
        *,
        scope: Literal["user", "project", "team", "system"],
        scope_id: str | None,
        params: PageParams,
    ) -> Page[Memory]:  # type: ignore[override]
        rows = list(self._rows.values())
        if scope == "system":
            rows = [m for m in rows if not m.user_id]
        elif scope == "user" and scope_id:
            rows = [m for m in rows if m.user_id == scope_id]
        return _page(rows, params, key=lambda r: r.id)

    async def search_by_similarity(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 10,
        scope: str | None = None,
    ) -> list[Memory]:
        # In-memory similarity is intentionally a stub; vector-store tests
        # go through VectorStorePort implementations.  Returns rows ordered by
        # importance to give test callers deterministic partial ordering.
        rows = list(self._rows.values())
        if scope == "user":
            rows = [m for m in rows if m.user_id]
        elif scope == "system":
            rows = [m for m in rows if not m.user_id]
        rows.sort(key=lambda m: m.importance, reverse=True)
        return rows[:top_k]


class InMemoryDocumentRepository(_BaseInMemoryRepo[Document, UUID], DocumentRepositoryPort):
    async def search_by_similarity(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 10,
        namespace: str | None = None,
        metadata_filter: dict | None = None,
    ) -> list[tuple[Document, float]]:
        # Stub: returns empty results with distance 0.0.  Real similarity uses
        # VectorStorePort + join back to document IDs.
        return []


class InMemoryTaskExecutionRepository(_BaseInMemoryRepo[TaskExecution, UUID], TaskExecutionRepositoryPort):
    async def list_for_run(self, run_id: UUID, params: PageParams) -> Page[TaskExecution]:  # type: ignore[override]
        run_s = str(run_id)
        rows = [t for t in self._rows.values() if run_s in (t.run_id, t.conversation_id)]
        return _page(rows, params, key=lambda r: r.id)


class InMemoryArtifactRepository(_BaseInMemoryRepo[Artifact, UUID], ArtifactRepositoryPort):
    async def list_for_task(self, task_id: UUID, params: PageParams) -> Page[Artifact]:  # type: ignore[override]
        task_s = str(task_id)
        rows = [a for a in self._rows.values() if a.task_id == task_s]
        return _page(rows, params, key=lambda r: r.id)

    async def find_by_sha256(self, sha256: str) -> Artifact | None:
        for a in self._rows.values():
            if a.sha256 == sha256:
                return a
        return None


class InMemoryKnowledgeObjectRepository(_BaseInMemoryRepo[KnowledgeObject, UUID], KnowledgeObjectRepositoryPort):
    async def list_for_workspace(
        self,
        workspace_id: UUID,
        params: PageParams,
        *,
        kind: str | None = None,
    ) -> Page[KnowledgeObject]:  # type: ignore[override]
        ws = str(workspace_id)
        rows = [k for k in self._rows.values() if k.workspace_id == ws]
        if kind:
            rows = [k for k in rows if k.kind == kind]
        return _page(rows, params, key=lambda r: r.id)

    async def search_by_tag(
        self,
        tags: list[str],
        params: PageParams,
        *,
        workspace_id: UUID | None = None,
    ) -> Page[KnowledgeObject]:  # type: ignore[override]
        rows = list(self._rows.values())
        if workspace_id is not None:
            ws = str(workspace_id)
            rows = [k for k in rows if k.workspace_id == ws]
        rows = [k for k in rows if any(t in k.tags for t in tags)]
        return _page(rows, params, key=lambda r: r.id)

    async def list_versions(self, parent_id: UUID, params: PageParams) -> Page[KnowledgeObject]:  # type: ignore[override]
        parent = str(parent_id)
        rows = [k for k in self._rows.values() if k.parent_id == parent]
        rows.sort(key=lambda k: k.version, reverse=True)
        # For ordered list (not keyed-by-UUID), do slice pagination
        start_idx = 0
        if params.cursor:
            try:
                start_idx = max(0, int(params.cursor))
            except ValueError:
                start_idx = 0
        window = rows[start_idx : start_idx + params.limit + 1]
        has_more = len(window) > params.limit
        if has_more:
            window = window[: params.limit]
        next_cursor: str | None = None
        if has_more:
            next_cursor = str(start_idx + params.limit)
        return Page(items=window, total=len(rows), next_cursor=next_cursor, has_more=has_more)
