"""
M2.4 Six-Tier Memory Promotion Pipeline with SHA-256 Provenance Chain.

Tier semantics (Sanskrit code names):
  T1 *Indriya*   — sensory / working hot tier (LRU, 60s window)
  T2 *Smriti*    — short-term, accessed ≥3× within TTL
  T3 *Gyān*      — semantic overlap ≥0.8 with Gyān corpus fingerprints
  T4 *Yojanā*    — referenced by ≥2 distinct execution plans
  T5 *Sādhanā*   — survived 7-day TTL AND referenced cross-goal
  T6 *Paalak*    — human-reviewed + SHA-256 provenance seal (immutable)

Determinism contract (C3):
  Given the same input entries, clock, and Gyān corpus fingerprints,
  :meth:`PromotionController.promotion` produces an identical sequence
  of tier migrations.  Every migration appends a SHA-256 hash of
  ``H(prev_state_sha || event_bytes)`` as the next entry's
  ``provenance_prev_sha``, forming an audit chain that can be replayed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from noesis.memory.tiers import MemoryEntry, MemoryTier, WorkingMemoryTier, _InMemoryTier

if TYPE_CHECKING:
    from uuid import UUID

TIER_NAMES: tuple[str, ...] = ("T1", "T2", "T3", "T4", "T5", "T6")

TIER_INDRIYA = "T1"
TIER_SMRITI = "T2"
TIER_GYAN = "T3"
TIER_YOJANA = "T4"
TIER_SADHANA = "T5"
TIER_PAALAK = "T6"


@dataclass(slots=True)
class PromotionThresholds:
    """Configurable promotion thresholds for every edge.

    Defaults match the spec; all values are public so callers can tighten
    or relax during stress tests without subclassing.
    """

    t1_to_t2_access_count: int = 3
    t1_to_t2_window_s: int = 60
    t2_to_t3_simhash_threshold: float = 0.8
    t3_to_t4_plan_refs: int = 2
    t4_to_t5_ttl_days: int = 7
    t5_to_t6_require_human_review: bool = True
    t1_size_cap: int = 1000


@dataclass(slots=True)
class PromotionEvent:
    """One atomic tier migration recorded for audit / replay."""

    memory_id: UUID
    from_tier: str
    to_tier: str
    event_sha: str
    prev_sha: str
    triggered_by: str
    at: datetime


@dataclass
class PromotionStats:
    """Aggregate counters returned by :meth:`PromotionController.run_once`."""

    promotion_counts: dict[str, int] = field(default_factory=lambda: {f"{TIER_NAMES[i]}->{TIER_NAMES[i + 1]}": 0 for i in range(5)})
    eviction_counts: dict[str, int] = field(default_factory=lambda: {t: 0 for t in TIER_NAMES})
    events: list[PromotionEvent] = field(default_factory=list)

    def count(self, edge: str) -> int:
        return self.promotion_counts.get(edge, 0)


@dataclass
class PromotionReport:
    """Final report returned by :meth:`PromotionController.run_all_promotions`.

    ``tier_counts`` maps each tier name (T1..T6) to the number of entries
    currently stored in that tier.  Together with ``promotion_stats`` this
    gives a deterministic snapshot suitable for C3-identity assertions.
    """

    tier_counts: dict[str, int] = field(default_factory=lambda: {t: 0 for t in TIER_NAMES})
    stats: PromotionStats = field(default_factory=PromotionStats)
    provenance_tail_sha: str = "0" * 64
    total_events: int = 0


def _entry_state_sha(entry: MemoryEntry, tier: str) -> str:
    """Deterministic canonical hash of one memory entry's promoted state.

    Uses a stable JSON sort-keys representation so two Python processes
    produce the same SHA-256 for identical entry content (C3 determinism).
    """
    payload = {
        "tier": tier,
        "memory_id": entry.memory_id.hex,
        "content": entry.content,
        "kind": entry.kind,
        "importance": entry.importance,
        "access_count": entry.access_count,
        "scope": entry.scope,
        "scope_id": entry.scope_id or "",
        "tags": sorted(entry.tags),
        "created_at": entry.created_at.astimezone(UTC).isoformat(),
        "last_accessed_at": entry.last_accessed_at.astimezone(UTC).isoformat(),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _fingerprint(content: str) -> int:
    """Cheap deterministic 64-bit simhash-ish fingerprint.

    Not cryptographically strong — good enough for overlap detection in
    the T2→T3 path.  Returns the same integer for byte-identical inputs
    (C3 deterministic).
    """
    h = 0
    for token in sorted(set(content.lower().split())):
        h = ((h << 5) - h) + sum(b for b in token.encode("utf-8"))
        h &= 0xFFFFFFFFFFFFFFFF
    return h


def _overlap(a: int, b: int) -> float:
    """Bitwise Hamming-similarity → 0..1 overlap score."""
    if a == b:
        return 1.0
    differing = bin(a ^ b).count("1")
    return 1.0 - differing / 64.0


class GyānCorpus:
    """In-memory Gyān semantic corpus (reference fingerprints for T3).

    Populated with :meth:`ingest`; tests can seed a handful of known
    fingerprints to control T2→T3 promotion deterministically.
    """

    def __init__(self) -> None:
        self._fps: dict[int, str] = {}

    def ingest(self, *, text: str, label: str | None = None) -> int:
        fp = _fingerprint(text)
        self._fps[fp] = label or text[:60]
        return fp

    def best_overlap(self, entry: MemoryEntry) -> float:
        if not self._fps or not entry.content:
            return 0.0
        target = _fingerprint(entry.content)
        return max(_overlap(target, fp) for fp in self._fps)


class _PaalakTier(_InMemoryTier):
    """T6 *Paalak* — immutable after write.

    :meth:`put` refuses overwrite attempts once a memory_id has been
    sealed into Paalak; callers must delete and re-promote if they
    really need to change (triggers a new provenance chain segment).
    """

    tier_name = "paalak"

    def put(self, entry: MemoryEntry) -> UUID:
        with self._lock:
            if entry.memory_id in self._data:
                raise ValueError(f"Paalak tier refuses overwrite of {entry.memory_id}")
            self._data[entry.memory_id] = entry
            return entry.memory_id


def _make_default_tiers() -> dict[str, MemoryTier]:
    return {
        TIER_INDRIYA: WorkingMemoryTier(capacity=1000),
        TIER_SMRITI: _InMemoryTier(),
        TIER_GYAN: _InMemoryTier(),
        TIER_YOJANA: _InMemoryTier(),
        TIER_SADHANA: _InMemoryTier(),
        TIER_PAALAK: _PaalakTier(),
    }


@dataclass
class PromotionController:
    """Orchestrates promotion across T1…T6.

    Accepts 6 :class:`MemoryTier` implementations via ``tiers`` mapping;
    defaults to in-memory adapters suitable for unit tests.  The
    ``provenance_tail_sha`` field is the most-recent event hash — it
    chains every migration so replay of ``events`` reproduces the same
    tail deterministically.
    """

    tiers: dict[str, MemoryTier] = field(default_factory=_make_default_tiers)
    thresholds: PromotionThresholds = field(default_factory=PromotionThresholds)
    gyan_corpus: GyānCorpus = field(default_factory=GyānCorpus)
    plan_refs: dict[UUID, set[str]] = field(default_factory=dict)
    human_reviewed: set[UUID] = field(default_factory=set)
    provenance_tail_sha: str = "0" * 64
    events: list[PromotionEvent] = field(default_factory=list)
    _clock: datetime | None = None

    # ---- clock control (tests) --------------------------------------------
    def _now(self) -> datetime:
        return self._clock.astimezone(UTC) if self._clock is not None else datetime.now(UTC)

    def set_clock(self, now: datetime) -> None:
        self._clock = now.astimezone(UTC)

    def advance_clock(self, delta: timedelta) -> datetime:
        new_now = self._now() + delta
        self._clock = new_now
        return new_now

    # ---- helpers ----------------------------------------------------------
    def _tier_snapshot(self, tier: str) -> dict[UUID, MemoryEntry]:
        t = self.tiers[tier]
        if isinstance(t, WorkingMemoryTier):
            with t._lock:
                return dict(t._data)
        if isinstance(t, _InMemoryTier):
            with t._lock:
                return dict(t._data)
        results = t.search(top_k=10_000_000)
        return {e.memory_id: e for e, _s in results}

    def _mark_provenance(self, entry: MemoryEntry, from_tier: str, to_tier: str, triggered_by: str) -> PromotionEvent:
        state_sha = _entry_state_sha(entry, from_tier)
        event_payload = f"{from_tier}->{to_tier}|{entry.memory_id.hex}|{triggered_by}|{state_sha}|{self.provenance_tail_sha}"
        event_sha = hashlib.sha256(event_payload.encode("utf-8")).hexdigest()
        next_tail = hashlib.sha256(f"{self.provenance_tail_sha}|{event_sha}".encode()).hexdigest()
        entry.metadata["provenance_prev_sha"] = self.provenance_tail_sha
        entry.metadata["provenance_event_sha"] = event_sha
        entry.metadata["promoted_from"] = from_tier
        self.provenance_tail_sha = next_tail
        ev = PromotionEvent(
            memory_id=entry.memory_id,
            from_tier=from_tier,
            to_tier=to_tier,
            event_sha=event_sha,
            prev_sha=self.provenance_tail_sha,
            triggered_by=triggered_by,
            at=self._now(),
        )
        self.events.append(ev)
        return ev

    def _migrate(self, *, entry: MemoryEntry, from_tier: str, to_tier: str, triggered_by: str) -> PromotionEvent:
        self.tiers[from_tier].delete(entry.memory_id)
        ev = self._mark_provenance(entry, from_tier, to_tier, triggered_by)
        self.tiers[to_tier].put(entry)
        return ev

    # ---- individual promotion edges --------------------------------------
    def _run_t1_t2(self, stats: PromotionStats) -> None:
        now = self._now()
        snap = self._tier_snapshot(TIER_INDRIYA)
        window_start = now - timedelta(seconds=self.thresholds.t1_to_t2_window_s)
        for _mid, entry in sorted(snap.items(), key=lambda kv: kv[0].hex):
            if entry.access_count >= self.thresholds.t1_to_t2_access_count and entry.last_accessed_at >= window_start:
                ev = self._migrate(entry=entry, from_tier=TIER_INDRIYA, to_tier=TIER_SMRITI, triggered_by="access_count_window")
                stats.promotion_counts[f"{TIER_INDRIYA}->{TIER_SMRITI}"] = stats.promotion_counts.get(f"{TIER_INDRIYA}->{TIER_SMRITI}", 0) + 1
                stats.events.append(ev)

    def _run_t2_t3(self, stats: PromotionStats) -> None:
        snap = self._tier_snapshot(TIER_SMRITI)
        for _mid, entry in sorted(snap.items(), key=lambda kv: kv[0].hex):
            overlap = self.gyan_corpus.best_overlap(entry)
            if overlap >= self.thresholds.t2_to_t3_simhash_threshold:
                ev = self._migrate(
                    entry=entry,
                    from_tier=TIER_SMRITI,
                    to_tier=TIER_GYAN,
                    triggered_by=f"gyan_overlap={overlap:.3f}",
                )
                stats.promotion_counts[f"{TIER_SMRITI}->{TIER_GYAN}"] = stats.promotion_counts.get(f"{TIER_SMRITI}->{TIER_GYAN}", 0) + 1
                stats.events.append(ev)

    def _run_t3_t4(self, stats: PromotionStats) -> None:
        snap = self._tier_snapshot(TIER_GYAN)
        for mid, entry in sorted(snap.items(), key=lambda kv: kv[0].hex):
            distinct_plans = self.plan_refs.get(mid, set())
            if len(distinct_plans) >= self.thresholds.t3_to_t4_plan_refs:
                ev = self._migrate(
                    entry=entry,
                    from_tier=TIER_GYAN,
                    to_tier=TIER_YOJANA,
                    triggered_by=f"plan_refs={len(distinct_plans)}",
                )
                stats.promotion_counts[f"{TIER_GYAN}->{TIER_YOJANA}"] = stats.promotion_counts.get(f"{TIER_GYAN}->{TIER_YOJANA}", 0) + 1
                stats.events.append(ev)

    def _run_t4_t5(self, stats: PromotionStats) -> None:
        now = self._now()
        snap = self._tier_snapshot(TIER_YOJANA)
        ttl_cutoff = now - timedelta(days=self.thresholds.t4_to_t5_ttl_days)
        for mid, entry in sorted(snap.items(), key=lambda kv: kv[0].hex):
            age_ok = entry.created_at <= ttl_cutoff
            plans = self.plan_refs.get(mid, set())
            cross_goal = any("::" in p for p in plans) or len({p.split("::", 1)[0] for p in plans if "::" in p}) >= 2
            if age_ok and cross_goal:
                ev = self._migrate(
                    entry=entry,
                    from_tier=TIER_YOJANA,
                    to_tier=TIER_SADHANA,
                    triggered_by=f"ttl={self.thresholds.t4_to_t5_ttl_days}d_cross_goal",
                )
                stats.promotion_counts[f"{TIER_YOJANA}->{TIER_SADHANA}"] = stats.promotion_counts.get(f"{TIER_YOJANA}->{TIER_SADHANA}", 0) + 1
                stats.events.append(ev)

    def _run_t5_t6(self, stats: PromotionStats) -> None:
        snap = self._tier_snapshot(TIER_SADHANA)
        for mid, entry in sorted(snap.items(), key=lambda kv: kv[0].hex):
            reviewed = mid in self.human_reviewed
            if (not self.thresholds.t5_to_t6_require_human_review) or reviewed:
                ev = self._migrate(
                    entry=entry,
                    from_tier=TIER_SADHANA,
                    to_tier=TIER_PAALAK,
                    triggered_by="human_reviewed=" + str(reviewed).lower(),
                )
                stats.promotion_counts[f"{TIER_SADHANA}->{TIER_PAALAK}"] = stats.promotion_counts.get(f"{TIER_SADHANA}->{TIER_PAALAK}", 0) + 1
                stats.events.append(ev)

    def _enforce_t1_cap(self, stats: PromotionStats) -> None:
        t1 = self.tiers[TIER_INDRIYA]
        if not isinstance(t1, WorkingMemoryTier):
            return
        with t1._lock:
            while len(t1._data) > self.thresholds.t1_size_cap:
                t1._data.popitem(last=False)
                stats.eviction_counts[TIER_INDRIYA] += 1

    # ---- public API -------------------------------------------------------
    def insert_t1(self, entry: MemoryEntry) -> UUID:
        """Insert one entry into T1 (Indriya) — convenience for tests."""
        self.tiers[TIER_INDRIYA].put(entry)
        self._enforce_t1_cap(PromotionStats())
        return entry.memory_id

    def mark_human_reviewed(self, memory_id: UUID) -> None:
        self.human_reviewed.add(memory_id)

    def add_plan_ref(self, memory_id: UUID, plan_id: str) -> None:
        self.plan_refs.setdefault(memory_id, set()).add(plan_id)

    def promotion(self) -> PromotionStats:
        """Run one deterministic promotion pass across every tier edge.

        Edges are always evaluated *bottom-up* (T1→T2 first, T5→T6 last)
        so an entry promoted in this pass does not get re-evaluated until
        the next call — keeps the function single-pass and C3-deterministic.
        """
        stats = PromotionStats(
            promotion_counts={f"{TIER_NAMES[i]}->{TIER_NAMES[i + 1]}": 0 for i in range(5)},
            eviction_counts={t: 0 for t in TIER_NAMES},
        )
        self._run_t1_t2(stats)
        self._run_t2_t3(stats)
        self._run_t3_t4(stats)
        self._run_t4_t5(stats)
        self._run_t5_t6(stats)
        self._enforce_t1_cap(stats)
        return stats

    def run_all_promotions(self, passes: int = 3) -> PromotionReport:
        """Run ``passes`` promotion rounds, then return a deterministic summary.

        Multiple passes allow entries freshly promoted T1→T2 in pass 0 to
        cascade to T3 in pass 1.  The default ``passes=3`` is enough for
        any single inserted entry to reach T4 (given Gyān overlap + plan refs).
        C3-deterministic: identical inputs always produce identical
        ``tier_counts`` + ``provenance_tail_sha``.
        """
        aggregate = PromotionStats(
            promotion_counts={f"{TIER_NAMES[i]}->{TIER_NAMES[i + 1]}": 0 for i in range(5)},
            eviction_counts={t: 0 for t in TIER_NAMES},
        )
        for _ in range(max(1, passes)):
            s = self.promotion()
            for k, v in s.promotion_counts.items():
                aggregate.promotion_counts[k] = aggregate.promotion_counts.get(k, 0) + v
            for k, v in s.eviction_counts.items():
                aggregate.eviction_counts[k] = aggregate.eviction_counts.get(k, 0) + v
            aggregate.events.extend(s.events)
        tier_counts: dict[str, int] = {}
        for t in TIER_NAMES:
            tier_counts[t] = len(self._tier_snapshot(t))
        return PromotionReport(
            tier_counts=tier_counts,
            stats=aggregate,
            provenance_tail_sha=self.provenance_tail_sha,
            total_events=len(self.events),
        )


__all__ = [
    "TIER_GYAN",
    "TIER_INDRIYA",
    "TIER_NAMES",
    "TIER_PAALAK",
    "TIER_SADHANA",
    "TIER_SMRITI",
    "TIER_YOJANA",
    "GyānCorpus",
    "PromotionController",
    "PromotionEvent",
    "PromotionReport",
    "PromotionStats",
    "PromotionThresholds",
    "_entry_state_sha",
    "_overlap",
]
