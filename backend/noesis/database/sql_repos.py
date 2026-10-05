"""
SQLAlchemy-backed RepositoryPort adapters — the default persistence layer.

Each adapter implements one ``RepositoryPort`` ABC from
``astra.core.ports`` using the ``session_scope`` from :mod:`astra.database.sql`.

Design Notes
------------
* Mappers (``_dto`` / ``_from_dto``) are explicit per ORM class so column
  additions/changes show up as compile errors instead of silent bugs.
* All ``list()`` methods use keyset pagination (``id > cursor``) because
  numeric ``OFFSET`` is quadratic for large tables — a classic production
  footgun on the interview whiteboard.
* ``UUID`` primary keys are round-tripped as strings through cursor values
  because JSON does not have a native UUID type.
* Adapters are **strictly typed**: every override carries ``# type: ignore[override]``
  silence for pydantic v2 covariance quirks (the LSP contract is intact at runtime).
"""

from __future__ import annotations

import json
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import func, select

from noesis.core.ports import (
    ArtifactRepositoryPort,
    ConversationRepositoryPort,
    DocumentRepositoryPort,
    KnowledgeObjectRepositoryPort,
    MemoryRepositoryPort,
    MessageRepositoryPort,
    Page,
    PageParams,
    TaskExecutionRepositoryPort,
    UserRepositoryPort,
)
from noesis.database.sql import session_scope
from noesis.logging import get_logger
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

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Local imports of ORM classes — deferred to keep ports.py independent of SQLAlchemy
# ---------------------------------------------------------------------------

import contextlib

from noesis.database.models import (
    Conversation as ORMConversation,
)
from noesis.database.models import (
    Document as ORMDocument,
)
from noesis.database.models import (
    Memory as ORMMemory,
)
from noesis.database.models import (
    Message as ORMMessage,
)
from noesis.database.models import (
    TaskExecution as ORMTaskExecution,
)
from noesis.database.models import (
    User as ORMUser,
)

# ---------------------------------------------------------------------------
# JSON column helpers — SQLite maps JSON/JSONB columns to String via
# ``JSONB().with_variant(String, "sqlite")``; Python dicts/lists must be
# explicitly serialised to ``str`` before binding to avoid ProgrammingError.
# ---------------------------------------------------------------------------


def _to_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list, tuple, bool, int, float, str)) or value is None:
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, ensure_ascii=False)
        return value
    # Fallback: attempt default json dump for non-primitive types
    return json.dumps(value, ensure_ascii=False, default=str)


def _from_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value
    return value


# ---------------------------------------------------------------------------
# ORM ↔ DTO mappers (column-level — never omit fields intentionally)
# ---------------------------------------------------------------------------


def _user_to_dto(orm: ORMUser) -> User:
    return User(
        id=orm.id,
        email=orm.email,
        full_name=orm.full_name,
        is_active=orm.is_active,
        is_admin=orm.is_admin,
        hashed_password=orm.hashed_password,
        external_id=orm.external_id,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _user_from_dto(dto: User) -> ORMUser:
    return ORMUser(
        id=dto.id,
        email=dto.email,
        full_name=dto.full_name,
        is_active=dto.is_active,
        is_admin=dto.is_admin,
        hashed_password=dto.hashed_password,
        external_id=dto.external_id,
        created_at=dto.created_at,
        updated_at=dto.updated_at,
    )


def _conversation_to_dto(orm: ORMConversation) -> Conversation:
    return Conversation(
        id=orm.id,
        user_id=str(orm.user_id) if orm.user_id else None,
        title=orm.title,
        messages=[],  # lazy; callers load explicitly via messages repo
        created_at=orm.created_at,
        updated_at=orm.updated_at,
        metadata={},
    )


def _conversation_from_dto(dto: Conversation) -> ORMConversation:
    return ORMConversation(
        id=dto.id,
        user_id=UUID(dto.user_id) if dto.user_id else None,
        title=dto.title,
        created_at=dto.created_at,
        updated_at=dto.updated_at,
    )


def _message_to_dto(orm: ORMMessage) -> Message:
    return Message(
        id=orm.id,
        conversation_id=orm.conversation_id,
        role=orm.role,
        content=orm.content,
        name=orm.name,
        tool_call_id=orm.tool_call_id,
        tool_calls=_from_json(orm.tool_calls_json) or [],
        prompt_tokens=orm.prompt_tokens,
        completion_tokens=orm.completion_tokens,
        latency_ms=orm.latency_ms,
        created_at=orm.created_at,
    )


def _message_from_dto(dto: Message) -> ORMMessage:
    return ORMMessage(
        id=dto.id,
        conversation_id=dto.conversation_id,
        role=dto.role,
        content=dto.content,
        name=dto.name,
        tool_call_id=dto.tool_call_id,
        tool_calls_json=_to_json(dto.tool_calls) if dto.tool_calls else None,
        prompt_tokens=dto.prompt_tokens,
        completion_tokens=dto.completion_tokens,
        latency_ms=dto.latency_ms,
        created_at=dto.created_at,
    )


def _memory_to_dto(orm: ORMMemory) -> Memory:
    return Memory(
        id=orm.id,
        user_id=str(orm.user_id) if orm.user_id else None,
        memory_type=orm.memory_type,
        content=orm.content,
        summary=orm.summary,
        importance=orm.importance,
        access_count=orm.access_count,
        is_compressed=orm.is_compressed,
        vector_id=orm.vector_id,
        scope="user" if orm.user_id else "system",
        scope_id=str(orm.user_id) if orm.user_id else None,
        metadata=_from_json(orm.metadata_json) or {},
        created_at=orm.created_at,
        last_accessed_at=orm.last_accessed_at,
    )


def _memory_from_dto(dto: Memory) -> ORMMemory:
    return ORMMemory(
        id=dto.id,
        user_id=UUID(dto.user_id) if dto.user_id else None,
        memory_type=dto.memory_type,
        content=dto.content,
        summary=dto.summary,
        importance=dto.importance,
        access_count=dto.access_count,
        is_compressed=dto.is_compressed,
        vector_id=dto.vector_id,
        metadata_json=_to_json(dto.metadata),
        created_at=dto.created_at,
        last_accessed_at=dto.last_accessed_at,
    )


def _document_to_dto(orm: ORMDocument) -> Document:
    return Document(
        id=orm.id,
        user_id=str(orm.user_id) if orm.user_id else None,
        title=orm.title,
        source_uri=orm.source_uri,
        mime_type=orm.mime_type,
        byte_size=orm.byte_size,
        chunk_count=orm.chunk_count,
        ingestion_status=_cast_ingestion_status(orm.ingestion_status),
        metadata=_from_json(orm.metadata_json) or {},
        created_at=orm.created_at,
    )


def _document_from_dto(dto: Document) -> ORMDocument:
    return ORMDocument(
        id=dto.id,
        user_id=UUID(dto.user_id) if dto.user_id else None,
        title=dto.title,
        source_uri=dto.source_uri,
        mime_type=dto.mime_type,
        byte_size=dto.byte_size,
        chunk_count=dto.chunk_count,
        ingestion_status=dto.ingestion_status,
        metadata_json=_to_json(dto.metadata),
        created_at=dto.created_at,
    )


def _task_execution_to_dto(orm: ORMTaskExecution) -> TaskExecution:
    return TaskExecution(
        id=orm.id,
        conversation_id=str(orm.conversation_id) if orm.conversation_id else None,
        run_id=None,
        plan_step_id=str(orm.plan_step_id) if orm.plan_step_id else None,
        agent_type=orm.agent_type,
        description=orm.description,
        status=orm.status,
        input_tokens=orm.input_tokens,
        output_tokens=orm.output_tokens,
        cost_usd=orm.cost_usd,
        duration_ms=orm.duration_ms,
        error=orm.error,
        result_preview=orm.result_preview,
        metadata={},
        created_at=orm.created_at,
    )


def _task_execution_from_dto(dto: TaskExecution) -> ORMTaskExecution:
    return ORMTaskExecution(
        id=dto.id,
        conversation_id=UUID(dto.conversation_id) if dto.conversation_id else None,
        plan_step_id=UUID(dto.plan_step_id) if dto.plan_step_id else None,
        agent_type=dto.agent_type,
        description=dto.description,
        status=dto.status,
        input_tokens=dto.input_tokens,
        output_tokens=dto.output_tokens,
        cost_usd=dto.cost_usd,
        duration_ms=dto.duration_ms,
        error=dto.error,
        result_preview=dto.result_preview,
        created_at=dto.created_at,
    )


def _cast_ingestion_status(raw: str) -> Literal["pending", "processing", "ready", "failed"]:
    if raw in {"pending", "processing", "ready", "failed"}:
        return raw  # type: ignore[return-value]
    return "pending"


# ---------------------------------------------------------------------------
# Shared helper: keyset pagination builder
# ---------------------------------------------------------------------------


async def _paginate_query(
    stmt,
    *,
    params: PageParams,
    pk_column,
    session,
    mapper,
) -> tuple[list[Any], int | None, str | None]:
    """Execute a paginated select using keyset (cursor) pagination.

    Returns
    -------
    ``(items, total, next_cursor_str)``
    """
    if params.cursor:
        try:
            cursor_uuid = UUID(params.cursor)
        except ValueError:
            cursor_uuid = None
        if cursor_uuid is not None:
            stmt = stmt.where(pk_column > cursor_uuid)
    stmt = stmt.order_by(pk_column.asc()).limit(params.limit + 1)
    result = await session.execute(stmt)
    rows: list = list(result.scalars().all())
    next_cursor: str | None = None
    has_more = len(rows) > params.limit
    if has_more:
        rows = rows[: params.limit]
        next_cursor = str(rows[-1].id)
    total: int | None = None
    try:
        count_stmt = select(func.count()).select_from(stmt.subquery().alias())
        count_result = await session.execute(count_stmt)
        total = int(count_result.scalar_one() or 0)
    except Exception:  # pragma: no cover - DB engine differences
        total = None
    items = [mapper(r) for r in rows]
    return items, total, next_cursor


# ---------------------------------------------------------------------------
# Repository implementations
# ---------------------------------------------------------------------------


class SqlUserRepository(UserRepositoryPort):
    async def get(self, id: UUID) -> User | None:  # type: ignore[override]
        async with session_scope() as s:
            orm = await s.get(ORMUser, id)
            return _user_to_dto(orm) if orm else None

    async def create(self, entity: User) -> User:  # type: ignore[override]
        async with session_scope() as s:
            orm = _user_from_dto(entity)
            s.add(orm)
            await s.flush()
            return _user_to_dto(orm)

    async def update(self, entity: User) -> User:  # type: ignore[override]
        async with session_scope() as s:
            orm = await s.get(ORMUser, entity.id)
            if orm is None:
                raise KeyError(f"User {entity.id} not found")
            for k, v in entity.model_dump(exclude={"id", "created_at"}).items():
                setattr(orm, k, v)
            await s.flush()
            return _user_to_dto(orm)

    async def delete(self, id: UUID) -> bool:  # type: ignore[override]
        async with session_scope() as s:
            orm = await s.get(ORMUser, id)
            if orm is None:
                return False
            await s.delete(orm)
            return True

    async def list(self, params: PageParams) -> Page[User]:  # type: ignore[override]
        async with session_scope() as s:
            stmt = select(ORMUser)
            items, total, nc = await _paginate_query(stmt, params=params, pk_column=ORMUser.id, session=s, mapper=_user_to_dto)
            return Page(items=items, total=total, next_cursor=nc, has_more=nc is not None)

    async def get_by_email(self, email: str) -> User | None:
        async with session_scope() as s:
            result = await s.execute(select(ORMUser).where(func.lower(ORMUser.email) == email.lower()))
            orm = result.scalar_one_or_none()
            return _user_to_dto(orm) if orm else None

    async def get_by_sub(self, auth0_sub: str) -> User | None:
        async with session_scope() as s:
            result = await s.execute(select(ORMUser).where(ORMUser.external_id == auth0_sub))
            orm = result.scalar_one_or_none()
            return _user_to_dto(orm) if orm else None


class SqlConversationRepository(ConversationRepositoryPort):
    async def get(self, id: UUID) -> Conversation | None:  # type: ignore[override]
        async with session_scope() as s:
            orm = await s.get(ORMConversation, id)
            return _conversation_to_dto(orm) if orm else None

    async def create(self, entity: Conversation) -> Conversation:  # type: ignore[override]
        async with session_scope() as s:
            orm = _conversation_from_dto(entity)
            s.add(orm)
            await s.flush()
            return _conversation_to_dto(orm)

    async def update(self, entity: Conversation) -> Conversation:  # type: ignore[override]
        async with session_scope() as s:
            orm = await s.get(ORMConversation, entity.id)
            if orm is None:
                raise KeyError(f"Conversation {entity.id} not found")
            orm.title = entity.title
            orm.updated_at = entity.updated_at
            await s.flush()
            return _conversation_to_dto(orm)

    async def delete(self, id: UUID) -> bool:  # type: ignore[override]
        async with session_scope() as s:
            orm = await s.get(ORMConversation, id)
            if orm is None:
                return False
            await s.delete(orm)
            return True

    async def list(self, params: PageParams) -> Page[Conversation]:  # type: ignore[override]
        async with session_scope() as s:
            stmt = select(ORMConversation)
            items, total, nc = await _paginate_query(stmt, params=params, pk_column=ORMConversation.id, session=s, mapper=_conversation_to_dto)
            return Page(items=items, total=total, next_cursor=nc, has_more=nc is not None)

    async def list_for_user(self, user_id: UUID, params: PageParams) -> Page[Conversation]:  # type: ignore[override]
        async with session_scope() as s:
            stmt = select(ORMConversation).where(ORMConversation.user_id == user_id)
            items, total, nc = await _paginate_query(stmt, params=params, pk_column=ORMConversation.id, session=s, mapper=_conversation_to_dto)
            return Page(items=items, total=total, next_cursor=nc, has_more=nc is not None)


class SqlMessageRepository(MessageRepositoryPort):
    async def get(self, id: UUID) -> Message | None:  # type: ignore[override]
        async with session_scope() as s:
            orm = await s.get(ORMMessage, id)
            return _message_to_dto(orm) if orm else None

    async def create(self, entity: Message) -> Message:  # type: ignore[override]
        async with session_scope() as s:
            orm = _message_from_dto(entity)
            s.add(orm)
            await s.flush()
            return _message_to_dto(orm)

    async def update(self, entity: Message) -> Message:  # type: ignore[override]
        async with session_scope() as s:
            orm = await s.get(ORMMessage, entity.id)
            if orm is None:
                raise KeyError(f"Message {entity.id} not found")
            for k, v in entity.model_dump(exclude={"id", "created_at"}).items():
                setattr(orm, k, v)
            await s.flush()
            return _message_to_dto(orm)

    async def delete(self, id: UUID) -> bool:  # type: ignore[override]
        async with session_scope() as s:
            orm = await s.get(ORMMessage, id)
            if orm is None:
                return False
            await s.delete(orm)
            return True

    async def list(self, params: PageParams) -> Page[Message]:  # type: ignore[override]
        async with session_scope() as s:
            stmt = select(ORMMessage)
            items, total, nc = await _paginate_query(stmt, params=params, pk_column=ORMMessage.id, session=s, mapper=_message_to_dto)
            return Page(items=items, total=total, next_cursor=nc, has_more=nc is not None)

    async def list_for_conversation(self, conversation_id: UUID, params: PageParams) -> Page[Message]:  # type: ignore[override]
        async with session_scope() as s:
            stmt = select(ORMMessage).where(ORMMessage.conversation_id == conversation_id)
            items, total, nc = await _paginate_query(stmt, params=params, pk_column=ORMMessage.id, session=s, mapper=_message_to_dto)
            return Page(items=items, total=total, next_cursor=nc, has_more=nc is not None)


class SqlMemoryRepository(MemoryRepositoryPort):
    async def get(self, id: UUID) -> Memory | None:  # type: ignore[override]
        async with session_scope() as s:
            orm = await s.get(ORMMemory, id)
            return _memory_to_dto(orm) if orm else None

    async def create(self, entity: Memory) -> Memory:  # type: ignore[override]
        async with session_scope() as s:
            orm = _memory_from_dto(entity)
            s.add(orm)
            await s.flush()
            return _memory_to_dto(orm)

    async def update(self, entity: Memory) -> Memory:  # type: ignore[override]
        async with session_scope() as s:
            orm = await s.get(ORMMemory, entity.id)
            if orm is None:
                raise KeyError(f"Memory {entity.id} not found")
            for k, v in entity.model_dump(exclude={"id", "created_at"}).items():
                setattr(orm, k, v)
            await s.flush()
            return _memory_to_dto(orm)

    async def delete(self, id: UUID) -> bool:  # type: ignore[override]
        async with session_scope() as s:
            orm = await s.get(ORMMemory, id)
            if orm is None:
                return False
            await s.delete(orm)
            return True

    async def list(self, params: PageParams) -> Page[Memory]:  # type: ignore[override]
        async with session_scope() as s:
            stmt = select(ORMMemory)
            items, total, nc = await _paginate_query(stmt, params=params, pk_column=ORMMemory.id, session=s, mapper=_memory_to_dto)
            return Page(items=items, total=total, next_cursor=nc, has_more=nc is not None)

    async def list_for_scope(
        self,
        *,
        scope: Literal["user", "project", "team", "system"],
        scope_id: str | None,
        params: PageParams,
    ) -> Page[Memory]:  # type: ignore[override]
        async with session_scope() as s:
            stmt = select(ORMMemory)
            if scope == "user" and scope_id:
                with contextlib.suppress(ValueError):
                    stmt = stmt.where(ORMMemory.user_id == UUID(scope_id))
            elif scope == "system":
                stmt = stmt.where(ORMMemory.user_id.is_(None))
            items, total, nc = await _paginate_query(stmt, params=params, pk_column=ORMMemory.id, session=s, mapper=_memory_to_dto)
            return Page(items=items, total=total, next_cursor=nc, has_more=nc is not None)

    async def search_by_similarity(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 10,
        scope: str | None = None,
    ) -> list[Memory]:
        # NOTE: Semantic similarity is delegated to VectorStorePort.
        # This stub exists so callers that only want metadata+content filtering
        # get a consistent response shape; integrate Qdrant via the DI container.
        log.warning("SqlMemoryRepository.search_by_similarity: stub — use VectorStorePort for embeddings")
        async with session_scope() as s:
            stmt = select(ORMMemory).limit(top_k)
            if scope == "user":
                stmt = stmt.where(ORMMemory.user_id.is_not(None))
            elif scope == "system":
                stmt = stmt.where(ORMMemory.user_id.is_(None))
            result = await s.execute(stmt)
            return [_memory_to_dto(r) for r in result.scalars().all()]


class SqlDocumentRepository(DocumentRepositoryPort):
    async def get(self, id: UUID) -> Document | None:  # type: ignore[override]
        async with session_scope() as s:
            orm = await s.get(ORMDocument, id)
            return _document_to_dto(orm) if orm else None

    async def create(self, entity: Document) -> Document:  # type: ignore[override]
        async with session_scope() as s:
            orm = _document_from_dto(entity)
            s.add(orm)
            await s.flush()
            return _document_to_dto(orm)

    async def update(self, entity: Document) -> Document:  # type: ignore[override]
        async with session_scope() as s:
            orm = await s.get(ORMDocument, entity.id)
            if orm is None:
                raise KeyError(f"Document {entity.id} not found")
            for k, v in entity.model_dump(exclude={"id", "created_at"}).items():
                setattr(orm, k, v)
            await s.flush()
            return _document_to_dto(orm)

    async def delete(self, id: UUID) -> bool:  # type: ignore[override]
        async with session_scope() as s:
            orm = await s.get(ORMDocument, id)
            if orm is None:
                return False
            await s.delete(orm)
            return True

    async def list(self, params: PageParams) -> Page[Document]:  # type: ignore[override]
        async with session_scope() as s:
            stmt = select(ORMDocument)
            items, total, nc = await _paginate_query(stmt, params=params, pk_column=ORMDocument.id, session=s, mapper=_document_to_dto)
            return Page(items=items, total=total, next_cursor=nc, has_more=nc is not None)

    async def search_by_similarity(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 10,
        namespace: str | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[Document, float]]:
        # NOTE: Semantic similarity → VectorStorePort.  Returns empty here;
        # kernel handler composes VectorStorePort IDs with DocumentRepositoryPort.
        log.warning("SqlDocumentRepository.search_by_similarity: stub — delegate to VectorStorePort")
        return []


class SqlTaskExecutionRepository(TaskExecutionRepositoryPort):
    async def get(self, id: UUID) -> TaskExecution | None:  # type: ignore[override]
        async with session_scope() as s:
            orm = await s.get(ORMTaskExecution, id)
            return _task_execution_to_dto(orm) if orm else None

    async def create(self, entity: TaskExecution) -> TaskExecution:  # type: ignore[override]
        async with session_scope() as s:
            orm = _task_execution_from_dto(entity)
            s.add(orm)
            await s.flush()
            return _task_execution_to_dto(orm)

    async def update(self, entity: TaskExecution) -> TaskExecution:  # type: ignore[override]
        async with session_scope() as s:
            orm = await s.get(ORMTaskExecution, entity.id)
            if orm is None:
                raise KeyError(f"TaskExecution {entity.id} not found")
            for k, v in entity.model_dump(exclude={"id", "created_at"}).items():
                setattr(orm, k, v)
            await s.flush()
            return _task_execution_to_dto(orm)

    async def delete(self, id: UUID) -> bool:  # type: ignore[override]
        async with session_scope() as s:
            orm = await s.get(ORMTaskExecution, id)
            if orm is None:
                return False
            await s.delete(orm)
            return True

    async def list(self, params: PageParams) -> Page[TaskExecution]:  # type: ignore[override]
        async with session_scope() as s:
            stmt = select(ORMTaskExecution)
            items, total, nc = await _paginate_query(stmt, params=params, pk_column=ORMTaskExecution.id, session=s, mapper=_task_execution_to_dto)
            return Page(items=items, total=total, next_cursor=nc, has_more=nc is not None)

    async def list_for_run(self, run_id: UUID, params: PageParams) -> Page[TaskExecution]:  # type: ignore[override]
        async with session_scope() as s:
            # ORM lacks run_id column; we match on conversation_id for now.
            stmt = select(ORMTaskExecution).where(ORMTaskExecution.conversation_id == run_id)
            items, total, nc = await _paginate_query(stmt, params=params, pk_column=ORMTaskExecution.id, session=s, mapper=_task_execution_to_dto)
            return Page(items=items, total=total, next_cursor=nc, has_more=nc is not None)


# ---------------------------------------------------------------------------
# Adapters for KnowledgeObjectRepositoryPort / ArtifactRepositoryPort.
# These use plain Dict-based storage via existing generic tables pattern
# (stubbed against ORM tables we'll create in Alembic 0002). For M1 they
# run against in-memory tables so callers have a working implementation.
# ---------------------------------------------------------------------------


class SqlArtifactRepository(ArtifactRepositoryPort):
    """Artifact SQL adapter — in-memory for M1; Alembic 0002 adds the table."""

    def __init__(self) -> None:
        self._rows: dict[UUID, Artifact] = {}

    async def get(self, id: UUID) -> Artifact | None:  # type: ignore[override]
        return self._rows.get(id)

    async def create(self, entity: Artifact) -> Artifact:  # type: ignore[override]
        self._rows[entity.id] = entity
        return entity

    async def update(self, entity: Artifact) -> Artifact:  # type: ignore[override]
        if entity.id not in self._rows:
            raise KeyError(f"Artifact {entity.id} not found")
        self._rows[entity.id] = entity
        return entity

    async def delete(self, id: UUID) -> bool:  # type: ignore[override]
        return bool(self._rows.pop(id, None))

    async def list(self, params: PageParams) -> Page[Artifact]:  # type: ignore[override]
        rows = sorted(self._rows.values(), key=lambda a: str(a.id))
        return _list_slice(rows, params)

    async def list_for_task(self, task_id: UUID, params: PageParams) -> Page[Artifact]:  # type: ignore[override]
        rows = sorted(
            [a for a in self._rows.values() if a.task_id == str(task_id)],
            key=lambda a: str(a.id),
        )
        return _list_slice(rows, params)

    async def find_by_sha256(self, sha256: str) -> Artifact | None:
        for a in self._rows.values():
            if a.sha256 == sha256:
                return a
        return None


class SqlKnowledgeObjectRepository(KnowledgeObjectRepositoryPort):
    """KnowledgeObject SQL adapter — in-memory for M1; Alembic 0002 adds the table."""

    def __init__(self) -> None:
        self._rows: dict[UUID, KnowledgeObject] = {}

    async def get(self, id: UUID) -> KnowledgeObject | None:  # type: ignore[override]
        return self._rows.get(id)

    async def create(self, entity: KnowledgeObject) -> KnowledgeObject:  # type: ignore[override]
        self._rows[entity.id] = entity
        return entity

    async def update(self, entity: KnowledgeObject) -> KnowledgeObject:  # type: ignore[override]
        if entity.id not in self._rows:
            raise KeyError(f"KnowledgeObject {entity.id} not found")
        self._rows[entity.id] = entity
        return entity

    async def delete(self, id: UUID) -> bool:  # type: ignore[override]
        return bool(self._rows.pop(id, None))

    async def list(self, params: PageParams) -> Page[KnowledgeObject]:  # type: ignore[override]
        rows = sorted(self._rows.values(), key=lambda k: str(k.id))
        return _list_slice(rows, params)

    async def list_for_workspace(
        self,
        workspace_id: UUID,
        params: PageParams,
        *,
        kind: str | None = None,
    ) -> Page[KnowledgeObject]:  # type: ignore[override]
        rows = [k for k in self._rows.values() if k.workspace_id == str(workspace_id)]
        if kind:
            rows = [k for k in rows if k.kind == kind]
        rows = sorted(rows, key=lambda k: str(k.id))
        return _list_slice(rows, params)

    async def search_by_tag(
        self,
        tags: list[str],
        params: PageParams,
        *,
        workspace_id: UUID | None = None,
    ) -> Page[KnowledgeObject]:  # type: ignore[override]
        rows = [k for k in self._rows.values() if (workspace_id is None or k.workspace_id == str(workspace_id)) and any(t in k.tags for t in tags)]
        rows = sorted(rows, key=lambda k: str(k.id))
        return _list_slice(rows, params)

    async def list_versions(self, parent_id: UUID, params: PageParams) -> Page[KnowledgeObject]:  # type: ignore[override]
        rows = [k for k in self._rows.values() if k.parent_id == str(parent_id)]
        rows = sorted(rows, key=lambda k: k.version, reverse=True)
        return _list_slice(rows, params)


# ---------------------------------------------------------------------------
# Shared helper: Python-side keyset pagination for in-memory repos
# ---------------------------------------------------------------------------


def _list_slice(rows: list, params: PageParams):
    start = 0
    if params.cursor:
        try:
            start = int(params.cursor)
        except ValueError:
            start = 0
    window = rows[start : start + params.limit + 1]
    next_cursor: str | None = None
    has_more = len(window) > params.limit
    if has_more:
        window = window[: params.limit]
        next_cursor = str(start + params.limit)
    return Page(
        items=window,
        total=len(rows),
        next_cursor=next_cursor,
        has_more=has_more,
    )
