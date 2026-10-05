"""
Noesis - The Autonomous Multi-Agent AI Operating System.

A production-grade platform for orchestrating specialised AI agents
with long-term memory, RAG, tool-calling, planning, and self-reflection.

Public API surface for the ``noesis`` package.

Subsystems exposed at top-level:
  * ``noesis.config``      — settings, env vars.
  * ``noesis.types``       — DTOs (Pydantic models shared across boundaries).
  * ``noesis.kernel``      — microkernel: syscalls, scheduler, allocator, router, interrupts.
  * ``noesis.uap``         — Universal Agent Protocol (cross-language wire format).
  * ``noesis.plugins``     — Plugin Ecosystem: manager, 12 hook groups, manifest, sandbox API.
  * ``noesis.core``        — Hexagonal ports (abstract) + DI container.
  * ``noesis.llm``         — LLM providers, 3-layer parse pipeline, prompt registry.
  * ``noesis.database``    — Adapter implementations (SQL, Qdrant, Redis).
  * ``noesis.api``         — FastAPI application (/v1 prefix, OpenAPI, idempotency).
  * ``noesis.cli``         — Typer entry point: ``noesis serve/doctor/shell/…``.
"""

from noesis.config import Settings, get_settings
from noesis.kernel import (
    AgentContext,
    AgentHandle,
    Capability,
    CapabilityToken,
    CrashRestartPolicy,
    Deadline,
    Interrupt,
    InterruptCode,
    Kernel,
    KernelState,
    MemoryAllocator,
    MemoryZone,
    ModelClass,
    ModelProfile,
    ModelRouter,
    PermissionDenied,
    Priority,
    QuotaEnvelope,
    RoutingConstraint,
    Scheduler,
    SchedulerStats,
    SysCall,
    SysCallResult,
    TaskHandle,
    TaskState,
)
from noesis.plugins import (
    HookGroup,
    NoesisPluginHookSpec,
    PluginCapabilityAPI,
    PluginLifecycleState,
    PluginLoadError,
    PluginManager,
    PluginManifest,
)
from noesis.types import (
    AgentType,
    ChatMessage,
    MessageRole,
    PlanStep,
    ProviderType,
    TaskStatus,
)
from noesis.uap import (
    UAPArtifact,
    UAPEvidence,
    UAPGoal,
    UAPIntent,
    UAPMessage,
    UAPOrigin,
    UAPSpan,
    make_message,
)

__version__ = "0.1.0"

__all__ = [
    "AgentContext",
    "AgentHandle",
    "AgentType",
    "Capability",
    "CapabilityToken",
    "ChatMessage",
    "CrashRestartPolicy",
    "Deadline",
    "HookGroup",
    "Interrupt",
    "InterruptCode",
    "Kernel",
    "KernelState",
    "MemoryAllocator",
    "MemoryZone",
    "MessageRole",
    "ModelClass",
    "ModelProfile",
    "ModelRouter",
    "NoesisPluginHookSpec",
    "PermissionDenied",
    "PlanStep",
    "PluginCapabilityAPI",
    "PluginLifecycleState",
    "PluginLoadError",
    "PluginManager",
    "PluginManifest",
    "Priority",
    "ProviderType",
    "QuotaEnvelope",
    "RoutingConstraint",
    "Scheduler",
    "SchedulerStats",
    "Settings",
    "SysCall",
    "SysCallResult",
    "TaskHandle",
    "TaskState",
    "TaskStatus",
    "UAPArtifact",
    "UAPEvidence",
    "UAPGoal",
    "UAPIntent",
    "UAPMessage",
    "UAPOrigin",
    "UAPSpan",
    "__version__",
    "get_settings",
    "make_message",
]
