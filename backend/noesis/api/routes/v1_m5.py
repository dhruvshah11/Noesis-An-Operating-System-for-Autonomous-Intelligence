"""
Milestone-5 v1 routes — dashboard front-end parity.

Route summary (all under ``/v1`` prefix):

Conversations (matches frontend page ``app/conversations/page.tsx``)
  * GET    /v1/conversations             paginated list with status/agent/tags filters
  * POST   /v1/conversations             create a new thread
  * GET    /v1/conversations/{id}        fetch one (include first ~20 messages)
  * PATCH  /v1/conversations/{id}        update title / status / metadata
  * DELETE /v1/conversations/{id}        soft delete (mark status=completed archived tag)
  * GET    /v1/conversations/{id}/messages  page messages
  * POST   /v1/conversations/{id}/messages  append a user OR assistant message

Agents (matches frontend page ``app/agents/page.tsx``)
  * GET    /v1/agents                     list of available agents (capabilities + manifest)
  * POST   /v1/agents/invoke              run single named agent on a state dict

Runs (Planner + AgentRuntime orchestration — Execution Timeline)
  * POST   /v1/runs/plan                  PlannerSvc.plan → ExecutionPlan + PlannerReport
  * POST   /v1/runs/execute               AgentSvc.run_plan(plan) → (run_id, step results)
  * GET    /v1/runs/{run_id}/executions   paginated TaskExecution list

Documents (matches ``app/documents/page.tsx``)
  * GET    /v1/documents                  list (status, kind filters)
  * POST   /v1/documents                  create document metadata
  * GET    /v1/documents/{id}             read metadata
  * DELETE /v1/documents/{id}             delete
  * POST   /v1/documents/upload           upload file multipart → ingest status

Memory (matches ``app/memory`` + ``app/memory/explorer``)
  * GET    /v1/memory                     list paginated, tier filter = memory_type
  * POST   /v1/memory/query               content + semantic filter + tier filter
  * POST   /v1/memory/compress            compress memory records older than N days

UAP wire (M5.2 — protocol tests call /uap/transports/inproc and /uap/envelope/send)
  * GET    /v1/uap/transports             list available transports
  * POST   /v1/uap/transports/inproc      create a new in-process pipe transport
  * POST   /v1/uap/envelope/send          accept UAPEnvelope JSON, validate, route in-process
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field

from noesis.api.deps import RequestID, ok_envelope
from noesis.core import ports
from noesis.services import build_services_from_container
from noesis.types import (
    AgentType,
    APIEnvelope,
    Conversation,
    ConversationStatus,
    Document,
    ExecutionPlan,
    Memory,
    Message,
    MessageRole,
    Page,
    PageParams,
    TaskStatus,
)

router = APIRouter(tags=["v1.m5"])


# ---------------------------------------------------------------------------
# DI helpers — the container is global per process; we re-use one Container
# instance instead of rebuilding per request.
# ---------------------------------------------------------------------------


async def _get_container(request: Request):
    from noesis.core.di import build_default_container

    c = getattr(request.app.state, "di_container", None)
    if c is None:
        c = build_default_container()
        request.app.state.di_container = c
    return c


async def _get_repo(request: Request, abstract):
    container = await _get_container(request)
    return await container.get(abstract)


async def get_conv_repo(request: Request) -> ports.ConversationRepositoryPort:
    return await _get_repo(request, ports.ConversationRepositoryPort)


async def get_msg_repo(request: Request) -> ports.MessageRepositoryPort:
    return await _get_repo(request, ports.MessageRepositoryPort)


async def get_mem_repo(request: Request) -> ports.MemoryRepositoryPort:
    return await _get_repo(request, ports.MemoryRepositoryPort)


async def get_doc_repo(request: Request) -> ports.DocumentRepositoryPort:
    return await _get_repo(request, ports.DocumentRepositoryPort)


async def get_te_repo(request: Request) -> ports.TaskExecutionRepositoryPort:
    return await _get_repo(request, ports.TaskExecutionRepositoryPort)


async def get_services(request: Request):
    container = await _get_container(request)
    return await build_services_from_container(container)


# ---------------------------------------------------------------------------
# Response helpers for Conversations (adds status, agent, preview, tags,
# counts) without modifying the Conversation persistence DTO shape.
# ---------------------------------------------------------------------------


class ConversationEnriched(BaseModel):
    model_config = ConfigDict(use_enum_values=True, from_attributes=True)

    id: UUID
    title: str
    status: ConversationStatus = ConversationStatus.ACTIVE
    agent: str = "orchestrator"
    preview: str = ""
    tags: list[str] = Field(default_factory=list)
    updated_at: datetime
    created_at: datetime
    message_count: int = 0
    token_count: int = 0
    cost_usd: float = 0.0
    user_id: str | None = None


def _page_cursor_params(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=200),
) -> PageParams:
    return PageParams(cursor=cursor or "", limit=limit)


def _enrich_conversation(conv: Conversation, messages: list[Message] | None = None) -> ConversationEnriched:
    status = ConversationStatus(str(conv.metadata.get("status") or ConversationStatus.ACTIVE.value))
    agent = str(conv.metadata.get("agent") or "orchestrator")
    tags: list[str] = list(conv.metadata.get("tags") or [])
    last_content = ""
    msg_cnt = len(messages) if messages is not None else int(conv.metadata.get("message_count", 0))
    tok_cnt = int(conv.metadata.get("token_count", 0))
    cost = float(conv.metadata.get("cost_usd", 0.0))
    if messages:
        user_or_assistant = [m for m in messages if m.role in {MessageRole.USER.value, MessageRole.ASSISTANT.value}]
        if user_or_assistant:
            last_content = (user_or_assistant[-1].content or "")[:160]
        tok_cnt = sum((m.prompt_tokens or 0) + (m.completion_tokens or 0) for m in messages) or tok_cnt
    return ConversationEnriched(
        id=conv.id,
        title=conv.title,
        status=status,
        agent=agent,
        preview=last_content or (conv.metadata.get("preview") or ""),
        tags=tags,
        updated_at=conv.updated_at,
        created_at=conv.created_at,
        message_count=msg_cnt,
        token_count=tok_cnt,
        cost_usd=cost,
        user_id=conv.user_id,
    )


# ===========================================================================
# 1. Conversations
# ===========================================================================


@router.get("/conversations", response_model=APIEnvelope)
async def list_conversations(
    request: Request,
    req_id: RequestID,
    params: PageParams = Depends(_page_cursor_params),
    status: str | None = Query(default=None),
    agent: str | None = Query(default=None),
    search: str | None = Query(default=None),
):
    repo: ports.ConversationRepositoryPort = await get_conv_repo(request)
    msg_repo: ports.MessageRepositoryPort = await get_msg_repo(request)
    page: Page[Conversation] = await repo.list(params)
    items: list[ConversationEnriched] = []
    for conv in page.items:
        msgs_page: Page[Message] = await msg_repo.list_for_conversation(conv.id, PageParams(cursor="", limit=20))
        enriched = _enrich_conversation(conv, msgs_page.items)
        if status and enriched.status.value != status:
            continue
        if agent and enriched.agent != agent:
            continue
        if search:
            q = search.lower()
            blob = f"{enriched.title.lower()} {enriched.preview.lower()} {' '.join(t.lower() for t in enriched.tags)}"
            if q not in blob:
                continue
        items.append(enriched)
    meta = {"limit": params.limit, "next_cursor": page.next_cursor, "total": page.total}
    return ok_envelope(
        [e.model_dump(mode="json") for e in items],
        request_id=req_id,
        meta=meta,
    )


class ConversationCreateReq(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    agent: str = "orchestrator"
    tags: list[str] = Field(default_factory=list)
    user_id: str | None = None


@router.post("/conversations", response_model=APIEnvelope)
async def create_conversation(
    request: Request,
    req_id: RequestID,
    body: ConversationCreateReq,
):
    repo: ports.ConversationRepositoryPort = await get_conv_repo(request)
    now = datetime.now(UTC)
    conv = Conversation(
        id=uuid4(),
        user_id=body.user_id,
        title=body.title,
        messages=[],
        created_at=now,
        updated_at=now,
        metadata={
            "status": ConversationStatus.ACTIVE.value,
            "agent": body.agent,
            "tags": list(body.tags),
            "message_count": 0,
            "token_count": 0,
            "cost_usd": 0.0,
        },
    )
    created = await repo.create(conv)
    return ok_envelope(
        _enrich_conversation(created).model_dump(mode="json"),
        request_id=req_id,
    )


@router.get("/conversations/{conversation_id}", response_model=APIEnvelope)
async def get_conversation(
    request: Request,
    req_id: RequestID,
    conversation_id: UUID,
    include_messages: bool = Query(default=True),
    limit_messages: int = Query(default=50, ge=1, le=500),
):
    repo: ports.ConversationRepositoryPort = await get_conv_repo(request)
    conv = await repo.get(conversation_id)
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Conversation {conversation_id} not found")
    msg_repo: ports.MessageRepositoryPort = await get_msg_repo(request)
    msgs = None
    if include_messages:
        page = await msg_repo.list_for_conversation(conversation_id, PageParams(cursor="", limit=limit_messages))
        msgs = page.items
    data = _enrich_conversation(conv, msgs).model_dump(mode="json")
    if msgs is not None:
        data["messages"] = [m.model_dump(mode="json") for m in msgs]
    return ok_envelope(data, request_id=req_id)


class ConversationPatchReq(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    status: ConversationStatus | None = None
    tags: list[str] | None = None


@router.patch("/conversations/{conversation_id}", response_model=APIEnvelope)
async def patch_conversation(
    request: Request,
    req_id: RequestID,
    conversation_id: UUID,
    body: ConversationPatchReq,
):
    repo: ports.ConversationRepositoryPort = await get_conv_repo(request)
    conv = await repo.get(conversation_id)
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Conversation {conversation_id} not found")
    if body.title is not None:
        conv.title = body.title
    if body.status is not None:
        conv.metadata["status"] = body.status.value
    if body.tags is not None:
        conv.metadata["tags"] = list(body.tags)
    conv.updated_at = datetime.now(UTC)
    updated = await repo.update(conv)
    msg_repo: ports.MessageRepositoryPort = await get_msg_repo(request)
    msgs = await msg_repo.list_for_conversation(updated.id, PageParams(cursor="", limit=20))
    return ok_envelope(
        _enrich_conversation(updated, msgs.items).model_dump(mode="json"),
        request_id=req_id,
    )


@router.delete("/conversations/{conversation_id}", response_model=APIEnvelope)
async def delete_conversation(
    request: Request,
    req_id: RequestID,
    conversation_id: UUID,
):
    repo: ports.ConversationRepositoryPort = await get_conv_repo(request)
    ok = await repo.delete(conversation_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Conversation {conversation_id} not found")
    return ok_envelope({"deleted": True}, request_id=req_id)


@router.get("/conversations/{conversation_id}/messages", response_model=APIEnvelope)
async def list_messages(
    request: Request,
    req_id: RequestID,
    conversation_id: UUID,
    params: PageParams = Depends(_page_cursor_params),
):
    repo: ports.MessageRepositoryPort = await get_msg_repo(request)
    page = await repo.list_for_conversation(conversation_id, params)
    data = [m.model_dump(mode="json") for m in page.items]
    meta = {"limit": params.limit, "next_cursor": page.next_cursor, "total": page.total}
    return ok_envelope(data, request_id=req_id, meta=meta)


class MessageCreateReq(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant", "tool", "observation", "reflection"]
    content: str = Field(min_length=1)
    name: str | None = None
    tool_call_id: str | None = None


@router.post("/conversations/{conversation_id}/messages", response_model=APIEnvelope)
async def append_message(
    request: Request,
    req_id: RequestID,
    conversation_id: UUID,
    body: MessageCreateReq,
):
    conv_repo: ports.ConversationRepositoryPort = await get_conv_repo(request)
    conv = await conv_repo.get(conversation_id)
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Conversation {conversation_id} not found")
    msg_repo: ports.MessageRepositoryPort = await get_msg_repo(request)
    msg = Message(
        id=uuid4(),
        conversation_id=conversation_id,
        role=body.role,
        content=body.content,
        name=body.name,
        tool_call_id=body.tool_call_id,
        tool_calls=[],
        created_at=datetime.now(UTC),
    )
    saved = await msg_repo.create(msg)
    # Bump counters + status=active, preview = last content on Conversation.metadata
    prev_count = int(conv.metadata.get("message_count", 0))
    prev_tokens = int(conv.metadata.get("token_count", 0))
    conv.metadata["message_count"] = prev_count + 1
    conv.metadata["token_count"] = prev_tokens
    conv.metadata["preview"] = body.content[:160]
    conv.metadata["status"] = ConversationStatus.ACTIVE.value
    conv.updated_at = saved.created_at
    await conv_repo.update(conv)
    return ok_envelope(saved.model_dump(mode="json"), request_id=req_id)


# ===========================================================================
# 2. Agents
# ===========================================================================


class AgentManifest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    name: str
    agent_type: str
    description: str
    required_capabilities: list[str] = Field(default_factory=list)
    report_type: str | None = None


_BUILTIN_AGENTS: list[AgentManifest] = [
    AgentManifest(
        name="planner",
        agent_type=AgentType.PLANNER.value,
        description="Decompose a goal into a dependency-ordered ExecutionPlan (seeded deterministic).",
        required_capabilities=["rag_search:*"],
        report_type="PlannerReport",
    ),
    AgentManifest(
        name="research",
        agent_type=AgentType.RESEARCH.value,
        description="Seed-URL-driven cross-source research report.",
        required_capabilities=["tool_invoke:web_fetch"],
        report_type="ResearchReport",
    ),
    AgentManifest(
        name="coding",
        agent_type=AgentType.CODING.value,
        description="Instruction→patch-list alpha CodingAgent with dry-run diff.",
        required_capabilities=["tool_invoke:files", "tool_invoke:shell"],
        report_type="CodingPatchReport",
    ),
    AgentManifest(
        name="reflection",
        agent_type=AgentType.REFLECTION.value,
        description="Mistake-detector + confidence scorer + replan recommender.",
        required_capabilities=["memory_read:*"],
        report_type="ReflectionReport",
    ),
    AgentManifest(
        name="memory",
        agent_type=AgentType.MEMORY.value,
        description="Placeholder — 6-tier memory curator (M2).",
        required_capabilities=["memory_write:*"],
        report_type=None,
    ),
    AgentManifest(
        name="rag",
        agent_type=AgentType.RAG.value,
        description="Placeholder — document/RAG ingestion agent (M2).",
        required_capabilities=["rag_ingest:*"],
        report_type=None,
    ),
    AgentManifest(
        name="tool",
        agent_type=AgentType.TOOL.value,
        description="Placeholder — safe tool-invocation agent (M3).",
        required_capabilities=["tool_invoke:*"],
        report_type=None,
    ),
]


@router.get("/agents", response_model=APIEnvelope)
async def list_agents(req_id: RequestID):
    data = [a.model_dump(mode="json") for a in _BUILTIN_AGENTS]
    return ok_envelope(data, request_id=req_id)


class AgentInvokeReq(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: str = Field(min_length=1)
    state: dict[str, Any] = Field(default_factory=dict)


@router.post("/agents/invoke", response_model=APIEnvelope)
async def invoke_agent(
    request: Request,
    req_id: RequestID,
    body: AgentInvokeReq,
):
    from noesis.agents.core import (
        AgentRunContext,
        CodingAgent,
        PlannerAgent,
        ReflectionAgent,
        ResearchAgent,
    )
    from noesis.services import _default_tool_registry
    from noesis.services.kernel_services import ALL_CAPABILITIES, mint_token

    agents = {
        "planner": (PlannerAgent, PlannerAgent().required_capabilities),
        "research": (ResearchAgent, ResearchAgent().required_capabilities),
        "coding": (CodingAgent, CodingAgent().required_capabilities),
        "reflection": (ReflectionAgent, ReflectionAgent().required_capabilities),
    }
    entry = agents.get(body.agent)
    if entry is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown agent '{body.agent}'")
    cls, caps = entry
    instance = cls()
    tools = _default_tool_registry()
    token = mint_token(subject=f"api:{body.agent}", capabilities=tuple(caps), ttl_s=600)
    ctx = AgentRunContext(
        token=token,
        capabilities=tuple(caps) or ALL_CAPABILITIES,
        tools=tools,
        request_id=req_id,
    )
    loop = asyncio.get_event_loop()
    out = await loop.run_in_executor(None, instance.run, dict(body.state), ctx)
    return ok_envelope(out, request_id=req_id)


# ===========================================================================
# 3. Runs (Plan + Execute)
# ===========================================================================


class PlanReq(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=5)
    seed: int | None = None
    conversation_id: UUID | None = None


@router.post("/runs/plan", response_model=APIEnvelope)
async def plan_goal(request: Request, req_id: RequestID, body: PlanReq):
    _planner_svc, _agent_svc = await get_services(request)
    report = _planner_svc.plan(body.goal, seed=body.seed, conversation_id=body.conversation_id)
    data = report.model_dump(mode="json")
    return ok_envelope(data, request_id=req_id)


class ExecuteReq(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: dict[str, Any]  # ExecutionPlan JSON shape
    conversation_id: UUID | None = None
    user_id: str | None = None


@router.post("/runs/execute", response_model=APIEnvelope)
async def execute_plan(request: Request, req_id: RequestID, body: ExecuteReq):
    _planner_svc, agent_svc = await get_services(request)
    plan = ExecutionPlan.model_validate(body.plan)
    run_id, results = await agent_svc.run_plan_async(plan, conversation_id=body.conversation_id, user_id=body.user_id)
    data = {
        "run_id": str(run_id),
        "steps": [
            {
                "step_id": str(r.step_id),
                "agent_type": r.agent_type,
                "status": TaskStatus(r.status).name,
                "status_code": r.status.value,
                "duration_ms": r.duration_ms,
                "tokens_in": r.tokens_in,
                "tokens_out": r.tokens_out,
                "cost_usd": r.cost_usd,
                "result_preview": r.result_preview,
                "report_type": r.report_type,
                "report": r.report,
                "error": r.error,
            }
            for r in results
        ],
    }
    return ok_envelope(data, request_id=req_id)


@router.get("/runs/{run_id}/executions", response_model=APIEnvelope)
async def list_executions(
    request: Request,
    req_id: RequestID,
    run_id: UUID,
    params: PageParams = Depends(_page_cursor_params),
):
    repo: ports.TaskExecutionRepositoryPort = await get_te_repo(request)
    try:
        page = await repo.list_for_run(run_id, params)
    except Exception:
        page = Page(items=[], total=0, next_cursor=None, has_more=False)
    data = [te.model_dump(mode="json") for te in page.items]
    return ok_envelope(
        data,
        request_id=req_id,
        meta={"limit": params.limit, "next_cursor": page.next_cursor, "total": page.total},
    )


# ===========================================================================
# 4. Documents
# ===========================================================================


@router.get("/documents", response_model=APIEnvelope)
async def list_documents(
    request: Request,
    req_id: RequestID,
    params: PageParams = Depends(_page_cursor_params),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
):
    repo: ports.DocumentRepositoryPort = await get_doc_repo(request)
    page = await repo.list(params)
    docs: list[Document] = page.items
    if status:
        docs = [d for d in docs if d.ingestion_status == status]
    if search:
        q = search.lower()
        docs = [d for d in docs if q in d.title.lower() or q in d.source_uri.lower()]
    data = [d.model_dump(mode="json") for d in docs]
    return ok_envelope(
        data,
        request_id=req_id,
        meta={"limit": params.limit, "next_cursor": page.next_cursor, "total": page.total},
    )


class DocumentCreateReq(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    source_uri: str = Field(min_length=1)
    mime_type: str = "application/octet-stream"
    user_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/documents", response_model=APIEnvelope)
async def create_document(request: Request, req_id: RequestID, body: DocumentCreateReq):
    repo: ports.DocumentRepositoryPort = await get_doc_repo(request)
    doc = Document(
        id=uuid4(),
        user_id=body.user_id,
        title=body.title,
        source_uri=body.source_uri,
        mime_type=body.mime_type,
        byte_size=0,
        chunk_count=0,
        ingestion_status="pending",
        metadata=body.metadata,
        created_at=datetime.now(UTC),
    )
    saved = await repo.create(doc)
    return ok_envelope(saved.model_dump(mode="json"), request_id=req_id)


@router.get("/documents/{document_id}", response_model=APIEnvelope)
async def get_document(request: Request, req_id: RequestID, document_id: UUID):
    repo: ports.DocumentRepositoryPort = await get_doc_repo(request)
    doc = await repo.get(document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Document {document_id} not found")
    return ok_envelope(doc.model_dump(mode="json"), request_id=req_id)


@router.delete("/documents/{document_id}", response_model=APIEnvelope)
async def delete_document(request: Request, req_id: RequestID, document_id: UUID):
    repo: ports.DocumentRepositoryPort = await get_doc_repo(request)
    ok = await repo.delete(document_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Document {document_id} not found")
    return ok_envelope({"deleted": True}, request_id=req_id)


@router.post("/documents/upload", response_model=APIEnvelope)
async def upload_document(
    request: Request,
    req_id: RequestID,
    file: UploadFile = File(...),
    user_id: str | None = Form(default=None),
    title: str | None = Form(default=None),
    source_uri: str | None = Form(default=None),
):
    repo: ports.DocumentRepositoryPort = await get_doc_repo(request)
    raw = await file.read()
    doc = Document(
        id=uuid4(),
        user_id=user_id,
        title=title or file.filename or "Untitled upload",
        source_uri=source_uri or f"upload://{req_id}/{file.filename or 'file'}",
        mime_type=file.content_type or "application/octet-stream",
        byte_size=len(raw),
        chunk_count=0,
        ingestion_status="processing",
        metadata={"filename": file.filename, "uploaded_at": datetime.now(UTC).isoformat()},
        created_at=datetime.now(UTC),
    )
    saved = await repo.create(doc)
    # Simulate ingest completion (deterministic: after 1 step we're "ready").
    saved.ingestion_status = "ready"
    saved.chunk_count = max(1, len(raw) // 2048)
    await repo.update(saved)
    return ok_envelope(saved.model_dump(mode="json"), request_id=req_id)


# ===========================================================================
# 5. Memory
# ===========================================================================


@router.get("/memory", response_model=APIEnvelope)
async def list_memory(
    request: Request,
    req_id: RequestID,
    params: PageParams = Depends(_page_cursor_params),
    memory_type: str | None = Query(default=None),
    min_importance: float = Query(default=0.0, ge=0.0, le=1.0),
):
    repo: ports.MemoryRepositoryPort = await get_mem_repo(request)
    page = await repo.list(params)
    rows = [m for m in page.items if m.importance >= min_importance]
    if memory_type:
        rows = [m for m in rows if m.memory_type == memory_type]
    data = [m.model_dump(mode="json") for m in rows]
    return ok_envelope(
        data,
        request_id=req_id,
        meta={"limit": params.limit, "next_cursor": page.next_cursor, "total": page.total},
    )


class MemoryQueryReq(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1)
    tiers: list[str] = Field(default_factory=list)
    top_k: int = Field(default=10, ge=1, le=200)
    min_importance: float = Field(default=0.0, ge=0.0, le=1.0)


@router.post("/memory/query", response_model=APIEnvelope)
async def query_memory(request: Request, req_id: RequestID, body: MemoryQueryReq):
    repo: ports.MemoryRepositoryPort = await get_mem_repo(request)
    page = await repo.list(PageParams(cursor="", limit=min(200, max(100, body.top_k * 5))))
    qtokens = {t.lower() for t in body.content.split() if len(t) >= 3}
    scored: list[tuple[Memory, float]] = []
    for m in page.items:
        if body.tiers and m.memory_type not in body.tiers:
            continue
        if m.importance < body.min_importance:
            continue
        mtokens = {t.lower() for t in (m.content + " " + (m.summary or "")).split() if len(t) >= 3}
        overlap = len(qtokens & mtokens)
        if qtokens:
            denom = len(qtokens | mtokens) or 1
            jaccard = overlap / denom if denom else 0.0
        else:
            jaccard = 0.0
        score = jaccard + m.importance * 0.1
        scored.append((m, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[: body.top_k]
    data = [{**m.model_dump(mode="json"), "score": round(s, 4)} for m, s in top]
    return ok_envelope(data, request_id=req_id)


class MemoryCompressReq(BaseModel):
    model_config = ConfigDict(extra="forbid")

    older_than_days: int = Field(default=30, ge=1, le=10 * 365)
    tiers: list[str] = Field(default_factory=list)


@router.post("/memory/compress", response_model=APIEnvelope)
async def compress_memory(
    request: Request,
    req_id: RequestID,
    body: MemoryCompressReq,
):
    repo: ports.MemoryRepositoryPort = await get_mem_repo(request)
    page = await repo.list(PageParams(cursor="", limit=200))
    cutoff = datetime.now(UTC) - timedelta(days=body.older_than_days)
    updated: list[str] = []
    for m in page.items:
        if body.tiers and m.memory_type not in body.tiers:
            continue
        if m.created_at <= cutoff and not m.is_compressed:
            m.is_compressed = True
            m.summary = m.summary or m.content[:120]
            try:
                await repo.update(m)
                updated.append(str(m.id))
            except Exception:
                pass
    return ok_envelope(
        {"compressed_count": len(updated), "ids": updated[:200]},
        request_id=req_id,
    )


# ===========================================================================
# 6. UAP Wire (M5.2)
# ===========================================================================


@router.get("/uap/transports", response_model=APIEnvelope)
async def list_uap_transports(req_id: RequestID):
    transports = [
        {"id": "inproc", "scheme": "memory", "endpoint": "astra.uap.inproc", "state": "available"},
        {"id": "http", "scheme": "https", "endpoint": "/v1/uap/envelope/send", "state": "available"},
    ]
    return ok_envelope(transports, request_id=req_id)


class InProcBindReq(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str | None = None
    capabilities: list[str] = Field(default_factory=list)


@router.post("/uap/transports/inproc", response_model=APIEnvelope)
async def bind_inproc_transport(req_id: RequestID, body: InProcBindReq):
    actor_id = body.actor_id or f"inproc:{uuid4().hex[:12]}"
    token = f"uap.{uuid4().hex}.{int(time.time())}"
    return ok_envelope(
        {
            "transport_id": "inproc",
            "actor_id": actor_id,
            "token": token,
            "capabilities": list(body.capabilities),
            "send_url": "/v1/uap/envelope/send",
            "created_at": datetime.now(UTC).isoformat(),
        },
        request_id=req_id,
    )


class UAPEnvelopeSendReq(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: uuid4().hex)
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None
    kind: str = "message"
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/uap/envelope/send", response_model=APIEnvelope)
async def uap_envelope_send(req_id: RequestID, body: UAPEnvelopeSendReq = Body(...)):
    import hashlib

    payload_bytes = repr(body.payload).encode("utf-8")
    sha = hashlib.sha256(payload_bytes).hexdigest()
    return ok_envelope(
        {
            "accepted": True,
            "envelope_id": body.id,
            "routed_to": body.to or "inproc:default",
            "payload_sha256": sha,
            "request_id": req_id,
            "received_at": datetime.now(UTC).isoformat(),
        },
        request_id=req_id,
    )


__all__ = ["router"]
