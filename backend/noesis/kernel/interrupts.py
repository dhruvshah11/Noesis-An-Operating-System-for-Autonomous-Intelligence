"""
Interrupts (IRQs) + crash-restart policies.

Analogy to classic OSes:
  * ``InterruptCode.DEADLINE_MISSED`` → soft IRQ from scheduler.
  * ``InterruptCode.OOM``              → from memory allocator.
  * ``InterruptCode.PANIC``            → unhandled exception propagated.
  * ``InterruptCode.USER_SIGNAL``      → delivered over UAP (Ctrl-C / cancel).

Every interrupt is delivered via a two-phase protocol:
    1. The agent ``IrqHandler`` is called with the interrupt.  It returns
       ``IrqAck.ACK_HANDLED`` to suppress the kernel crash policy.
    2. If it returns anything else (or raises), the kernel applies the
       CrashRestartPolicy (backoff + max attempts, similar to Kubernetes
       pod restart policies).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum, StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

if TYPE_CHECKING:  # pragma: no cover
    from .kernel import AgentContext


CRASH_RESTART_POLICY_MAX_ATTEMPTS = 5


class InterruptCode(StrEnum):
    """Canonical IRQ codes — never change their numeric values (wire format)."""

    NONE = "none"
    # Kernel-level
    KERNEL_BOOTED = "kernel.booted"
    KERNEL_SHUTDOWN = "kernel.shutdown"
    # Scheduler
    DEADLINE_MISSED = "sched.deadline_missed"
    PREEMPT = "sched.preempt"
    TIMESLICE_EXPIRED = "sched.timeslice"
    # Memory allocator
    OOM = "mem.oom"
    QUOTA_EXCEEDED = "mem.quota_exceeded"
    # Agent lifecycle
    AGENT_CRASHED = "agent.crashed"
    AGENT_SPAWNED = "agent.spawned"
    AGENT_EXIT_OK = "agent.exit_ok"
    AGENT_EXIT_ERROR = "agent.exit_error"
    # Tool
    TOOL_TIMEOUT = "tool.timeout"
    TOOL_PERMISSION_DENIED = "tool.perm_denied"
    # User / control plane
    USER_CANCEL = "user.cancel"
    USER_PAUSE = "user.pause"
    USER_RESUME = "user.resume"
    # Supervisor / self-debug
    WATCHDOG_TRIP = "supervisor.watchdog"
    SELF_TEST_FAILED = "supervisor.self_test_fail"
    # UAP-level
    PROTOCOL_ERROR = "uap.protocol_error"
    PROTOCOL_DESERIALIZE_FAIL = "uap.deserialize_fail"
    # Catch-all
    PANIC = "panic"


class IrqAck(Enum):
    HANDLED = 1  # Agent handled it; kernel skips escalation.
    NEED_RETRY = 2  # Agent asks kernel to retry the last syscall/task.
    ESCALATE = 3  # Agent defers to CrashRestartPolicy (default).


IrqHandler = Callable[["AgentContext", "Interrupt"], IrqAck]


class CrashRestartPolicy(StrEnum):
    """Analogous to Kubernetes ``restartPolicy``."""

    NEVER = "never"
    ON_FAILURE = "on_failure"
    ALWAYS = "always"
    BACKOFF_LINEAR = "backoff_linear"  # base_delay_s * attempt (capped at 60s)
    BACKOFF_EXPONENTIAL = "backoff_exp"  # base_delay_s * 2**attempt (capped at 300s)


@dataclass(slots=True)
class Interrupt:
    """An interrupt delivered to an agent."""

    code: InterruptCode
    payload: dict[str, Any] = field(default_factory=dict)
    source: str = "kernel"
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    # If the IRQ pertains to a specific syscall / task, these are populated.
    for_syscall: str | None = None
    for_task_id: UUID | None = None
    retry_count: int = 0

    def next_retry_after(self, policy: CrashRestartPolicy, *, base_delay_s: float = 0.5) -> timedelta:
        """Return the backoff suggested by ``policy`` given ``retry_count``."""
        if policy == CrashRestartPolicy.NEVER:
            return timedelta(seconds=0)
        if policy in {CrashRestartPolicy.ALWAYS, CrashRestartPolicy.ON_FAILURE}:
            return timedelta(seconds=base_delay_s)
        attempt = max(0, self.retry_count)
        if policy == CrashRestartPolicy.BACKOFF_LINEAR:
            return timedelta(seconds=min(60.0, base_delay_s * (attempt + 1)))
        # BACKOFF_EXPONENTIAL (default for most production agents)
        return timedelta(seconds=min(300.0, base_delay_s * (2**attempt)))


@dataclass(slots=True)
class InterruptDelivery:
    """Record of a single IRQ handoff (for audit logs / traces)."""

    interrupt_id: UUID
    agent_id: str
    delivered_at: datetime
    ack: IrqAck
    handler_latency_ms: float
    escalated: bool
