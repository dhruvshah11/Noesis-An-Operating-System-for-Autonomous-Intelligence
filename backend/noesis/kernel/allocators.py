"""
Memory allocator — per-agent quotas on semantic memory.

Analogous to the Linux buddy allocator + cgroup memory limits:
  * Each agent is issued a :class:`QuotaEnvelope` with soft/hard caps per zone.
  * ``MemoryAllocator.malloc(agent_id, zone, tokens)`` returns a
    :class:`MemoryAllocation` with a lease.  The agent must ``free()`` it
    explicitly or the allocator will OOM-interrupt when the lease expires.
  * On hard-cap breach: raises :class:`OOMInterrupt` (the agent's handler
    decides: prune, compress, or crash).

We deliberately do NOT implement LRU or complex eviction here — that's the
Memory *Agent's* job, per the single-responsibility principle.  The
allocator only enforces quotas & emits IRQs.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from .interrupts import Interrupt, InterruptCode

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


class MemoryZone(StrEnum):
    """Semantic memory zones (8-tier system, §7)."""

    WORKING = "working"  # scratchpad, ~4k tokens window
    CONVERSATION = "conversation"  # current chat thread
    USER = "user"  # user-level long-term memory
    PROJECT = "project"  # project-level memories
    EPISODIC = "episodic"  # specific events, tagged with time
    SEMANTIC = "semantic"  # factual / world-knowledge
    INSTRUCTION = "instruction"  # user instructions / "constitutional"
    META = "meta"  # meta-memories (about memories)

    @property
    def default_soft_tokens(self) -> int:
        # Tiered quotas: working memory is small, semantic is vast.
        return {
            MemoryZone.WORKING: 16_000,
            MemoryZone.CONVERSATION: 256_000,
            MemoryZone.USER: 2_000_000,
            MemoryZone.PROJECT: 4_000_000,
            MemoryZone.EPISODIC: 16_000_000,
            MemoryZone.SEMANTIC: 128_000_000,
            MemoryZone.INSTRUCTION: 1_000_000,
            MemoryZone.META: 500_000,
        }[self]

    @property
    def default_hard_tokens(self) -> int:
        return int(self.default_soft_tokens * 1.5)


@dataclass(slots=True)
class QuotaEnvelope:
    """Per-agent/per-workspace token quotas."""

    agent_id: str
    soft_tokens_by_zone: dict[MemoryZone, int] = field(default_factory=dict)
    hard_tokens_by_zone: dict[MemoryZone, int] = field(default_factory=dict)

    def soft(self, zone: MemoryZone) -> int:
        return self.soft_tokens_by_zone.get(zone, zone.default_soft_tokens)

    def hard(self, zone: MemoryZone) -> int:
        return self.hard_tokens_by_zone.get(zone, zone.default_hard_tokens)


class OOMInterrupt(Interrupt):
    """Specialisation for OOMs (adds zone + current/requested/hard tokens)."""

    def __init__(
        self,
        *,
        agent_id: str,
        zone: MemoryZone,
        requested_tokens: int,
        current_tokens: int,
        hard_tokens: int,
    ) -> None:
        super().__init__(
            code=InterruptCode.OOM,
            source="allocator",
            payload={
                "agent_id": agent_id,
                "zone": zone.value,
                "requested_tokens": requested_tokens,
                "current_tokens": current_tokens,
                "hard_tokens": hard_tokens,
                "shortfall_tokens": max(0, current_tokens + requested_tokens - hard_tokens),
            },
        )


@dataclass(slots=True)
class MemoryAllocation:
    """A single lease on memory tokens."""

    id: UUID = field(default_factory=uuid4)
    agent_id: str = ""
    zone: MemoryZone = MemoryZone.WORKING
    tokens: int = 0
    expires_at: datetime | None = None
    freed: bool = False

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and datetime.now(UTC) >= self.expires_at


class MemoryAllocator:
    """Token-accounting memory allocator + OOM interrupt emitter."""

    def __init__(
        self,
        *,
        emit_irq: Callable[[Interrupt], Awaitable[None]] | None = None,
        default_lease_s: int = 3600,
    ) -> None:
        self._usage: dict[tuple[str, MemoryZone], int] = {}
        self._leases: dict[UUID, MemoryAllocation] = {}
        self._agent_quotas: dict[str, QuotaEnvelope] = {}
        self._emit_irq = emit_irq
        self._default_lease_s = default_lease_s
        self._gc_task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    # ------------------------------------------------------------------ API

    def register_agent(self, envelope: QuotaEnvelope) -> None:
        self._agent_quotas[envelope.agent_id] = envelope

    async def malloc(
        self,
        agent_id: str,
        zone: MemoryZone,
        tokens: int,
        *,
        lease_s: int | None = None,
        allow_over_soft: bool = True,
    ) -> MemoryAllocation:
        """Allocate ``tokens``, raising OOMInterrupt on hard-cap breach.

        Raises :class:`OOMInterrupt` synchronously — the caller is expected
        to deliver it to the agent via :class:`Kernel.irq_inbox`.
        """
        if tokens < 0:
            raise ValueError("tokens must be >= 0")
        quota = self._agent_quotas.get(agent_id) or QuotaEnvelope(agent_id=agent_id)
        current = self._usage.get((agent_id, zone), 0)
        hard = quota.hard(zone)
        if current + tokens > hard:
            oom = OOMInterrupt(
                agent_id=agent_id,
                zone=zone,
                requested_tokens=tokens,
                current_tokens=current,
                hard_tokens=hard,
            )
            if self._emit_irq is not None:
                await self._emit_irq(oom)
            raise oom
        if not allow_over_soft and current + tokens > quota.soft(zone):
            # Emit a warning-level quota_exceeded IRQ but don't block the alloc.
            if self._emit_irq is not None:
                await self._emit_irq(
                    Interrupt(
                        code=InterruptCode.QUOTA_EXCEEDED,
                        source="allocator",
                        payload={
                            "agent_id": agent_id,
                            "zone": zone.value,
                            "current_tokens": current + tokens,
                            "soft_tokens": quota.soft(zone),
                        },
                    )
                )
        self._usage[(agent_id, zone)] = current + tokens
        lease_s = lease_s or self._default_lease_s
        alloc = MemoryAllocation(
            agent_id=agent_id,
            zone=zone,
            tokens=tokens,
            expires_at=datetime.now(UTC) + timedelta(seconds=lease_s),
        )
        self._leases[alloc.id] = alloc
        return alloc

    def free(self, alloc: MemoryAllocation) -> int:
        if alloc.freed:
            return 0
        alloc.freed = True
        key = (alloc.agent_id, alloc.zone)
        self._usage[key] = max(0, self._usage.get(key, 0) - alloc.tokens)
        self._leases.pop(alloc.id, None)
        return alloc.tokens

    def usage_of(self, agent_id: str, zone: MemoryZone) -> int:
        return self._usage.get((agent_id, zone), 0)

    # ----------------------------------------------------- GC background loop

    async def start(self) -> None:
        if self._gc_task is None:
            self._stop.clear()
            self._gc_task = asyncio.create_task(self._gc_loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._gc_task is not None and not self._gc_task.done():
            _done, pending = await asyncio.wait([self._gc_task], timeout=0.2, return_when=asyncio.FIRST_COMPLETED)
            for _ in pending:
                self._gc_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._gc_task
        self._gc_task = None

    async def _gc_loop(self) -> None:
        while not self._stop.is_set():
            now = datetime.now(UTC)
            expired = [a for a in self._leases.values() if a.expires_at and not a.freed and a.expires_at <= now]
            for alloc in expired:
                self.free(alloc)
            await asyncio.sleep(max(1, self._default_lease_s // 4))
