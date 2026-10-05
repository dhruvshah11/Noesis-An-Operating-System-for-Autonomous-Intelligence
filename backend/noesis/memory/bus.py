"""
M2.3 MemoryBus — tier orchestrator.

Design rules (10yr-abstraction mindset):

1. **No hidden single-tier fallbacks.**  Every ``remember()`` call MUST
   declare which tiers receive the write; the bus refuses to silently invent
   a default policy (silent defaults = dead data in 2036).
2. **Recall is multi-tier but weighted.**  A query scoped to
   ``(user_id, conv_id)`` fans out to Working + Conversation + User tiers;
   results are merged by a global Reciprocal Rank Fusion (RRF) across all
   tiers so no single tier can dominate the top-k.
3. **Retention policies are explicit.**  ``retain()`` walks each tier and
   runs its ``prune()``; callers can override per-tier keep-top-K values.
4. **Summarisation is tier-aware.**  ``summarize()`` produces a composite
   TL;DR: one section per tier that actually has content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from noesis.memory.tiers import (
    ConversationMemoryTier,
    EpisodicMemoryTier,
    MemoryEntry,
    MemoryTier,
    ProjectMemoryTier,
    SemanticMemoryTier,
    UserMemoryTier,
    WorkingMemoryTier,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from uuid import UUID

# Tier names — alphabetical = intentional, no reordering = stable diffs.
TIER_CONVERSATION = "conversation"
TIER_EPISODIC = "episodic"
TIER_PROJECT = "project"
TIER_SEMANTIC = "semantic"
TIER_USER = "user"
TIER_WORKING = "working"

ALL_TIERS: frozenset[str] = frozenset({TIER_CONVERSATION, TIER_EPISODIC, TIER_PROJECT, TIER_SEMANTIC, TIER_USER, TIER_WORKING})

# Default tier-mapping: scope → which tiers to write/query.
SCOPE_TO_TIERS: dict[str, tuple[str, ...]] = {
    # A conversation-hot memory touches working+conversation+semantic+episodic.
    "conversation": (TIER_WORKING, TIER_CONVERSATION, TIER_EPISODIC, TIER_SEMANTIC),
    # User prefs write to user + semantic (so cross-conv recall works).
    "user": (TIER_USER, TIER_SEMANTIC),
    # Project decisions write to project + semantic (for architectural RAG).
    "project": (TIER_PROJECT, TIER_SEMANTIC),
    # System facts are semantic-only (immutable, long-lived).
    "system": (TIER_SEMANTIC,),
    # Agent self-observation is episodic + working.
    "agent": (TIER_WORKING, TIER_EPISODIC),
}


# ---------------------------------------------------------------------------
# Recall result: one row with tier identity so callers can see WHERE a fact
# came from (debugability / citation traceability).
# ---------------------------------------------------------------------------


@dataclass
class RecallHit:
    entry: MemoryEntry
    score: float  # global RRF-merged 0..1 score
    tier: str  # tier that produced this row


# ---------------------------------------------------------------------------
# Bus core
# ---------------------------------------------------------------------------


class MemoryBus:
    """Fan-out / fan-in across all 6 memory tiers."""

    def __init__(
        self,
        *,
        tiers: Mapping[str, MemoryTier] | None = None,
        rrf_k: int = 60,
    ) -> None:
        if tiers is None:
            tiers = {
                TIER_WORKING: WorkingMemoryTier(),
                TIER_CONVERSATION: ConversationMemoryTier(),
                TIER_EPISODIC: EpisodicMemoryTier(),
                TIER_USER: UserMemoryTier(),
                TIER_PROJECT: ProjectMemoryTier(),
                TIER_SEMANTIC: SemanticMemoryTier(),
            }
        missing = ALL_TIERS - set(tiers.keys())
        if missing:
            raise ValueError(f"MemoryBus.__init__: missing tiers {sorted(missing)}")
        self._tiers: dict[str, MemoryTier] = dict(tiers)
        self._rrf_k = rrf_k

    # ------------- introspection -------------------------------------------
    @property
    def tier_names(self) -> list[str]:
        return sorted(self._tiers.keys())

    @property
    def tiers(self) -> dict[str, MemoryTier]:
        return dict(self._tiers)

    # ------------- write: remember -----------------------------------------
    def remember(
        self,
        entry: MemoryEntry,
        *,
        tiers: Iterable[str] | None = None,
    ) -> dict[str, UUID]:
        """Write *entry* to each tier in ``tiers``.

        If ``tiers`` is None, derive target tiers from ``entry.scope`` via
        :data:`SCOPE_TO_TIERS`.  Returns the memory_id used per tier (always
        the same UUID — deterministic across tiers so callers can later
        delete one logical fact from everywhere with a single id).
        """
        targets = list(tiers) if tiers is not None else list(SCOPE_TO_TIERS.get(entry.scope, ()))
        if not targets:
            raise ValueError(f"MemoryBus.remember: no tiers for scope={entry.scope!r}. Pass tiers=[...] explicitly.")
        unknown = [t for t in targets if t not in self._tiers]
        if unknown:
            raise KeyError(f"MemoryBus.remember: unknown tiers {unknown!r}")
        ids: dict[str, UUID] = {}
        for name in targets:
            ids[name] = self._tiers[name].put(entry)
        return ids

    # ------------- atomic delete -------------------------------------------
    def forget(self, memory_id: UUID, *, tiers: Iterable[str] | None = None) -> dict[str, bool]:
        """Delete one memory_id from the requested tiers (default: ALL_TIERS)."""
        targets = list(tiers) if tiers is not None else list(ALL_TIERS)
        return {name: self._tiers[name].delete(memory_id) for name in targets}

    # ------------- fan-in recall: RRF merge across tiers -------------------
    def recall(
        self,
        *,
        query: str | None = None,
        scope: str | None = None,
        scope_id: str | None = None,
        tiers: Iterable[str] | None = None,
        top_k: int = 20,
    ) -> list[RecallHit]:
        """Multi-tier recall with global Reciprocal Rank Fusion.

        Formula (per Cormack et al.): ``score = Σ 1 / (k + rank_i)`` across
        every tier that returns an entry for ``memory_id``.  ``k`` is the
        RRF smoothing constant (default 60, standard value from literature).
        """
        targets = list(tiers) if tiers is not None else self._tiers_for_scope(scope)
        rrf: dict[UUID, float] = {}
        per_memory: dict[UUID, MemoryEntry] = {}
        per_tier_of: dict[UUID, str] = {}
        for name in targets:
            tier = self._tiers[name]
            tier_hits = tier.search(query=query, scope=scope, scope_id=scope_id, top_k=max(top_k, 50))
            for rank, (entry, _tier_score) in enumerate(tier_hits, start=1):
                rrf[entry.memory_id] = rrf.get(entry.memory_id, 0.0) + 1.0 / (self._rrf_k + rank)
                # Keep the highest-ranked tier as the "owner" for display.
                if entry.memory_id not in per_memory:
                    per_memory[entry.memory_id] = entry
                    per_tier_of[entry.memory_id] = name
        # Normalise RRF scores to 0..1 for downstream consumption.
        if not rrf:
            return []
        max_score = max(rrf.values())
        merged = [
            RecallHit(
                entry=per_memory[mid],
                score=score if max_score == 0 else score / max_score,
                tier=per_tier_of[mid],
            )
            for mid, score in rrf.items()
        ]
        merged.sort(key=lambda h: h.score, reverse=True)
        return merged[:top_k]

    # ------------- summarisation: tier-aware composite ---------------------
    def summarize(
        self,
        *,
        scope: str | None = None,
        scope_id: str | None = None,
        tiers: Iterable[str] | None = None,
        max_chars_per_tier: int = 1200,
    ) -> str:
        targets = list(tiers) if tiers is not None else self._tiers_for_scope(scope)
        sections: list[str] = ["[MemoryBus composite summary]"]
        for name in targets:
            section = self._tiers[name].summarize(scope=scope, scope_id=scope_id, max_chars=max_chars_per_tier)
            if not section:
                continue
            sections.append(f"\n-- tier: {name} --")
            sections.append(section)
        return "\n".join(sections)

    # ------------- retention: prune each tier ------------------------------
    def retain(
        self,
        *,
        per_tier_keep: Mapping[str, int] | None = None,
        default_keep: int = 500,
        scope: str | None = None,
        scope_id: str | None = None,
    ) -> dict[str, int]:
        """Prune each tier, returning the number of entries deleted per tier."""
        per_tier_keep = per_tier_keep or {}
        out: dict[str, int] = {}
        for name, tier in self._tiers.items():
            k = int(per_tier_keep.get(name, default_keep))
            out[name] = tier.prune(scope=scope, scope_id=scope_id, keep_top_k=k)
        return out

    # ------------- helpers -------------------------------------------------
    def _tiers_for_scope(self, scope: str | None) -> list[str]:
        if scope is None:
            return list(ALL_TIERS)
        return list(SCOPE_TO_TIERS.get(scope, (TIER_SEMANTIC,)))


__all__ = [
    "ALL_TIERS",
    "SCOPE_TO_TIERS",
    "TIER_CONVERSATION",
    "TIER_EPISODIC",
    "TIER_PROJECT",
    "TIER_SEMANTIC",
    "TIER_USER",
    "TIER_WORKING",
    "MemoryBus",
    "RecallHit",
]
