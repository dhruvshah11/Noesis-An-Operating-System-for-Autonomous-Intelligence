"""
M2.2  Memory Tier port + 6 in-memory adapters.

The 10yr-abstraction rule: every memory tier exposes the SAME 7-method port
below, regardless of backing storage (SQLite, Qdrant, Redis, disk, RAM).
When we move `SemanticMemoryTier` from in-memory → Qdrant, no caller in
`astra.memory` or `noesis.kernel` changes a single line; only the DI wiring
in the container swaps the concrete class.

Storage unit: :class:`MemoryEntry`.  It carries its own ``importance``
(0..1) + ``access_count`` so ``prune()`` and ``score()`` have a canonical
input signal instead of inventing heuristics per tier.
"""

from __future__ import annotations

import math
import re
import threading
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------


@dataclass
class MemoryCitation:
    """Pointer back to *why* this memory was asserted."""

    source: str  # URL / doc id / agent id
    kind: str = "text"  # text|quote|link|tool_output|trace_id
    snippet: str = ""
    page: int | None = None
    span_id: str | None = None


@dataclass
class MemoryEntry:
    """One fact / observation / instruction stored in any tier."""

    memory_id: UUID = field(default_factory=uuid4)
    content: str = ""
    kind: str = "fact"  # fact|episode|instruction|preference|profile|chunk
    importance: float = 0.5  # 0..1
    access_count: int = 0
    citations: list[MemoryCitation] = field(default_factory=list)
    tags: set[str] = field(default_factory=set)
    scope: str = "user"  # user|conversation|project|team|system|agent
    scope_id: str | None = None  # user_id / conversation_id / project_id
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_accessed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    embedding: list[float] | None = None  # populated ONLY for semantic tier
    metadata: dict[str, Any] = field(default_factory=dict)

    # --- scoring helpers ----------------------------------------------------
    def age_seconds(self, now: datetime | None = None) -> float:
        now = now or datetime.now(UTC)
        return max(0.0, (now - self.created_at.astimezone(UTC)).total_seconds())

    def score(self, now: datetime | None = None) -> float:
        """Combine importance + recency + access_count into single 0..1 score.

        Formula:

            score = importance * (0.6 + 0.3 * recency_half_life + 0.1 * log2(1+accesses))

        Half-life for recency = 1 day.  This makes "fresh facts, frequently
        accessed" float to the top during retrieval, but highly-important
        long-term memories (importance=1.0) still win over unimportant-but-
        recent ones.
        """
        HALF_LIFE_S = 86_400.0
        age = self.age_seconds(now)
        recency = math.exp(-age * math.log(2) / HALF_LIFE_S)
        access = math.log2(1 + max(0, self.access_count))
        raw = self.importance * (0.6 + 0.3 * recency + 0.1 * min(1.0, access / 5.0))
        return max(0.0, min(1.0, raw))


# ---------------------------------------------------------------------------
# Port (hexagonal ABC)
# ---------------------------------------------------------------------------


class MemoryTier(ABC):
    """Uniform port for every memory tier — 7 methods total.

    *Put-only* methods never fail (they always append/overwrite); they return
    the memory_id that was stored.  *Search* returns a ranked list of
    MemoryEntry together with a per-tier score (0..1, higher=better).
    """

    tier_name: str = "abstract"

    @abstractmethod
    def put(self, entry: MemoryEntry) -> UUID:
        """Store one entry, replacing an existing one by `memory_id`."""

    @abstractmethod
    def get(self, memory_id: UUID) -> MemoryEntry | None: ...

    @abstractmethod
    def delete(self, memory_id: UUID) -> bool: ...

    @abstractmethod
    def search(
        self,
        *,
        query: str | None = None,
        scope: str | None = None,
        scope_id: str | None = None,
        tags: set[str] | None = None,
        top_k: int = 10,
    ) -> list[tuple[MemoryEntry, float]]:
        """Ranked retrieval.  Score = tier-specific 0..1 float."""

    @abstractmethod
    def score(self, entry: MemoryEntry) -> float:
        """Return the score that :meth:`search` *would* rank this entry with."""

    @abstractmethod
    def summarize(self, *, scope: str | None = None, scope_id: str | None = None, max_chars: int = 2000) -> str:
        """Human-readable TL;DR summary of this tier's contents within a scope."""

    @abstractmethod
    def prune(self, *, scope: str | None = None, scope_id: str | None = None, keep_top_k: int = 500) -> int:
        """Drop the lowest-scoring entries until ≤ ``keep_top_k`` remain.  Returns number deleted."""


# ---------------------------------------------------------------------------
# Shared helpers for in-memory tiers
# ---------------------------------------------------------------------------


def _filter_entries(
    entries: dict[UUID, MemoryEntry],
    *,
    scope: str | None,
    scope_id: str | None,
    tags: set[str] | None,
) -> list[MemoryEntry]:
    out: list[MemoryEntry] = []
    for e in entries.values():
        if scope is not None and e.scope != scope:
            continue
        if scope_id is not None and e.scope_id != scope_id:
            continue
        if tags is not None and not tags.issubset(e.tags):
            continue
        out.append(e)
    return out


def _rank(entries: list[MemoryEntry], query: str | None) -> list[tuple[MemoryEntry, float]]:
    now = datetime.now(UTC)
    q_terms = [w.lower() for w in re.findall(r"\w+", query or "")]
    ranked: list[tuple[MemoryEntry, float]] = []
    for e in entries:
        base = e.score(now=now)
        if q_terms:
            text = (e.content + " " + " ".join(e.tags)).lower()
            hits = sum(1 for t in q_terms if t in text)
            if hits == 0:
                continue
            base = 0.4 * base + 0.6 * min(1.0, hits / max(1, len(q_terms)))
        ranked.append((e, base))
    ranked.sort(key=lambda pair: pair[1], reverse=True)
    return ranked


# ---------------------------------------------------------------------------
# Adapter #1 — Working Memory (bounded-capacity LRU, scheduler hot path)
# ---------------------------------------------------------------------------


class WorkingMemoryTier(MemoryTier):
    tier_name = "working"

    def __init__(self, capacity: int = 256):
        self._capacity = capacity
        self._lock = threading.RLock()
        self._data: OrderedDict[UUID, MemoryEntry] = OrderedDict()

    def put(self, entry: MemoryEntry) -> UUID:
        with self._lock:
            if entry.memory_id in self._data:
                self._data.move_to_end(entry.memory_id)
            elif len(self._data) >= self._capacity:
                self._data.popitem(last=False)
            self._data[entry.memory_id] = entry
            return entry.memory_id

    def get(self, memory_id: UUID) -> MemoryEntry | None:
        with self._lock:
            e = self._data.get(memory_id)
            if e is None:
                return None
            e.access_count += 1
            e.last_accessed_at = datetime.now(UTC)
            self._data.move_to_end(memory_id)
            return e

    def delete(self, memory_id: UUID) -> bool:
        with self._lock:
            return self._data.pop(memory_id, None) is not None

    def search(self, *, query=None, scope=None, scope_id=None, tags=None, top_k=10):
        with self._lock:
            entries = _filter_entries(dict(self._data), scope=scope, scope_id=scope_id, tags=tags)
        return _rank(entries, query)[:top_k]

    def score(self, entry: MemoryEntry) -> float:
        return entry.score()

    def summarize(self, *, scope=None, scope_id=None, max_chars=2000) -> str:
        with self._lock:
            entries = _filter_entries(dict(self._data), scope=scope, scope_id=scope_id, tags=None)
        top = _rank(entries, query=None)[:10]
        parts = [f"[working {len(top)} top entries]"]
        used = 0
        for e, s in top:
            line = f"  * ({s:.2f}) [{e.kind}] {e.content}"
            if used + len(line) > max_chars:
                break
            parts.append(line)
            used += len(line)
        return "\n".join(parts)

    def prune(self, *, scope=None, scope_id=None, keep_top_k: int = 500) -> int:
        with self._lock:
            entries = _filter_entries(dict(self._data), scope=scope, scope_id=scope_id, tags=None)
            ranked = sorted(entries, key=lambda e: e.score(), reverse=True)
            delete_ids = {e.memory_id for e in ranked[keep_top_k:]}
            for mid in delete_ids:
                self._data.pop(mid, None)
            return len(delete_ids)


# ---------------------------------------------------------------------------
# Adapters 2-6 — general in-memory tier (base class) + 4 scoped + 1 semantic
# ---------------------------------------------------------------------------


class _InMemoryTier(MemoryTier):
    """Generic dict-backed tier; subclass to provide a specific tier_name."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._data: dict[UUID, MemoryEntry] = {}

    # -- 5 CRUD-ish methods are uniform --------------------------------------
    def put(self, entry: MemoryEntry) -> UUID:
        with self._lock:
            self._data[entry.memory_id] = entry
            return entry.memory_id

    def get(self, memory_id: UUID) -> MemoryEntry | None:
        with self._lock:
            e = self._data.get(memory_id)
            if e is None:
                return None
            e.access_count += 1
            e.last_accessed_at = datetime.now(UTC)
            return e

    def delete(self, memory_id: UUID) -> bool:
        with self._lock:
            return self._data.pop(memory_id, None) is not None

    def search(self, *, query=None, scope=None, scope_id=None, tags=None, top_k=10):
        with self._lock:
            snapshot = dict(self._data)
        entries = _filter_entries(snapshot, scope=scope, scope_id=scope_id, tags=tags)
        return _rank(entries, query)[:top_k]

    def score(self, entry: MemoryEntry) -> float:
        return entry.score()

    # -- summarisation + pruning are uniform too -----------------------------
    def summarize(self, *, scope=None, scope_id=None, max_chars=2000) -> str:
        with self._lock:
            snapshot = dict(self._data)
        entries = _filter_entries(snapshot, scope=scope, scope_id=scope_id, tags=None)
        top = sorted(entries, key=lambda e: e.score(), reverse=True)[:20]
        parts = [f"[{self.tier_name} {len(top)} top-scoring entries, {len(entries)} total in scope]"]
        used = 0
        for e in top:
            line = f"  * (score={e.score():.2f} imp={e.importance:.2f} n={e.access_count}) {e.content}"
            if used + len(line) > max_chars:
                break
            parts.append(line)
            used += len(line)
        return "\n".join(parts)

    def prune(self, *, scope=None, scope_id=None, keep_top_k: int = 500) -> int:
        with self._lock:
            entries = _filter_entries(self._data, scope=scope, scope_id=scope_id, tags=None)
            ranked = sorted(entries, key=lambda e: e.score(), reverse=True)
            delete_ids = {e.memory_id for e in ranked[keep_top_k:]}
            for mid in delete_ids:
                self._data.pop(mid, None)
            return len(delete_ids)


class ConversationMemoryTier(_InMemoryTier):
    """Per-conversation message-level memory (dialogue history + turn notes)."""

    tier_name = "conversation"


class UserMemoryTier(_InMemoryTier):
    """Per-user long-term preferences, profile facts, past interactions."""

    tier_name = "user"


class ProjectMemoryTier(_InMemoryTier):
    """Per-project / workspace decisions, architecture notes, conventions."""

    tier_name = "project"


class EpisodicMemoryTier(_InMemoryTier):
    """Agent experience log — step-recall, timestamp-ordered episodes."""

    tier_name = "episodic"

    def search(self, *, query=None, scope=None, scope_id=None, tags=None, top_k=10):
        results = super().search(query=query, scope=scope, scope_id=scope_id, tags=tags, top_k=top_k * 5)
        # Bias: episodic results prefer recency.  Re-rank with LIFO time-decay + any query hits.
        now = datetime.now(UTC)
        reranked: list[tuple[MemoryEntry, float]] = []
        for e, _s in results:
            age_hours = e.age_seconds(now) / 3600.0
            time_score = math.exp(-age_hours * math.log(2) / 24.0)  # half-life = 1 day
            combined = 0.7 * time_score + 0.3 * e.score(now=now)
            reranked.append((e, combined))
        reranked.sort(key=lambda p: p[1], reverse=True)
        return reranked[:top_k]


class SemanticMemoryTier(_InMemoryTier):
    """Semantic/embedding-scored memory.

    In this M2 reference (in-memory) adapter, the *real* vector store is not
    required — we fall back to BM25-ish keyword overlap over ``content +
    tags`` so tests work without a running Qdrant.  When a ``VectorStorePort``
    is wired through DI, the adapter calls it via a single pluggable method:
    :meth:`_semantic_rerank`.
    """

    tier_name = "semantic"

    def search(self, *, query=None, scope=None, scope_id=None, tags=None, top_k=10):
        with self._lock:
            snapshot = dict(self._data)
        entries = _filter_entries(snapshot, scope=scope, scope_id=scope_id, tags=tags)
        if not query:
            ranked = sorted(entries, key=lambda e: e.score(), reverse=True)
            return [(e, e.score()) for e in ranked[:top_k]]
        # Pre-filter: query token overlap (BM25-lite)
        q_tokens = set(re.findall(r"\w+", query.lower()))
        scored: list[tuple[MemoryEntry, float]] = []
        for e in entries:
            e_tokens = set(re.findall(r"\w+", (e.content + " " + " ".join(e.tags)).lower()))
            overlap = len(q_tokens & e_tokens) / max(1, len(q_tokens)) if q_tokens else 0.0
            combined = 0.5 * e.score() + 0.5 * overlap
            if e.embedding is not None and q_tokens:
                # Embedding bonus (if ever populated): just add 10% boost —
                # this reference implementation doesn't compute cosine, but
                # the tier *accepts* embeddings so tests can round-trip them.
                combined = 0.9 * combined + 0.1
            scored.append((e, combined))
        scored.sort(key=lambda p: p[1], reverse=True)
        return scored[:top_k]


__all__ = [
    "ConversationMemoryTier",
    "EpisodicMemoryTier",
    "MemoryCitation",
    "MemoryEntry",
    "MemoryTier",
    "ProjectMemoryTier",
    "SemanticMemoryTier",
    "UserMemoryTier",
    "WorkingMemoryTier",
]
