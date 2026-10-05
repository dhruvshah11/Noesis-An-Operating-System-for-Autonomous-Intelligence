"""
Kernel root — SysCall surface + Kernel + AgentContext + AgentHandle.

The kernel is the **only** module that imports capabilities, scheduler,
allocators, and model router together.  Rules:
  1. Agents never call adapters directly — they ask the kernel via syscalls.
  2. The kernel is the only code that inspects a CapabilityToken.
  3. Every syscall records an OpenTelemetry-shaped span record so
     observability tools (§12 frontend, §13 Prometheus) can render traces.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from noesis.logging import get_logger

from .allocators import MemoryAllocator, QuotaEnvelope
from .capabilities import (
    Capability,
    CapabilityOp,
    CapabilityToken,
    PermissionDenied,
)
from .interrupts import (
    CrashRestartPolicy,
    Interrupt,
    InterruptCode,
    IrqAck,
    IrqHandler,
)
from .model_router import ModelProfile, ModelRouter, RoutingConstraint
from .scheduler import Deadline, Priority, Scheduler, TaskHandle, TaskStatus

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Awaitable, Callable

    from noesis.core.ports import ChatPort, EmbeddingPort

log = get_logger(__name__)


class SysCall(StrEnum):
    """All 27 system calls exposed to agents.

    Keep this list SHORT — each is a trust boundary.
    """

    # Memory
    MEMORY_READ = "memory_read"
    MEMORY_WRITE = "memory_write"
    MEMORY_SEARCH = "memory_search"
    MEMORY_PRUNE = "memory_prune"

    # Knowledge / RAG
    RAG_SEARCH = "rag_search"
    RAG_INGEST = "rag_ingest"

    # Model inference
    MODEL_CHAT = "model_chat"
    MODEL_EMBED = "model_embed"
    MODEL_ROUTE = "model_route"

    # Tooling
    TOOL_INVOKE = "tool_invoke"
    TOOL_REGISTER = "tool_register"
    TOOL_DESCRIBE = "tool_describe"

    # Communication
    SEND_MESSAGE = "send_message"
    BROADCAST_EVENT = "broadcast_event"
    SUBSCRIBE_EVENTS = "subscribe_events"

    # Lifecycle
    SPAWN_AGENT = "spawn_agent"
    KILL_AGENT = "kill_agent"
    SUSPEND = "suspend"
    RESUME = "resume"

    # Workspace
    WORKSPACE_READ = "workspace_read"
    WORKSPACE_WRITE = "workspace_write"

    # Tracing / meta
    TRACE_EVENT = "trace_event"
    GET_CLOCK = "get_clock"
    GET_RUN_CONTEXT = "get_run_context"

    # Plugin
    PLUGIN_LOAD = "plugin_load"
    PLUGIN_CALL = "plugin_call"


@dataclass(slots=True)
class SysCallResult:
    """Canonical return shape for every syscall."""

    syscall: SysCall
    success: bool
    payload: Any = None
    error: str | None = None
    latency_ms: float = 0.0
    trace_id: UUID = field(default_factory=uuid4)
    span_id: UUID = field(default_factory=uuid4)
    artifacts: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentContext:
    """Per-agent run-context stored inside the kernel (in the capability table).

    Agents never receive this directly; they receive an opaque
    :class:`AgentHandle`.  The kernel keeps the authoritative truth here.
    """

    agent_id: str
    agent_type: str
    run_id: UUID
    token: CapabilityToken
    capabilities: list[Capability]
    workspace_id: str | None
    crash_policy: CrashRestartPolicy
    crash_backoff_s: float
    crash_attempts: int = 0
    irq_handler: IrqHandler | None = None
    inbox: asyncio.Queue[Interrupt] = field(default_factory=asyncio.Queue)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    state: dict[str, Any] = field(default_factory=dict)

    async def deliver_irq(self, irq: Interrupt) -> IrqAck:
        if self.irq_handler is None:
            return IrqAck.ESCALATE
        try:
            return self.irq_handler(self, irq)
        except Exception as exc:
            log.error(
                "kernel.irq_handler_crashed",
                agent_id=self.agent_id,
                irq=irq.code.value,
                exc=str(exc),
            )
            return IrqAck.ESCALATE


@dataclass(frozen=True, slots=True)
class AgentHandle:
    """Opaque handle returned by :meth:`Kernel.spawn_agent`."""

    agent_id: str
    run_id: UUID

    # Allow handles to work as dict keys / in sets.
    def __hash__(self) -> int:
        return hash((self.agent_id, self.run_id))


class KernelState(StrEnum):
    BOOTING = "booting"
    RUNNING = "running"
    PAUSED = "paused"
    SHUTTING_DOWN = "shutting_down"
    SHUT_DOWN = "shut_down"


class Kernel:
    """
    The Noesis microkernel.

    Defaults are tuned for single-process deployment; distributed execution
    plane adds a Raft-consensus replicated kernel via §Future F-8.

    Construct with :meth:`Kernel.build_default()` which wires sane defaults
    (background scheduler GC, default chat port registered for model calls,
    etc).
    """

    def __init__(
        self,
        *,
        scheduler: Scheduler | None = None,
        allocator: MemoryAllocator | None = None,
        model_router: ModelRouter | None = None,
        chat_port: ChatPort | None = None,
        embedding_port: EmbeddingPort | None = None,
    ) -> None:
        self._scheduler = scheduler or Scheduler(emit_irq=self.emit_irq)
        self._allocator = allocator or MemoryAllocator(emit_irq=self.emit_irq)
        self._router = model_router or ModelRouter()
        self._agents: dict[tuple[str, UUID], AgentContext] = {}
        self._tokens: dict[UUID, tuple[str, UUID]] = {}  # token.id -> (agent_id, run_id)
        self._cap_table: dict[tuple[str, UUID], list[Capability]] = {}
        self._subscribers: dict[str, list[Callable[[dict[str, Any]], Awaitable[None]]]] = defaultdict(list)
        self._state: KernelState = KernelState.BOOTING
        self._chat_port = chat_port
        self._embedding_port = embedding_port
        self._tool_dispatch: dict[str, Callable[..., Awaitable[Any]]] = {}
        self._span_records: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._started_at: datetime | None = None
        # Hooks for syscall handlers (populated via plugins / kernel boot).
        self._handlers: dict[SysCall, Callable[[AgentContext, dict[str, Any]], Awaitable[SysCallResult]]] = {}
        # Shared service container (repository adapters, tool registries, …).
        # Accessed by DI factories in astra.core.di; plugins add their own
        # services here via the plugin manifest ``caps_requested`` scope.
        self._services: dict[str, Any] = {}
        self._register_default_handlers()

    # ----------------------------------------------------------- Construction

    @classmethod
    def build_default(cls) -> Kernel:
        """Sensible-production ready defaults.

        Callers are expected to wire chat/embedding ports later (they require
        credentials, which may not be available on import).
        """
        k = cls()
        k._register_default_models()
        return k

    # ----------------------------------------------------------- Lifecycle

    @property
    def state(self) -> KernelState:
        return self._state

    async def __aenter__(self) -> Kernel:
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.stop()

    async def start(self) -> None:
        if self._state != KernelState.BOOTING:
            return
        await self._scheduler.start()
        await self._allocator.start()
        self._started_at = datetime.now(UTC)
        self._state = KernelState.RUNNING
        await self.emit_irq(
            Interrupt(
                code=InterruptCode.KERNEL_BOOTED,
                payload={
                    "scheduler_running": True,
                    "allocator_gc_running": True,
                },
            )
        )
        log.info("kernel.started", started_at=self._started_at.isoformat())

    async def stop(self) -> None:
        if self._state in {KernelState.SHUT_DOWN, KernelState.SHUTTING_DOWN}:
            return
        self._state = KernelState.SHUTTING_DOWN
        await self.emit_irq(Interrupt(code=InterruptCode.KERNEL_SHUTDOWN))
        # Kill remaining agents with clean IRQ.
        async with self._lock:
            agents = list(self._agents.values())
        for ctx in agents:
            with suppress(Exception):
                await ctx.deliver_irq(Interrupt(code=InterruptCode.KERNEL_SHUTDOWN, source="shutdown"))
        await self._scheduler.stop()
        await self._allocator.stop()
        self._state = KernelState.SHUT_DOWN
        log.info("kernel.stopped")

    # ----------------------------------------------------------- Capability table

    def spawn_agent(
        self,
        *,
        agent_id: str,
        agent_type: str,
        run_id: UUID | None = None,
        capabilities: list[Capability],
        workspace_id: str | None = None,
        crash_policy: CrashRestartPolicy = CrashRestartPolicy.BACKOFF_EXPONENTIAL,
        crash_backoff_s: float = 0.5,
        quota: QuotaEnvelope | None = None,
        irq_handler: IrqHandler | None = None,
    ) -> AgentHandle:
        run_id = run_id or uuid4()
        token = CapabilityToken(owner_agent_id=agent_id, workspace_id=workspace_id)
        ctx = AgentContext(
            agent_id=agent_id,
            agent_type=agent_type,
            run_id=run_id,
            token=token,
            capabilities=list(capabilities),
            workspace_id=workspace_id,
            crash_policy=crash_policy,
            crash_backoff_s=crash_backoff_s,
            irq_handler=irq_handler,
        )
        self._agents[(agent_id, run_id)] = ctx
        self._tokens[token.id] = (agent_id, run_id)
        self._cap_table[(agent_id, run_id)] = list(capabilities)
        if quota is None:
            quota = QuotaEnvelope(agent_id=agent_id)
        self._allocator.register_agent(quota)
        log.info("kernel.agent_spawned", agent_id=agent_id, agent_type=agent_type, run_id=str(run_id))
        return AgentHandle(agent_id=agent_id, run_id=run_id)

    # ----------------------------------------------------------- Syscall surface

    async def syscall(
        self,
        handle: AgentHandle,
        call: SysCall,
        payload: dict[str, Any] | None = None,
    ) -> SysCallResult:
        """Invoke a kernel syscall on behalf of ``handle``.

        This is the single trust boundary — every capability check,
        permission denial, and trace span passes through here.
        """
        import time

        if self._state not in {KernelState.RUNNING, KernelState.PAUSED}:
            return SysCallResult(
                syscall=call,
                success=False,
                error=f"Kernel state {self._state.value} does not accept syscalls",
            )

        started = time.perf_counter()
        trace_id = uuid4()
        span_id = uuid4()
        ctx = self._agents.get((handle.agent_id, handle.run_id))
        if ctx is None:
            res = SysCallResult(
                syscall=call,
                success=False,
                error=f"Unknown agent handle {handle.agent_id}/{handle.run_id}",
                trace_id=trace_id,
                span_id=span_id,
            )
            self._record_span(res)
            return res

        # Capability check.
        cap_op, target = self._syscall_to_capability(call, payload or {})
        caps = self._cap_table[(handle.agent_id, handle.run_id)]
        if not any(c.allows(cap_op, target) for c in caps):
            denied = PermissionDenied(
                token_id=ctx.token.id,
                op=cap_op,
                target=target,
                details=f"syscall={call.value}",
            )
            latency_ms = (time.perf_counter() - started) * 1000
            res = SysCallResult(
                syscall=call,
                success=False,
                error=denied.args[0] if denied.args else str(denied),
                latency_ms=round(latency_ms, 3),
                trace_id=trace_id,
                span_id=span_id,
            )
            self._record_span(res, denied=True)
            return res

        # Dispatch to the registered handler.
        handler = self._handlers.get(call)
        if handler is None:
            return SysCallResult(
                syscall=call,
                success=False,
                error=f"No handler for syscall {call.value}",
                latency_ms=round((time.perf_counter() - started) * 1000, 3),
                trace_id=trace_id,
                span_id=span_id,
            )
        try:
            result = await handler(ctx, payload or {})
        except PermissionDenied as exc:
            result = SysCallResult(syscall=call, success=False, error=str(exc))
        except Exception as exc:
            result = SysCallResult(
                syscall=call,
                success=False,
                error=f"{type(exc).__name__}: {exc}"[:500],
            )
            log.warning("kernel.syscall_unhandled_error", agent=handle.agent_id, call=call.value, error=result.error)
        latency_ms = (time.perf_counter() - started) * 1000
        result.latency_ms = round(latency_ms, 3)
        result.trace_id = trace_id
        result.span_id = span_id
        self._record_span(result)
        return result

    # ----------------------------------------------------------- IRQ / Event delivery

    async def emit_irq(self, irq: Interrupt) -> None:
        """Deliver IRQ to matching agents."""
        if irq.for_task_id is not None:
            # Find owner via scheduler state and deliver directly.
            return
        # Broadcast to every agent's inbox.
        async with self._lock:
            agents = list(self._agents.values())
        for ctx in agents:
            await ctx.inbox.put(irq)

    async def publish_event(self, topic: str, payload: dict[str, Any]) -> None:
        self._span_records.append(
            {
                "topic": topic,
                "payload": dict(payload),
                "ts": datetime.now(UTC).isoformat(),
            }
        )
        # Fan out to subscribers.
        handlers = list(self._subscribers.get(topic, ()))
        if handlers:
            await asyncio.gather(*(h(dict(payload)) for h in handlers), return_exceptions=True)

    def subscribe_events(self, topic: str, handler: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        self._subscribers[topic].append(handler)

    # ----------------------------------------------------------- Ports

    def register_chat_port(self, port: ChatPort) -> None:
        self._chat_port = port

    def register_embedding_port(self, port: EmbeddingPort) -> None:
        self._embedding_port = port

    def register_tool(self, name: str, fn: Callable[..., Awaitable[Any]]) -> None:
        self._tool_dispatch[name] = fn

    def register_model_profile(self, profile: ModelProfile) -> None:
        self._router.register(profile)

    # ----------------------------------------------------------- Scheduler pass-through

    def spawn_task(
        self,
        fn: Callable[..., Awaitable[Any]],
        *,
        agent_handle: AgentHandle,
        priority: Priority = Priority.USER,
        deadline: Deadline | None = None,
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
    ) -> TaskHandle:
        return self._scheduler.spawn(
            fn,
            owner_agent_id=agent_handle.agent_id,
            priority=priority,
            deadline=deadline,
            args=args,
            kwargs=kwargs,
        )

    def task_status(self, handle: TaskHandle) -> TaskStatus | None:
        state = self._scheduler.status_of(handle)
        return state.status if state else None

    # ----------------------------------------------------------- Router

    def route_model(self, constraint: RoutingConstraint, input_tokens: int = 0, output_tokens: int = 1024):
        return self._router.route(constraint=constraint, estimated_input_tokens=input_tokens, estimated_output_tokens=output_tokens)

    # ----------------------------------------------------------- Internals

    def _syscall_to_capability(self, call: SysCall, payload: dict[str, Any]) -> tuple[CapabilityOp, str]:
        """Map each syscall to its (op, target) pair for capability checks."""
        mapping: dict[SysCall, tuple[CapabilityOp, str]] = {
            SysCall.MEMORY_READ: (CapabilityOp.MEMORY_READ, payload.get("zone", "*")),
            SysCall.MEMORY_WRITE: (CapabilityOp.MEMORY_WRITE, payload.get("zone", "*")),
            SysCall.MEMORY_SEARCH: (CapabilityOp.MEMORY_READ, payload.get("zone", "*")),
            SysCall.MEMORY_PRUNE: (CapabilityOp.MEMORY_PRUNE, payload.get("zone", "*")),
            SysCall.RAG_SEARCH: (CapabilityOp.RAG_SEARCH, payload.get("namespace", "*")),
            SysCall.RAG_INGEST: (CapabilityOp.RAG_INGEST, payload.get("namespace", "*")),
            SysCall.MODEL_CHAT: (CapabilityOp.MODEL_INFERENCE, "chat"),
            SysCall.MODEL_EMBED: (CapabilityOp.MODEL_INFERENCE, "embedding"),
            SysCall.MODEL_ROUTE: (CapabilityOp.MODEL_INFERENCE, "route"),
            SysCall.TOOL_INVOKE: (CapabilityOp.TOOL_INVOKE, payload.get("tool", "*")),
            SysCall.TOOL_REGISTER: (CapabilityOp.TOOL_REGISTER, payload.get("tool", "*")),
            SysCall.TOOL_DESCRIBE: (CapabilityOp.TOOL_INVOKE, payload.get("tool", "*")),
            SysCall.SEND_MESSAGE: (CapabilityOp.SEND_MESSAGE, payload.get("recipient_agent", "*")),
            SysCall.BROADCAST_EVENT: (CapabilityOp.BROADCAST_EVENT, payload.get("topic", "*")),
            SysCall.SUBSCRIBE_EVENTS: (CapabilityOp.BROADCAST_EVENT, payload.get("topic", "*")),
            SysCall.SPAWN_AGENT: (CapabilityOp.SPAWN_AGENT, "*"),
            SysCall.KILL_AGENT: (CapabilityOp.KILL_AGENT, payload.get("agent_id", "*")),
            SysCall.SUSPEND: (CapabilityOp.ADMIN, "self"),
            SysCall.RESUME: (CapabilityOp.ADMIN, "self"),
            SysCall.WORKSPACE_READ: (CapabilityOp.WORKSPACE_READ, payload.get("path", "*")),
            SysCall.WORKSPACE_WRITE: (CapabilityOp.WORKSPACE_WRITE, payload.get("path", "*")),
            SysCall.TRACE_EVENT: (CapabilityOp.SEND_MESSAGE, "trace"),
            SysCall.GET_CLOCK: (CapabilityOp.MEMORY_READ, "clock"),
            SysCall.GET_RUN_CONTEXT: (CapabilityOp.SEND_MESSAGE, "run_context"),
            SysCall.PLUGIN_LOAD: (CapabilityOp.ADMIN, "plugin"),
            SysCall.PLUGIN_CALL: (CapabilityOp.TOOL_INVOKE, payload.get("plugin", "*")),
        }
        return mapping.get(call, (CapabilityOp.ADMIN, call.value))

    def _register_default_handlers(self) -> None:
        # The default handlers keep the kernel operational even before plugins
        # install richer adapters.  They either stub out responses, or delegate
        # to the registered port.

        async def _h_memory_read(ctx: AgentContext, payload: dict[str, Any]) -> SysCallResult:
            # Delegate to registered MemoryRepositoryPort when present; fall back
            # to the allocator's accounting to return an empty list in stubs.
            mem_repo = self._services.get("memories")
            if mem_repo is not None:
                from noesis.types import PageParams

                params = PageParams(limit=int(payload.get("limit", 50)))
                page = await mem_repo.list_for_scope(
                    scope=payload.get("scope", "user"),
                    scope_id=payload.get("scope_id"),
                    params=params,
                )
                return SysCallResult(
                    SysCall.MEMORY_READ,
                    success=True,
                    payload={
                        "items": [m.model_dump(mode="json") for m in page.items],
                        "total": page.total,
                        "next_cursor": page.next_cursor,
                        "has_more": page.has_more,
                    },
                )
            return SysCallResult(SysCall.MEMORY_READ, success=True, payload={"items": []})

        async def _h_memory_write(ctx: AgentContext, payload: dict[str, Any]) -> SysCallResult:
            tokens = int(payload.get("tokens", 0))
            zone = (payload.get("zone") or "working").lower()
            from .allocators import MemoryZone

            zone_e = MemoryZone(zone) if zone in {z.value for z in MemoryZone} else MemoryZone.WORKING
            alloc = await self._allocator.malloc(ctx.agent_id, zone_e, tokens)
            return SysCallResult(
                SysCall.MEMORY_WRITE,
                success=True,
                payload={
                    "allocation_id": str(alloc.id),
                    "expires_at": alloc.expires_at.isoformat() if alloc.expires_at else None,
                },
            )

        async def _h_model_chat(ctx: AgentContext, payload: dict[str, Any]) -> SysCallResult:
            port = self._chat_port
            if port is None:
                return SysCallResult(SysCall.MODEL_CHAT, success=False, error="No ChatPort installed in Kernel")
            response = await port.chat(
                messages=payload.get("messages", []),
                tools=payload.get("tools"),
                tool_choice=payload.get("tool_choice"),
                system_prompt=payload.get("system_prompt"),
            )
            return SysCallResult(
                SysCall.MODEL_CHAT,
                success=True,
                payload={
                    "content": response.content,
                    "tool_calls": response.tool_calls,
                    "usage": response.usage.model_dump() if hasattr(response.usage, "model_dump") else dict(response.usage),
                    "latency_ms": response.latency_ms,
                    "finish_reason": response.finish_reason,
                },
            )

        async def _h_model_route(ctx: AgentContext, payload: dict[str, Any]) -> SysCallResult:
            from .model_router import RoutingConstraint

            rc = RoutingConstraint(**{k: v for k, v in payload.items() if v is not None})
            decision = self._router.route(
                constraint=rc,
                estimated_input_tokens=int(payload.get("input_tokens", 0)),
                estimated_output_tokens=int(payload.get("output_tokens", 1024)),
            )
            return SysCallResult(
                SysCall.MODEL_ROUTE,
                success=True,
                payload={
                    "call_id": str(decision.call_id),
                    "primary": {
                        "provider": decision.primary.profile.provider.value,
                        "model_id": decision.primary.profile.model_id,
                        "model_class": decision.primary.profile.model_class.value,
                        "score": round(decision.primary.score, 4),
                        "cost_estimate": round(decision.primary.cost_estimate, 6),
                        "components": {k: round(v, 4) for k, v in decision.primary.components.items()},
                    },
                    "fallbacks": [
                        {
                            "provider": f.profile.provider.value,
                            "model_id": f.profile.model_id,
                            "score": round(f.score, 4),
                        }
                        for f in decision.fallbacks
                    ],
                    "reason": decision.reason,
                },
            )

        async def _h_tool_invoke(ctx: AgentContext, payload: dict[str, Any]) -> SysCallResult:
            tool = payload.get("tool")
            if not tool or tool not in self._tool_dispatch:
                return SysCallResult(SysCall.TOOL_INVOKE, success=False, error=f"Tool {tool!r} not registered")
            kwargs = dict(payload.get("args") or {})
            start = __import__("time").perf_counter()
            result = await self._tool_dispatch[tool](**kwargs)
            latency_ms = (__import__("time").perf_counter() - start) * 1000
            return SysCallResult(SysCall.TOOL_INVOKE, success=True, payload={"result": result}, latency_ms=round(latency_ms, 3))

        async def _h_clock(ctx: AgentContext, payload: dict[str, Any]) -> SysCallResult:
            return SysCallResult(
                SysCall.GET_CLOCK,
                success=True,
                payload={
                    "utc_now": datetime.now(UTC).isoformat(),
                },
            )

        self._handlers[SysCall.MEMORY_READ] = _h_memory_read
        self._handlers[SysCall.MEMORY_WRITE] = _h_memory_write
        self._handlers[SysCall.MODEL_CHAT] = _h_model_chat
        self._handlers[SysCall.MODEL_ROUTE] = _h_model_route
        self._handlers[SysCall.TOOL_INVOKE] = _h_tool_invoke
        self._handlers[SysCall.GET_CLOCK] = _h_clock

    def _register_default_models(self) -> None:
        # A modest library of well-known profile cards.  Not exhaustive —
        # plugins register more via :meth:`register_model_profile`.
        from noesis.types import ProviderType

        from .model_router import LatencySla, ModelClass, ModelProfile

        well_known: list[ModelProfile] = [
            ModelProfile(
                provider=ProviderType.OPENAI,
                model_id="gpt-4o-mini",
                model_class=ModelClass.CHAT_FAST,
                quality=0.80,
                reasoning=0.70,
                code=0.75,
                tool_use=0.85,
                context_tokens=128_000,
                max_output_tokens=16_384,
                input_cost_per_1k=0.00015,
                output_cost_per_1k=0.00060,
                latency=LatencySla(p50_ms=400, p95_ms=1_200, timeout_ms=60_000),
                capabilities=("json_mode", "structured_outputs", "tool_use"),
                tags=("default",),
            ),
            ModelProfile(
                provider=ProviderType.OPENAI,
                model_id="gpt-4o",
                model_class=ModelClass.CHAT_BALANCED,
                quality=0.95,
                reasoning=0.90,
                code=0.92,
                tool_use=0.95,
                vision=0.95,
                multimodal=0.95,
                context_tokens=128_000,
                max_output_tokens=16_384,
                input_cost_per_1k=0.00250,
                output_cost_per_1k=0.01000,
                latency=LatencySla(p50_ms=1_500, p95_ms=6_000, timeout_ms=120_000),
                capabilities=("json_mode", "structured_outputs", "tool_use", "vision"),
            ),
            ModelProfile(
                provider=ProviderType.ANTHROPIC,
                model_id="claude-3-5-sonnet-latest",
                model_class=ModelClass.CHAT_BALANCED,
                quality=0.94,
                reasoning=0.92,
                code=0.95,
                tool_use=0.94,
                context_tokens=200_000,
                max_output_tokens=8_192,
                input_cost_per_1k=0.00300,
                output_cost_per_1k=0.01500,
                latency=LatencySla(p50_ms=2_000, p95_ms=8_000, timeout_ms=180_000),
                capabilities=("tool_use", "prompt_caching", "long_context"),
                supports_prompt_caching=True,
            ),
            ModelProfile(
                provider=ProviderType.ANTHROPIC,
                model_id="claude-3-opus-latest",
                model_class=ModelClass.CHAT_VERY_STRONG,
                quality=0.99,
                reasoning=0.98,
                code=0.97,
                tool_use=0.97,
                context_tokens=200_000,
                max_output_tokens=8_192,
                input_cost_per_1k=0.01500,
                output_cost_per_1k=0.07500,
                latency=LatencySla(p50_ms=6_000, p95_ms=30_000, timeout_ms=300_000),
                capabilities=("tool_use", "prompt_caching", "long_context"),
                supports_prompt_caching=True,
            ),
            ModelProfile(
                provider=ProviderType.GEMINI,
                model_id="gemini-1.5-pro",
                model_class=ModelClass.CHAT_BALANCED,
                quality=0.93,
                reasoning=0.91,
                code=0.90,
                tool_use=0.90,
                vision=0.96,
                multimodal=0.96,
                audio=0.90,
                context_tokens=2_000_000,
                max_output_tokens=8_192,
                input_cost_per_1k=0.00125,
                output_cost_per_1k=0.00375,
                latency=LatencySla(p50_ms=2_000, p95_ms=12_000, timeout_ms=240_000),
                capabilities=("long_context", "vision", "audio", "tool_use"),
            ),
            ModelProfile(
                provider=ProviderType.OLLAMA,
                model_id="llama3.1:8b",
                model_class=ModelClass.CHAT_FAST,
                quality=0.70,
                reasoning=0.60,
                code=0.65,
                tool_use=0.60,
                context_tokens=128_000,
                max_output_tokens=8_192,
                input_cost_per_1k=0.0,
                output_cost_per_1k=0.0,
                requires_gpu=True,
                vram_gb_required=16,
                latency=LatencySla(p50_ms=2_000, p95_ms=6_000, timeout_ms=120_000),
                tags=("local", "on_prem"),
            ),
            ModelProfile(
                provider=ProviderType.OPENROUTER,
                model_id="meta-llama/llama-3.1-405b-instruct",
                model_class=ModelClass.CHAT_STRONG,
                quality=0.90,
                reasoning=0.85,
                code=0.88,
                tool_use=0.85,
                context_tokens=128_000,
                max_output_tokens=16_384,
                input_cost_per_1k=0.00270,
                output_cost_per_1k=0.00270,
                latency=LatencySla(p50_ms=4_000, p95_ms=20_000, timeout_ms=300_000),
                capabilities=("long_context", "tool_use"),
                tags=("open_source",),
            ),
        ]
        for p in well_known:
            self.register_model_profile(p)

    def _record_span(self, result: SysCallResult, *, denied: bool = False) -> None:
        self._span_records.append(
            {
                "trace_id": str(result.trace_id),
                "span_id": str(result.span_id),
                "syscall": result.syscall.value,
                "success": result.success and not denied,
                "denied": denied,
                "latency_ms": result.latency_ms,
                "error": result.error,
                "ts": datetime.now(UTC).isoformat(),
            }
        )
        # Trim buffer to last 10k spans so memory doesn't grow unbounded.
        if len(self._span_records) > 10_000:
            self._span_records = self._span_records[-10_000:]

    # ---------------------------------------------------------------- Admin

    def dump_recent_spans(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return list(self._span_records[-limit:])

    def scheduler_stats(self) -> dict[str, Any]:
        s = self._scheduler.stats()
        return {
            "tasks_queued": s.tasks_queued,
            "tasks_running": s.tasks_running,
            "tasks_done": s.tasks_done,
            "tasks_failed": s.tasks_failed,
            "tasks_cancelled": s.tasks_cancelled,
            "deadline_misses": s.deadline_misses,
            "per_agent_queued": s.per_agent_queued,
            "per_priority_queued": s.per_priority_queued,
        }

    def allocator_stats(self) -> dict[str, Any]:
        usage_by_zone: dict[str, int] = {}
        usage_by_agent: dict[str, int] = {}
        for (agent_id, zone), tokens in self._allocator._usage.items():
            usage_by_zone[zone.value] = usage_by_zone.get(zone.value, 0) + tokens
            usage_by_agent[agent_id] = usage_by_agent.get(agent_id, 0) + tokens
        return {
            "zones": usage_by_zone,
            "agents": usage_by_agent,
            "active_leases": len(self._allocator._leases),
            "registered_agents": len(self._allocator._agent_quotas),
        }

    def model_router_stats(self) -> dict[str, Any]:
        profiles = []
        for p in self._router._profiles:
            profiles.append(
                {
                    "provider": p.provider.value,
                    "model_id": p.model_id,
                    "model_class": p.model_class.value,
                    "input_cost_per_1k": round(p.input_cost_per_1k, 6),
                    "output_cost_per_1k": round(p.output_cost_per_1k, 6),
                    "context_tokens": p.context_tokens,
                    "max_output_tokens": p.max_output_tokens,
                    "quality": round(p.quality, 3),
                    "requires_gpu": p.requires_gpu,
                    "vram_gb_required": p.vram_gb_required,
                    "tags": list(p.tags),
                }
            )
        return {
            "profiles_registered": len(profiles),
            "profiles": profiles,
            "outcomes_recorded": len(self._router._outcome_buffer),
            "weights": {k: round(v, 4) for k, v in self._router._weights.items()},
        }

    def agents_registered_count(self) -> int:
        return len(self._agents)

    def uptime_seconds(self) -> float | None:
        if self._started_at is None:
            return None
        from datetime import UTC

        return (datetime.now(UTC) - self._started_at).total_seconds()
