"""
Universal Agent Protocol (UAP) — wire format + intent ontology.

Problem
-------
Existing inter-agent message formats (AutoGen, CrewAI, LangGraph messages) are
untyped, ad-hoc, and lock you into one Python process.  For Noesis to be the
*Linux of AI agents* (cross-language, cross-machine, durable over months) we
need a universal protocol with:

  - Wire-stable schema  (Pydantic → JSONSchema → Protobuf3 mapping is 1:1)
  - Intent ontology      (what the agent *wants*, not just what it says)
  - Evidence             (the *why* behind a claim)
  - Confidence           (0..1, calibration-aware)
  - Dependencies         (predecessor task IDs)
  - Artifacts            (attached blobs / Knowledge Object handles)
  - Tracing              (OTel trace_id / span_id so observability works)
  - Security             (JWT/signer + origin verification — §Zero Trust)

Why not use CloudEvents + Protobuf directly?
--------------------------------------------
CloudEvents is *too* generic for agent workloads (it's missing
intents/goals/evidence/confidence/dependencies — the things that make agents
*agents* vs message buses).  We align our top-level metadata shape with
CloudEvents but enrich it.  Protobuf support is a pure-subset translation
(Future F-12); for M0 we keep a single Pydantic source of truth.

Wire-Stability Rules
--------------------
  1. Never rename a field.  Deprecate via field-level ``deprecated=True``.
  2. New fields are always optional with sensible defaults.
  3. Enums use string values — never numeric values on the wire.
  4. ``message_id`` is a UUIDv7 (time-sortable — great for KX databases).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

if TYPE_CHECKING:
    from noesis.types import AgentType

# ---------------------------------------------------------------------------
# Intent Ontology — 22 common inter-agent intents.
# These are stable identifiers; do not renumber / rename.
# ---------------------------------------------------------------------------


class UAPIntent(StrEnum):
    """Stable, canonical agent intents — alphabetical by intent family."""

    # Communication (meta)
    ACK = "comm.ack"
    HEARTBEAT = "comm.heartbeat"
    PING = "comm.ping"
    PONG = "comm.pong"
    GREETING = "comm.greeting"

    # Orchestration
    DELEGATE = "orch.delegate"
    HANDOFF = "orch.handoff"
    SPAWN = "orch.spawn"
    KILL = "orch.kill"
    BROADCAST = "orch.broadcast"

    # Goals / execution
    DECLARE_GOAL = "goal.declare"
    GOAL_PROGRESS = "goal.progress"
    GOAL_COMPLETED = "goal.completed"
    GOAL_ABANDONED = "goal.abandoned"
    TASK_SUBMIT = "task.submit"
    TASK_RESULT = "task.result"
    TASK_FAILURE = "task.failure"

    # Knowledge
    QUERY = "know.query"
    QUERY_RESULT = "know.query_result"
    ASSERT = "know.assert"
    RECALL = "know.recall"

    # Tools
    TOOL_CALL = "tool.call"
    TOOL_RESULT = "tool.result"
    TOOL_FAILURE = "tool.failure"
    TOOL_REGISTER = "tool.register"

    # Reasoning
    THINK = "reason.think"
    REFLECT = "reason.reflect"
    CRITIQUE = "reason.critique"
    VOTE = "reason.vote"
    JUDGE = "reason.judge"

    # Observability
    TRACE = "obs.trace"
    METRIC = "obs.metric"
    LOG = "obs.log"

    # Error / failure escalation
    ERROR = "err.error"
    RETRY_REQUEST = "err.retry_request"
    ESCALATE = "err.escalate"


# ---------------------------------------------------------------------------
# Security / tracing / evidence
# ---------------------------------------------------------------------------


class UAPOrigin(BaseModel):
    """Who produced this message and on what authority."""

    agent_id: str
    agent_type: AgentType | str = "unknown"
    run_id: UUID | None = None
    workspace_id: str | None = None
    node_id: str | None = None  # e.g. kube pod name, distributed node
    pid: int | None = None
    signature: str | None = None  # EdDSA / JWS over UAPMessage.canonical_bytes()
    signer_issuer: str | None = None


class UAPEvidence(BaseModel):
    """One piece of evidence backing a claim."""

    model_config = ConfigDict(extra="allow")  # plugins may add fields.

    source: str  # URL, document ID, tool name, agent ID, ...
    kind: str = "text"  # text/quote/link/image/timestamp/tool_output
    snippet: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class UAPArtifact(BaseModel):
    """Pointer to a Knowledge Object / binary blob / workspace file."""

    id: str
    kind: str = "blob"  # blob / file / dataset / chart / diff / code_patch
    size_bytes: int | None = None
    mime_type: str | None = None
    url: str | None = None  # signed S3/GCS URL, or astra://knowledge/<id>
    sha256: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class UAPSpan(BaseModel):
    """OpenTelemetry-compatible tracing context."""

    trace_id: str | None = None  # 32-hex-char OTel trace_id
    span_id: str | None = None  # 16-hex-char OTel span_id
    parent_span_id: str | None = None
    service: str = "noesis"


class UAPGoal(BaseModel):
    """A single declarative goal (planner can emit many in a list)."""

    id: str = Field(default_factory=lambda: f"g-{uuid4().hex[:8]}")
    description: str
    priority: int = Field(default=5, ge=0, le=10)
    deadline: datetime | None = None
    success_criteria: str = ""
    parent_goal_id: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------


class UAPMessage(BaseModel):
    """
    One Universal Agent Protocol message.

    This is the *only* shape allowed on any agent-to-agent bus (local queue,
    NATS/Kafka durable stream, gRPC bidirectional stream — all must decode to
    a UAPMessage).  Plugins can add fields via ``extra='allow'`` but MUST
    NOT remove required fields.
    """

    model_config = ConfigDict(extra="allow")

    # --- Top-level CloudEvents-compatible metadata
    spec_version: str = "1.0"  # UAP wire format version
    message_id: UUID = Field(default_factory=uuid4)
    time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    type: str = Field(default=UAPIntent.TASK_SUBMIT)
    source: str = "noesis://kernel"
    subject: str = ""

    # --- Agent-specific payload contract
    intent: UAPIntent
    sender: UAPOrigin
    recipient_agent_id: str | None = None  # None == broadcast
    conversation_id: UUID | None = None
    thread_id: str | None = None

    # --- Semantics
    goals: list[UAPGoal] = Field(default_factory=list)
    body: str = ""
    structured: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: list[UAPEvidence] = Field(default_factory=list)

    # --- DAG / execution graph
    dependencies: list[UUID] = Field(default_factory=list)  # predecessor message_ids
    task_id: UUID | None = None

    # --- Attachments
    artifacts: list[UAPArtifact] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    metrics: list[dict[str, Any]] = Field(default_factory=list)
    resources: list[dict[str, Any]] = Field(default_factory=list)  # compute budget, GPU alloc, etc.
    execution_trace: list[dict[str, Any]] = Field(default_factory=list)  # OTel-style step records

    # --- Tracing
    span: UAPSpan = Field(default_factory=UAPSpan)

    # -------------------------------------------------------- Validation

    @field_validator("confidence")
    @classmethod
    def _round_confidence(cls, v: float) -> float:
        """Round to 4 decimals so wire representations are stable."""
        return round(float(v or 0.0), 4)

    @model_validator(mode="after")
    def _sync_type_and_intent(self) -> UAPMessage:
        if self.type != self.intent.value:
            # Keep ``type`` aligned with intent for CloudEvents compatibility.
            object.__setattr__(self, "type", self.intent.value)
        if not self.subject:
            object.__setattr__(self, "subject", f"{self.sender.agent_id}::{self.intent.value}")
        return self

    # -------------------------------------------------------- Canonical forms

    def canonical_json(self) -> bytes:
        """Deterministic JSON — used for signature verification."""
        import orjson

        payload = self.model_dump(mode="json", exclude={"span"})  # span is local-only
        return orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)

    def summary(self) -> str:
        return (
            f"[{self.time.isoformat(timespec='seconds')}] "
            f"{self.sender.agent_id} -> {self.recipient_agent_id or 'BROADCAST'} | "
            f"{self.intent.value} | confidence={self.confidence:.2f} | "
            f"evidence={len(self.evidence)} artifacts={len(self.artifacts)} | "
            f"{self.body[:80]}"
        )


# --- Marker / intent helper constructors -----------------------------------


def make_message(
    *,
    intent: UAPIntent,
    sender: UAPOrigin,
    body: str = "",
    **fields: Any,
) -> UAPMessage:
    """Thin helper that passes through kwargs to the UAPMessage constructor.

    Kept intentionally small so callers can migrate.  Future: add a
    fluent builder (``uap.msg(intent.TOOL_CALL).sender(…).body(…).done()``)
    if boilerplate becomes painful.
    """
    return UAPMessage(intent=intent, sender=sender, body=body, **fields)


# ---------------------------------------------------------------------------
# Pydantic v2 — resolve TYPE_CHECKING forward refs.
# UAPOrigin references AgentType which is imported under TYPE_CHECKING; even
# though `from __future__ import annotations` defers evaluation, some
# instantiation paths (pytest fixtures via faker + TestClient lifespan)
# hit the schema-builder *before* the runtime module finished importing,
# so we force a post-import rebuild here.
# ---------------------------------------------------------------------------
def _rebuild_models() -> None:  # pragma: no cover - only called at import time
    from noesis.types import AgentType as _AgentType

    _ns = {"AgentType": _AgentType}
    for _cls in (UAPOrigin, UAPEvidence, UAPArtifact, UAPGoal, UAPSpan, UAPMessage):
        try:
            _cls.model_rebuild(force=True, _types_namespace=_ns)
        except Exception:
            pass


_rebuild_models()
del _rebuild_models


# ---------------------------------------------------------------------------
# Transport layer — Turn / Envelope / SysCall
# ---------------------------------------------------------------------------


class UAPTransportKind(StrEnum):
    """Routed transport that produced a given UAPEnvelope."""

    LOCAL = "local"
    NATS = "nats"
    KAFKA = "kafka"
    GRPC = "grpc"
    REDIS = "redis"
    SQL_QUEUE = "sql_queue"


class UAPTurn(BaseModel):
    """One agent conversation step — request + replies, persisted as 1 row."""

    model_config = ConfigDict(extra="allow")

    turn_id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID = Field(default_factory=uuid4)
    sequence: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    request: UAPMessage
    replies: list[UAPMessage] = Field(default_factory=list)
    summary: str = ""
    wall_time_ms: float = 0.0


class UAPEnvelope(BaseModel):
    """Message wrapper for any bus (NATS/Kafka/gRPC/Redis/SQL/local queue)."""

    model_config = ConfigDict(extra="allow")

    envelope_id: UUID = Field(default_factory=uuid4)
    created_at_unix_ms: int = Field(default_factory=lambda: int(datetime.now(UTC).timestamp() * 1000))
    transport: UAPTransportKind = UAPTransportKind.LOCAL
    subject: str = ""
    payload: UAPMessage
    trace_headers: dict[str, str] = Field(default_factory=dict)

    def canonical_json(self) -> bytes:
        import orjson

        return orjson.dumps(self.model_dump(mode="json"), option=orjson.OPT_SORT_KEYS)


class UAPSysCallKind(StrEnum):
    """Privileged kernel ABI — agent ↔ kernel syscalls."""

    MEMORY_READ = "memory.read"
    MEMORY_WRITE = "memory.write"
    MEMORY_SEARCH = "memory.search"
    KNOWLEDGE_GET = "knowledge.get"
    KNOWLEDGE_PUT = "knowledge.put"
    RAG_RETRIEVE = "rag.retrieve"
    RAG_CHUNK = "rag.chunk"
    LLM_COMPLETE = "llm.complete"
    LLM_EMBED = "llm.embed"
    LLM_MULTIMODAL = "llm.multimodal"
    TOOL_INVOKE = "tool.invoke"
    TOOL_REGISTER = "tool.register"
    TOOL_LIST = "tool.list"
    SEND_MESSAGE = "msg.send"
    RECV_MESSAGE = "msg.recv"
    BROADCAST = "msg.broadcast"
    TOKEN_MALLOC = "token.malloc"
    TOKEN_FREE = "token.free"
    TOKEN_STATUS = "token.status"
    GET_CLOCK = "clock.get"
    SET_SCHEDULER = "scheduler.set"
    SPAWN_AGENT = "agent.spawn"
    SLEEP = "sleep"


class UAPSysCall(BaseModel):
    """One kernel syscall issued by an agent via its capability token."""

    model_config = ConfigDict(extra="allow")

    call_id: UUID = Field(default_factory=uuid4)
    issued_at_unix_ns: int = Field(default_factory=lambda: int(datetime.now(UTC).timestamp() * 1_000_000_000))
    caller_agent_id: str
    caller_handle: int = 0
    kind: UAPSysCallKind
    args_json: str = "{}"
    capability_token: str = ""


class UAPSysCallReply(BaseModel):
    """Kernel reply for one UAPSysCall."""

    model_config = ConfigDict(extra="allow")

    call_id: UUID
    completed_at_unix_ns: int = Field(default_factory=lambda: int(datetime.now(UTC).timestamp() * 1_000_000_000))
    success: bool = False
    denied: bool = False
    deny_reason: str = ""
    result_json: str = "{}"
    artifacts: list[str] = Field(default_factory=list)
    latency_ns: float = 0.0


__all__ = [
    "UAPArtifact",
    "UAPEnvelope",
    "UAPEvidence",
    "UAPGoal",
    "UAPIntent",
    "UAPMessage",
    "UAPOrigin",
    "UAPSpan",
    "UAPSysCall",
    "UAPSysCallKind",
    "UAPSysCallReply",
    "UAPTransportKind",
    "UAPTurn",
    "make_message",
]
