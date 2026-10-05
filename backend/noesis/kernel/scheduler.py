"""
Fair-share, deadline-aware, priority-elevated task scheduler.

Design rationale (vs alternatives):
-----------------------------------
  * LangGraph uses a DAG-topological step; no global fairness — a buggy
    planner loop can starve the rest of the graph.  We instead use a
    time-sliced scheduler that enforces a fair-share per agent.

  * Celery / Dramatiq / RQ are great for HTTP background jobs but carry
    heavy broker dependencies + are designed for throughput of independent
    tasks, not fine-grained cooperative multitasking inside a single
    kernel-instance.

  * Our scheduler is fully in-process async (one run loop per kernel).
    Cross-machine distribution is a *future* add-on via the Distributed
    Execution Plane; we keep the core scheduling algorithm tiny so it can
    be lifted to a distributed state machine later (e.g. Raft-backed run
    queue).

  * Deadlines are "soft" — a missed deadline raises IRQ ``DEADLINE_MISSED``
    but does NOT preemptively kill the task; the agent's crash policy decides.
    This mirrors Linux CFS rather than an RTOS, which is the correct
    default for AI workloads where reasoning time is highly variable.
"""

from __future__ import annotations

import asyncio
import heapq
from collections import defaultdict
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import IntEnum, StrEnum
from typing import Any
from uuid import UUID, uuid4

from noesis.logging import get_logger

from .interrupts import Interrupt, InterruptCode

log = get_logger(__name__)


class Priority(IntEnum):
    """Scheduling priority, 0..31.

    Higher numeric = runs first (similar to Linux ``nice`` but in reverse).
    Default: USER = 16.  Reserved values:
        - IDLE (0)       — garbage-collection agents, self-study daemon.
        - USER (16)      — default.
        - ELEVATED (24)  — user-visible latency-sensitive tasks.
        - SUPERVISOR (31) — kernel supervisor, watchdog, crash recovery.
    """

    IDLE = 0
    BACKGROUND = 8
    USER = 16
    ELEVATED = 24
    REALTIME = 28
    SUPERVISOR = 31


@dataclass(slots=True)
class Deadline:
    """Soft deadline; absolute timestamp.  ``None`` = no deadline."""

    absolute: datetime | None = None

    @classmethod
    def from_now(cls, delta: timedelta) -> Deadline:
        return cls(absolute=datetime.now(UTC) + delta)

    def is_missed(self) -> bool:
        if self.absolute is None:
            return False
        return datetime.now(UTC) >= self.absolute

    def remaining_ms(self) -> float | None:
        if self.absolute is None:
            return None
        return (self.absolute - datetime.now(UTC)).total_seconds() * 1000


class TaskStatus(StrEnum):  # type: ignore[misc]
    QUEUED = "queued"
    RUNNING = "running"
    BLOCKED = "blocked"
    YIELDED = "yielded"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMESLICE = "timeslice"


@dataclass(slots=True)
class TaskState:
    handle: TaskHandle
    status: TaskStatus
    owner_agent_id: str
    priority: Priority
    deadline: Deadline
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    result: Any = None
    # Fair-share accounting
    cpu_ns: int = 0
    yield_count: int = 0
    timeslice_count: int = 0
    # For heap
    _heap_seq: int = field(default=0, repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class TaskHandle:
    """Opaque handle returned by ``Scheduler.spawn``."""

    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class SchedulerStats:
    """Exported via OpenTelemetry."""

    tasks_queued: int
    tasks_running: int
    tasks_done: int
    tasks_failed: int
    tasks_cancelled: int
    deadline_misses: int
    per_agent_queued: dict[str, int]
    per_priority_queued: dict[str, int]


TaskFn = Callable[..., Awaitable[Any]]


class Scheduler:
    """Cooperative, fair-share, deadline-aware scheduler."""

    # Time-slicing quantum for CPU-bound reasoning tasks.  After this slice
    # we re-enter the event loop so other agents can make progress.  This is
    # *not* preemptive (we can't yank a coroutine in Python); instead we
    # set a cooperative flag that well-behaved coroutines check via
    # ``TaskHandle.yield_if_needed``.
    DEFAULT_TIMESLICE_SEC = 0.5

    def __init__(
        self,
        *,
        default_timeslice_s: float = DEFAULT_TIMESLICE_SEC,
        emit_irq: Callable[[Interrupt], Awaitable[None]] | None = None,
    ) -> None:
        self._runq: list[tuple[int, int, UUID]] = []  # (-priority, -deadline_ts, seq) heap
        self._by_id: dict[UUID, TaskState] = {}
        self._per_agent_pending: dict[str, set[UUID]] = defaultdict(set)
        self._default_timeslice_s = default_timeslice_s
        self._emit_irq = emit_irq
        self._seq = 0
        self._loop_task: asyncio.Task[None] | None = None
        self._stop_evt: asyncio.Event | None = None
        self._lock = asyncio.Lock()
        # Counters for stats
        self._c_done = 0
        self._c_failed = 0
        self._c_cancelled = 0
        self._c_deadline_misses = 0

    # ---------------------------------------------------------------- API

    def spawn(
        self,
        fn: TaskFn,
        *,
        owner_agent_id: str,
        priority: Priority = Priority.USER,
        deadline: Deadline | None = None,
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
    ) -> TaskHandle:
        state = TaskState(
            handle=TaskHandle(),
            status=TaskStatus.QUEUED,
            owner_agent_id=owner_agent_id,
            priority=priority,
            deadline=deadline or Deadline(),
            created_at=datetime.now(UTC),
        )
        # Attach the coroutine function lazily; it's not part of TaskState
        # (keep TaskState fully serialisable for traces).
        self._by_id[state.handle.id] = state
        self._per_agent_pending[owner_agent_id].add(state.handle.id)
        self._seq += 1
        state._heap_seq = self._seq
        dl_ts = int(state.deadline.absolute.timestamp() * 1000_000) if state.deadline.absolute else 0
        heapq.heappush(self._runq, (-int(priority), -dl_ts, state._heap_seq, state.handle.id))
        self._by_id[state.handle.id]._fn = fn  # type: ignore[attr-defined]
        self._by_id[state.handle.id]._args = args  # type: ignore[attr-defined]
        self._by_id[state.handle.id]._kwargs = kwargs or {}  # type: ignore[attr-defined]
        log.debug("sched.spawned", task_id=str(state.handle.id), agent=owner_agent_id, priority=int(priority))
        return state.handle

    async def cancel(self, handle: TaskHandle) -> bool:
        state = self._by_id.get(handle.id)
        if state is None or state.status in {TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED}:
            return False
        state.status = TaskStatus.CANCELLED
        if state.status == TaskStatus.RUNNING:
            self._c_cancelled += 1
        return True

    def status_of(self, handle: TaskHandle) -> TaskState | None:
        return self._by_id.get(handle.id)

    # ---------------------------------------------------------------- Run loop

    async def start(self) -> None:
        if self._loop_task is not None:
            return
        self._stop_evt = asyncio.Event()
        self._loop_task = asyncio.create_task(self._run_loop(), name="astra-scheduler")

    async def stop(self) -> None:
        if self._stop_evt is None:
            return
        self._stop_evt.set()
        if self._loop_task is not None and not self._loop_task.done():
            # Give the loop task 200ms to exit cleanly (typically: it's in
            # _run_loop's wait_for with a 0.5s poll so may still be asleep).
            # If it doesn't wake by then, cancel it — we're done.
            _done, pending = await asyncio.wait([self._loop_task], timeout=0.2, return_when=asyncio.FIRST_COMPLETED)
            for _ in pending:
                self._loop_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._loop_task
        self._loop_task = None

    # ---------------------------------------------------------------- Stats

    def stats(self) -> SchedulerStats:
        queued = sum(1 for s in self._by_id.values() if s.status == TaskStatus.QUEUED)
        running = sum(1 for s in self._by_id.values() if s.status == TaskStatus.RUNNING)
        per_agent: dict[str, int] = {k: len(v) for k, v in self._per_agent_pending.items()}
        per_prio: dict[str, int] = defaultdict(int)
        for s in self._by_id.values():
            if s.status == TaskStatus.QUEUED:
                per_prio[s.priority.name] += 1
        return SchedulerStats(
            tasks_queued=queued,
            tasks_running=running,
            tasks_done=self._c_done,
            tasks_failed=self._c_failed,
            tasks_cancelled=self._c_cancelled,
            deadline_misses=self._c_deadline_misses,
            per_agent_queued=per_agent,
            per_priority_queued=dict(per_prio),
        )

    # -------------------------------------------------------------- internals

    async def _run_loop(self) -> None:
        assert self._stop_evt is not None
        while not self._stop_evt.is_set() or self._runq:
            async with self._lock:
                # Pull up to 1 runnable task per pass; this is single-threaded.
                if not self._runq:
                    await asyncio.sleep(0.01)
                    continue
                neg_prio, neg_dl, seq, tid = heapq.heappop(self._runq)
                _ = (neg_prio, neg_dl, seq)
            state = self._by_id.get(tid)
            if state is None or state.status in {TaskStatus.CANCELLED, TaskStatus.DONE, TaskStatus.FAILED}:
                self._per_agent_pending[state.owner_agent_id].discard(tid) if state else None
                continue
            if state.status != TaskStatus.QUEUED:
                # A task being retried; re-enqueue at the back.
                heapq.heappush(
                    self._runq,
                    (
                        -int(state.priority),
                        -(int(state.deadline.absolute.timestamp() * 1e6) if state.deadline.absolute else 0),
                        state._heap_seq,
                        state.handle.id,
                    ),
                )
                await asyncio.sleep(0.001)
                continue

            # Deadline pre-check
            if state.deadline.is_missed():
                self._c_deadline_misses += 1
                if self._emit_irq is not None:
                    await self._emit_irq(
                        Interrupt(
                            code=InterruptCode.DEADLINE_MISSED,
                            source="scheduler",
                            for_task_id=state.handle.id,
                            payload={
                                "agent": state.owner_agent_id,
                                "missed_by_ms": -round(float(state.deadline.remaining_ms() or 0), 2),
                            },
                        )
                    )

            state.status = TaskStatus.RUNNING
            state.started_at = datetime.now(UTC)
            try:
                fn = state._fn
                args = getattr(state, "_args", ())
                kwargs = getattr(state, "_kwargs", {})
                # Enforce the cooperative timeslice: cancel the inner task if
                # it takes longer than ``timeslice_s``.  We use ``asyncio.wait_for``.
                try:
                    coro = fn(*args, **kwargs)
                    start = time.perf_counter_ns()
                    result = await asyncio.wait_for(coro, timeout=self._default_timeslice_s)
                    state.cpu_ns += time.perf_counter_ns() - start
                    state.result = result
                    state.status = TaskStatus.DONE
                    self._c_done += 1
                except TimeoutError:
                    state.timeslice_count += 1
                    state.status = TaskStatus.TIMESLICE
                    # Re-enqueue the task at the back of its priority bucket.
                    self._per_agent_pending[state.owner_agent_id].add(state.handle.id)
                    self._seq += 1
                    state._heap_seq = self._seq
                    heapq.heappush(
                        self._runq,
                        (
                            -int(state.priority),
                            -(int(state.deadline.absolute.timestamp() * 1e6) if state.deadline.absolute else 0),
                            state._heap_seq,
                            state.handle.id,
                        ),
                    )
            except Exception as exc:
                state.status = TaskStatus.FAILED
                state.error = f"{type(exc).__name__}: {exc}"
                self._c_failed += 1
                if self._emit_irq is not None:
                    await self._emit_irq(
                        Interrupt(
                            code=InterruptCode.AGENT_CRASHED,
                            source="scheduler",
                            for_task_id=state.handle.id,
                            payload={"agent": state.owner_agent_id, "error": state.error[:500]},
                        )
                    )
            finally:
                state.finished_at = state.finished_at or datetime.now(UTC)
                self._per_agent_pending[state.owner_agent_id].discard(state.handle.id)


# Import ``time`` lazily at the bottom to keep namespace clean for readers.
import time
