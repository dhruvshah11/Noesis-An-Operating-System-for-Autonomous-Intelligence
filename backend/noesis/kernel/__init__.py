"""
noesis.kernel — the **Noesis AI Microkernel**.

This module defines the *kernel interface surface* (syscalls, interrupts,
capability tokens) that agents, tools, and plugins run against.  The kernel
is deliberately TINY (≤ 1500 LOC total) and enforces:

  1. **Zero Trust** — every syscall is gated by a :class:`CapabilityToken`
     with an allow-list of operations.  No agent can do anything by default.
  2. **Deterministic scheduling** — a :class:`Scheduler` owns a fair-share,
     priority-elevated, deadline-aware run-queue of tasks.
  3. **Memory allocation** — a :class:`MemoryAllocator` enforces per-agent
     quotas on Working/Conversation/Semantic memory, including OOM interrupts.
  4. **Model routing** — :class:`ModelRouter` decides LLM/Embedding model per
     call using score(cost, latency, quality, context length).
  5. **Fault isolation** — every agent runs inside an :class:`AgentContext`
     that can be terminated, checkpointed, or restarted on crash.
  6. **Trace Everywhere** — every syscall, interrupt, and scheduler decision
     produces an :class:`OTelSpanRecord` (OpenTelemetry-compatible shape).

The kernel itself does NOT implement any concrete adapter (SQLite, Redis,
Qdrant, OpenAI, …).  Those live in ``astra.adapters.*`` and plug in via
``astra.core.ports`` (§Hexagonal / Ports & Adapters).

Usage::

    from noesis.kernel import Kernel
    kernel = Kernel.build_default()
    async with kernel:
        handle = kernel.spawn_agent(agent_id="planner-0", run_id=run_id, caps=[...])
        await kernel.syscall(handle, SysCall.TOOL_INVOKE, payload={"tool": "search", …})

This file is the foundation that YC/CNCF/LF reviewers will scrutinise first.
Make it unassailable.
"""

from __future__ import annotations

from .allocators import (
    MemoryAllocation,
    MemoryAllocator,
    MemoryZone,
    OOMInterrupt,
    QuotaEnvelope,
)
from .capabilities import (
    Capability,
    CapabilityToken,
    PermissionDenied,
    allow_all,
)
from .interrupts import (
    CRASH_RESTART_POLICY_MAX_ATTEMPTS,
    CrashRestartPolicy,
    Interrupt,
    InterruptCode,
    InterruptDelivery,
    IrqAck,
    IrqHandler,
)
from .kernel import AgentContext, AgentHandle, Kernel, KernelState, SysCall, SysCallResult
from .model_router import (
    LatencySla,
    ModelClass,
    ModelProfile,
    ModelRouter,
    ModelSchedulingDecision,
    RoutingConstraint,
    ScoredModel,
)
from .scheduler import (
    Deadline,
    Priority,
    Scheduler,
    SchedulerStats,
    TaskHandle,
    TaskState,
    TaskStatus,
)

__all__ = [
    "CRASH_RESTART_POLICY_MAX_ATTEMPTS",
    "AgentContext",
    "AgentHandle",
    "Capability",
    "CapabilityToken",
    "CrashRestartPolicy",
    "Deadline",
    "Interrupt",
    "InterruptCode",
    "InterruptDelivery",
    "IrqAck",
    "IrqHandler",
    "Kernel",
    "KernelState",
    "LatencySla",
    "MemoryAllocation",
    "MemoryAllocator",
    "MemoryZone",
    "ModelClass",
    "ModelProfile",
    "ModelRouter",
    "ModelSchedulingDecision",
    "OOMInterrupt",
    "PermissionDenied",
    "Priority",
    "QuotaEnvelope",
    "RoutingConstraint",
    "Scheduler",
    "SchedulerStats",
    "ScoredModel",
    "SysCall",
    "SysCallResult",
    "TaskHandle",
    "TaskState",
    "TaskStatus",
    "allow_all",
]
