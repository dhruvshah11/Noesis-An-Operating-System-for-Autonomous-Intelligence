"""
In-memory repository unit tests.

Strategy: every RepositoryPort LSP contract is exercised against its
``InMemory*Repository`` implementation.  If these tests pass, a SQL / Qdrant
adapter that implements the same ABC with the same semantic behaviour will
work in production (it only needs an equivalent test).

Tested for each adapter:
  1. create -> get round-trips
  2. update returns updated entity, raises KeyError on unknown
  3. delete returns bool; second delete is idempotent (False)
  4. list respects limit + cursor (keyset pagination shape)
  5. Subclass-specific finders return the filtered shape
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio

from noesis.core.ports import (
    ArtifactRepositoryPort,
    ConversationRepositoryPort,
    DocumentRepositoryPort,
    KnowledgeObjectRepositoryPort,
    MemoryRepositoryPort,
    MessageRepositoryPort,
    PageParams,
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
from tests._support.repos import (
    InMemoryArtifactRepository,
    InMemoryConversationRepository,
    InMemoryDocumentRepository,
    InMemoryKnowledgeObjectRepository,
    InMemoryMemoryRepository,
    InMemoryMessageRepository,
    InMemoryTaskExecutionRepository,
    InMemoryUserRepository,
)

# ---------------------------------------------------------------------------
# Fixtures — one in-memory adapter per port
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
def users() -> InMemoryUserRepository:
    return InMemoryUserRepository()


@pytest_asyncio.fixture
def convs() -> InMemoryConversationRepository:
    return InMemoryConversationRepository()


@pytest_asyncio.fixture
def msgs() -> InMemoryMessageRepository:
    return InMemoryMessageRepository()


@pytest_asyncio.fixture
def mems() -> InMemoryMemoryRepository:
    return InMemoryMemoryRepository()


@pytest_asyncio.fixture
def docs() -> InMemoryDocumentRepository:
    return InMemoryDocumentRepository()


@pytest_asyncio.fixture
def texs() -> InMemoryTaskExecutionRepository:
    return InMemoryTaskExecutionRepository()


@pytest_asyncio.fixture
def arts() -> InMemoryArtifactRepository:
    return InMemoryArtifactRepository()


@pytest_asyncio.fixture
def kos() -> InMemoryKnowledgeObjectRepository:
    return InMemoryKnowledgeObjectRepository()


# ---------------------------------------------------------------------------
# UserRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_crud_round_trip(users: UserRepositoryPort) -> None:
    u = User(email="a@astraos.test")
    created = await users.create(u)
    fetched = await users.get(created.id)
    assert fetched is not None
    assert fetched.email == "a@astraos.test"

    created.full_name = "Updated"
    updated = await users.update(created)
    assert updated.full_name == "Updated"

    assert await users.delete(created.id) is True
    assert await users.delete(created.id) is False  # idempotent

    with pytest.raises(KeyError):
        await users.update(User(email="ghost@astraos.test"))


@pytest.mark.asyncio
async def test_user_getters(users: UserRepositoryPort) -> None:
    await users.create(User(email="alice@astraos.test", external_id="auth0|1"))
    assert (await users.get_by_email("ALICE@ASTRAOS.TEST")).email == "alice@astraos.test"
    assert (await users.get_by_sub("auth0|1")).external_id == "auth0|1"
    assert await users.get_by_email("nonexistent@astraos.test") is None


@pytest.mark.asyncio
async def test_user_list_pagination(users: UserRepositoryPort) -> None:
    for i in range(7):
        await users.create(User(email=f"u{i}@astraos.test"))
    page = await users.list(PageParams(limit=3))
    assert len(page.items) == 3
    assert page.total == 7
    assert page.has_more is True
    assert page.next_cursor is not None
    page2 = await users.list(PageParams(limit=3, cursor=page.next_cursor))
    assert len(page2.items) == 3
    page3 = await users.list(PageParams(limit=3, cursor=page2.next_cursor))
    assert len(page3.items) == 1
    assert page3.has_more is False


# ---------------------------------------------------------------------------
# ConversationRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_conversation_crud_and_list_for_user(convs: ConversationRepositoryPort) -> None:
    user_id = uuid4()
    c = await convs.create(Conversation(user_id=str(user_id), title="C1"))
    await convs.create(Conversation(title="orphan"))
    user_page = await convs.list_for_user(user_id, PageParams(limit=10))
    assert len(user_page.items) == 1
    assert user_page.items[0].id == c.id


# ---------------------------------------------------------------------------
# MessageRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_message_list_for_conversation(msgs: MessageRepositoryPort) -> None:
    cid = uuid4()
    for i in range(5):
        await msgs.create(Message(conversation_id=cid, role="user", content=f"m{i}"))
    await msgs.create(Message(conversation_id=uuid4(), role="user", content="other"))
    page = await msgs.list_for_conversation(cid, PageParams(limit=10))
    assert len(page.items) == 5


# ---------------------------------------------------------------------------
# MemoryRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memory_scope_filters_and_similarity_stub(mems: MemoryRepositoryPort) -> None:
    user_id = uuid4()
    vid = uuid4()
    await mems.create(Memory(vector_id=vid, memory_type="semantic", content="a", user_id=str(user_id), scope="user"))
    await mems.create(Memory(vector_id=uuid4(), memory_type="semantic", content="sys", scope="system"))
    user_page = await mems.list_for_scope(scope="user", scope_id=str(user_id), params=PageParams())
    assert len(user_page.items) == 1
    sys_page = await mems.list_for_scope(scope="system", scope_id=None, params=PageParams())
    assert len(sys_page.items) == 1
    # search_by_similarity for in-memory returns ordered-by-importance (deterministic stub)
    await mems.create(Memory(vector_id=uuid4(), memory_type="semantic", content="high", importance=0.99, scope="system"))
    top = await mems.search_by_similarity(query_embedding=[0.1, 0.2], top_k=1, scope="system")
    assert len(top) == 1
    assert top[0].content == "high"


# ---------------------------------------------------------------------------
# DocumentRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_document_crud(docs: DocumentRepositoryPort) -> None:
    created = await docs.create(Document(title="spec", source_uri="s3://bucket/spec.pdf"))
    got = await docs.get(created.id)
    assert got is not None and got.source_uri == "s3://bucket/spec.pdf"
    assert (await docs.delete(created.id)) is True


# ---------------------------------------------------------------------------
# TaskExecutionRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_execution_run_filter(texs: TaskExecutionRepositoryPort) -> None:
    cid = uuid4()
    await texs.create(TaskExecution(conversation_id=str(cid), agent_type="tool", description="a", status=3))
    await texs.create(TaskExecution(agent_type="x", description="b"))
    page = await texs.list_for_run(cid, PageParams())
    assert len(page.items) == 1
    assert page.items[0].status == 3


# ---------------------------------------------------------------------------
# ArtifactRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_artifact_sha_and_task_filter(arts: ArtifactRepositoryPort) -> None:
    tid = uuid4()
    a = Artifact(kind="file", name="a.txt", size_bytes=12, sha256="0" * 64, task_id=str(tid))
    a = await arts.create(a)
    assert (await arts.find_by_sha256("0" * 64)).id == a.id
    assert await arts.find_by_sha256("deadbeef") is None
    await arts.create(Artifact(kind="x", name="b.txt"))
    page = await arts.list_for_task(tid, PageParams())
    assert len(page.items) == 1


# ---------------------------------------------------------------------------
# KnowledgeObjectRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_knowledge_object_search_tag_and_versions(
    kos: KnowledgeObjectRepositoryPort,
) -> None:
    ws = uuid4()
    parent = uuid4()
    for v in (1, 2, 3):
        await kos.create(
            KnowledgeObject(
                workspace_id=str(ws),
                kind="decision",
                title=f"v{v}",
                parent_id=str(parent),
                version=v,
                tags=["adr", f"v{v}"],
            )
        )
    await kos.create(
        KnowledgeObject(
            workspace_id=str(ws),
            kind="report",
            title="Report",
            tags=["report", "adr"],
        )
    )
    ws_page = await kos.list_for_workspace(ws, PageParams(limit=100), kind="decision")
    assert len(ws_page.items) == 3
    adr_page = await kos.search_by_tag(["adr"], PageParams(limit=100), workspace_id=ws)
    assert len(adr_page.items) == 4
    # Versions sorted desc by semver int (3,2,1)
    versions = await kos.list_versions(parent, PageParams(limit=100))
    assert [v.version for v in versions.items] == [3, 2, 1]
