"""
Core data types for Noesis.

Every public interface between agents, services, and the API uses
Pydantic v2 models from this module. This gives us:

  * Strict validation at trust boundaries (API, DB read/write, LLM output)
  * Zero-copy JSON serialisation via ``orjson``
  * IDE-friendly auto-complete and mypy type-checking
  * Schema generation for OpenAPI / JSONSchema tool-calling
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum, IntEnum
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4, uuid5

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag, field_validator, model_validator

NOESIS_NAMESPACE_PLAN = UUID("1b030f78-2b6b-4aa0-9ddc-7a6d82c0d5e5")
"""Deterministic namespace UUID used for all seeded PlanStep/ExecutionPlan ids."""

EPOCH_SENTINEL = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
"""Deterministic sentinel created_at used when ``deterministic=True`` so the
audit hash of a plan does not depend on wall-clock time."""

# ---------------------------------------------------------------------------
# Enums — shared across agents, API, and persistence
# ---------------------------------------------------------------------------


class StrEnum(str, Enum):
    """A string-backed Enum that serialises to its value."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class ProviderType(StrEnum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"
    LLAMACPP = "llamacpp"


class AgentType(StrEnum):
    """Specialised agents in the Noesis architecture.

    The 12-agent roster implements a hierarchical Judge/Critic/Executor/Supervisor
    pattern (see AUDIT.md §5) on top of the 7 baseline agents.
    """

    PLANNER = "planner"
    RESEARCH = "research"
    CODING = "coding"
    MEMORY = "memory"
    RAG = "rag"
    TOOL = "tool"
    REFLECTION = "reflection"
    JUDGE = "judge"
    CRITIC = "critic"
    EXECUTOR = "executor"
    SUPERVISOR = "supervisor"
    ORCHESTRATOR = "orchestrator"


class MessageRole(StrEnum):
    """Standard LLM chat roles + Noesis-specific extensions."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    OBSERVATION = "observation"
    REFLECTION = "reflection"


class TaskStatus(IntEnum):
    """Lifecycle of a plan-step / task in the execution queue."""

    PENDING = 0
    QUEUED = 1
    RUNNING = 2
    SUCCESS = 3
    FAILED = 4
    SKIPPED = 5
    AWAITING_INPUT = 6


class ConversationStatus(StrEnum):
    """Lifecycle status for a conversation thread — matches frontend Zod enum."""

    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Messaging primitives
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    """A single turn in a conversation.

    ``id`` + ``timestamp`` are auto-generated so callers only need to
    provide ``role`` and ``content`` (or ``tool_calls``).
    """

    model_config = ConfigDict(
        frozen=False,
        use_enum_values=True,
        extra="forbid",
        json_encoders={UUID: str, datetime: lambda v: v.isoformat()},
    )

    id: UUID = Field(default_factory=uuid4)
    role: MessageRole
    content: str | None = None
    name: str | None = Field(default=None, description="For tool-message attribution.")
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _enforce_message_invariants(self) -> ChatMessage:
        """Cross-field invariants — run AFTER all fields are populated.

        Rules:
          1. ``role='tool'`` requires ``tool_call_id`` (tool result attribution).
          2. Otherwise, the message must have at least one of: textual
             ``content`` or a ``tool_calls`` block (assistant asking to
             call tools).  An assistant message that calls tools can
             omit content for brevity.
        """
        role = self.role
        if role == MessageRole.TOOL:
            if not self.tool_call_id:
                raise ValueError("role='tool' requires tool_call_id")
            return self
        if self.content is None and not self.tool_calls:
            raise ValueError("ChatMessage must have content, tool_calls, or role='tool' with tool_call_id")
        return self


class Conversation(BaseModel):
    """Ordered sequence of messages forming one conversation thread."""

    id: UUID = Field(default_factory=uuid4)
    user_id: str | None = None
    title: str = "Untitled conversation"
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Persistence DTOs — 1:1 mirror of astra.database.models ORM classes
# (round-trippable via ORM.from_dto / ORM.to_dto helpers in sql_repos.py)
# ---------------------------------------------------------------------------


class User(BaseModel):
    """Noesis end-user (authenticated entity)."""

    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    email: str
    full_name: str | None = None
    is_active: bool = True
    is_admin: bool = False
    hashed_password: str | None = None
    external_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Message(BaseModel):
    """Individual turn inside a conversation thread."""

    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID
    role: str  # system/user/assistant/tool/observation/reflection
    content: str | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Memory(BaseModel):
    """Long-term semantic/episodic memory row.

    The embedding vector lives in a vector store (Qdrant); this DTO holds
    the provenance, AI-scored importance, and the human-readable text.
    """

    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    user_id: str | None = None
    memory_type: str  # episodic/semantic/project/working/conversation/instruction/meta
    content: str
    summary: str | None = None
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    access_count: int = 0
    is_compressed: bool = False
    vector_id: UUID
    scope: Literal["user", "project", "team", "system"] = "user"
    scope_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_accessed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Document(BaseModel):
    """Ingested RAG document (Knowledge Object — raw file payload / URI)."""

    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    user_id: str | None = None
    title: str
    source_uri: str
    mime_type: str = "application/octet-stream"
    byte_size: int = 0
    chunk_count: int = 0
    ingestion_status: Literal["pending", "processing", "ready", "failed"] = "pending"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class KnowledgeObject(BaseModel):
    """A structured Knowledge Object — the Noesis analogue of a "file".

    Unlike :class:`Document` (a raw payload), a KnowledgeObject carries
    semantic typing, provenance, references, and version so the AI kernel
    can treat it as a first-class addressable unit instead of opaque bytes.
    """

    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    workspace_id: str | None = None
    owner_id: str | None = None
    kind: str  # report/code/metric/dataset/spec/decision/experiment
    title: str
    summary: str | None = None
    body: str | None = None
    parent_id: str | None = None
    version: int = 1
    tags: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Artifact(BaseModel):
    """A produced output / file-attached payload from a task or agent.

    Mirrors :class:`noesis.uap.UAPArtifact` but with an Noesis-local UUID
    primary key so repository adapters can persist produced outputs.
    """

    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    task_id: str | None = None
    producer_agent_id: str | None = None
    kind: str
    name: str
    mime_type: str = "application/octet-stream"
    size_bytes: int = 0
    url: str | None = None
    sha256: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TaskExecution(BaseModel):
    """Audit log for a single plan-step / agent-run execution."""

    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    conversation_id: str | None = None
    run_id: str | None = None
    plan_step_id: str | None = None
    agent_type: str
    description: str
    status: int = 0  # maps to TaskStatus IntEnum for backward compat
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: float = 0.0
    error: str | None = None
    result_preview: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Planning & Task Decomposition
# ---------------------------------------------------------------------------


class PlanStep(BaseModel):
    """One step in a plan produced by the Planner agent."""

    id: UUID = Field(default_factory=uuid4)
    index: int = Field(ge=0)
    description: str = Field(min_length=3)
    assigned_agent: AgentType
    dependencies: list[UUID] = Field(default_factory=list)
    tool_hints: list[str] = Field(default_factory=list)
    rag_query: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    result: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @classmethod
    def deterministic(
        cls,
        *,
        index: int,
        description: str,
        assigned_agent: AgentType,
        seed: str,
        dependencies: list[UUID] | None = None,
        **kwargs: Any,
    ) -> PlanStep:
        """Return a PlanStep whose ``id`` is deterministic given ``(seed, index)``.

        Used by :meth:`ExecutionPlan.deterministic` and the determinism manifest
        so paper Claim C3 can assert bit-exact reproducibility on equal inputs.
        """
        step_id = uuid5(NOESIS_NAMESPACE_PLAN, f"step:{seed}:{index}")
        return cls(
            id=step_id,
            index=index,
            description=description,
            assigned_agent=assigned_agent,
            dependencies=list(dependencies or []),
            **kwargs,
        )


class ExecutionPlan(BaseModel):
    """A full plan: ordered steps the orchestrator will execute."""

    id: UUID = Field(default_factory=uuid4)
    goal: str = Field(min_length=5)
    steps: list[PlanStep] = Field(min_length=1)
    reasoning: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("steps")
    @classmethod
    def _contiguous_index(cls, steps: list[PlanStep]) -> list[PlanStep]:
        indices = sorted(s.index for s in steps)
        expected = list(range(len(steps)))
        if indices != expected:
            raise ValueError(f"PlanStep indices must be 0..n-1 contiguous, got {indices}")
        return steps

    @classmethod
    def deterministic(
        cls,
        *,
        goal: str,
        steps: list[PlanStep],
        reasoning: str,
        seed: str,
    ) -> ExecutionPlan:
        """Return an ExecutionPlan whose ``id`` + ``created_at`` + step-ordering
        + step-ids (via :meth:`PlanStep.deterministic`) are all derived from
        ``seed`` — guaranteeing SHA-256 equality across runs of equal inputs.
        """
        plan_id = uuid5(NOESIS_NAMESPACE_PLAN, f"plan:{seed}:{goal}")
        seeded_steps = [
            s.model_copy(
                update={
                    "id": uuid5(
                        NOESIS_NAMESPACE_PLAN,
                        f"step:{seed}:{s.index}",
                    ),
                    "dependencies": [uuid5(NOESIS_NAMESPACE_PLAN, f"step:{seed}:{s2.index}") for s2 in steps if s2.id in s.dependencies],
                },
            )
            for s in steps
        ]
        return cls(
            id=plan_id,
            goal=goal,
            steps=seeded_steps,
            reasoning=reasoning,
            created_at=EPOCH_SENTINEL,
        )


# ---------------------------------------------------------------------------
# LLM / Provider responses
# ---------------------------------------------------------------------------


class TokenUsage(BaseModel):
    """Unified token-usage accounting across providers."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


class ProviderResponse(BaseModel):
    """Standardised completion/chat response from any provider."""

    provider: ProviderType
    model: str
    content: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    usage: TokenUsage = Field(default_factory=TokenUsage)
    latency_ms: float = 0.0
    finish_reason: Literal["stop", "length", "tool_calls", "error", "unknown"] = "unknown"
    raw: Any = None


class BenchmarkResult(BaseModel):
    """Timing + throughput snapshot from a single provider.chat() call."""

    provider: str
    model: str
    reachable: bool
    used_mock: bool
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    first_token_latency_ms: float
    prompt_tokens_per_sec: float
    completion_tokens_per_sec: float
    fallback_provider: str
    error: str | None = None


class Embedding(BaseModel):
    """One embedding vector and its source metadata."""

    provider: ProviderType
    model: str
    vector: list[float]
    dimensions: int
    usage: TokenUsage = Field(default_factory=TokenUsage)


# ---------------------------------------------------------------------------
# Observability / Execution trace
# ---------------------------------------------------------------------------


class ToolCallRecord(BaseModel):
    """Audit record of one tool invocation."""

    tool_name: str
    arguments: dict[str, Any]
    result_preview: str
    success: bool
    latency_ms: float
    error: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentRunRecord(BaseModel):
    """Telemetry for a single agent execution."""

    agent: AgentType
    task_id: UUID | None = None
    status: TaskStatus
    duration_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    error: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Generic API envelope
# ---------------------------------------------------------------------------


class APIEnvelope[T](BaseModel):
    """Standard envelope for every JSON response.

    Consumers always look at the same keys: ``ok``, ``data``, ``error``,
    ``request_id`` — simplifies frontend error handling.
    """

    ok: bool
    data: T | None = None
    error: str | None = None
    request_id: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Pagination (cursor + offset)
# ---------------------------------------------------------------------------


class PageParams(BaseModel):
    """Cursor + limit pagination parameters accepted by list endpoints.

    Cursor is preferred over numeric offset because it remains stable when
    rows are inserted between pages.  Clients take ``next_cursor`` from a
    :class:`Page` response and pass it back as ``cursor`` on the next request.
    """

    cursor: str | None = Field(default=None, description="Opaque pagination cursor returned by the previous page.")
    limit: Annotated[int, Field(ge=1, le=200)] = Field(default=50, description="Maximum items per page.")


class Page[T](BaseModel):
    """Standard paginated envelope returned by list endpoints."""

    items: list[T]
    total: int | None = Field(default=None, description="Total matching items (server may omit for performance).")
    next_cursor: str | None = Field(default=None, description="Pass as ``cursor`` to fetch the next page.")
    has_more: bool = Field(default=False, description="True if a subsequent page exists.")


# ---------------------------------------------------------------------------
# Agent-to-Agent message envelope (MH-10)
# ---------------------------------------------------------------------------


class _BaseSignal(BaseModel):
    """Private base shared by every inter-agent signal."""

    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    signal_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    from_agent: AgentType
    to_agent: AgentType | None = Field(default=None, description="None = broadcast to any subscriber.")
    run_id: UUID | None = None


class ThinkSignal(_BaseSignal):
    """Agent broadcasts its internal reasoning (not shown to the user)."""

    kind: Literal["think"] = "think"
    reasoning: str


class SaySignal(_BaseSignal):
    """Agent emits a user-facing text utterance."""

    kind: Literal["say"] = "say"
    text: str
    conversation_id: UUID | None = None


class ToolCallSignal(_BaseSignal):
    """Agent asks the Tool Agent / Executor to invoke a tool."""

    kind: Literal["tool_call"] = "tool_call"
    tool_name: str
    arguments: dict[str, Any]


class ToolResultSignal(_BaseSignal):
    """Executor / Tool Agent returns a tool result."""

    kind: Literal["tool_result"] = "tool_result"
    tool_call_id: UUID
    tool_name: str
    result_preview: str
    success: bool
    error: str | None = None


class MemoryStoreSignal(_BaseSignal):
    """Memory Agent is asked to persist a memory item."""

    kind: Literal["memory_store"] = "memory_store"
    memory_type: Literal["working", "conversation", "episodic", "semantic", "project", "meta", "instruction"]
    content: str
    importance: float = Field(default=0.5, ge=0.0, le=1.0)


class CriticSignal(_BaseSignal):
    """Critic Agent publishes flaws it found in a candidate answer."""

    kind: Literal["critic"] = "critic"
    target_run_id: UUID
    flaws: list[str]
    suggested_fix: str
    severity: Annotated[int, Field(ge=0, le=3)]  # 0=nit, 1=minor, 2=major, 3=critical


class HandoffSignal(_BaseSignal):
    """Agent delegates responsibility to another agent (e.g. sub-orchestrator)."""

    kind: Literal["handoff"] = "handoff"
    target_agent: AgentType
    payload: dict[str, Any]


AgentMessageEnvelope = Annotated[
    Annotated[ThinkSignal, Tag("think")]
    | Annotated[SaySignal, Tag("say")]
    | Annotated[ToolCallSignal, Tag("tool_call")]
    | Annotated[ToolResultSignal, Tag("tool_result")]
    | Annotated[MemoryStoreSignal, Tag("memory_store")]
    | Annotated[CriticSignal, Tag("critic")]
    | Annotated[HandoffSignal, Tag("handoff")],
    Discriminator("kind"),
]
"""Typed discriminator-union for every agent-to-agent signal in the system."""


# ---------------------------------------------------------------------------
# Tri-state Executor decision system
# ---------------------------------------------------------------------------


class TriStateDecision(StrEnum):
    """Terminal tri-state decision from ExecutorAgent/Kriyakārī."""

    SIGNOFF = "signoff"
    REJECT = "reject"
    REPLAN = "replan"


class AcceptCriterion(BaseModel):
    """A single acceptance criterion with severity weight.

    ``severity`` ∈ {"low", "medium", "high", "critical"} maps to weights
    {0.05, 0.10, 0.20, 0.35} in the Executor scoring algorithm.
    """

    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    id: str = Field(min_length=1)
    description: str = Field(min_length=3)
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    met: bool = False


class ExecutorTriStateDecision(BaseModel):
    """Structured tri-state decision output from ExecutorAgent.run().

    Fields:
      decision: SIGNOFF | REJECT | REPLAN
      reason: Human-readable rationale for the decision
      violations: List of criterion IDs that were not met (empty on SIGNOFF)
      acceptance_confidence: 0.0..1.0 score driving the threshold decision
    """

    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    decision: TriStateDecision
    reason: str
    violations: list[str] = Field(default_factory=list)
    acceptance_confidence: float = Field(ge=0.0, le=1.0)
