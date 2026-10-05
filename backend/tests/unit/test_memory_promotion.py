"""
Unit tests for M2.4 six-tier PromotionController.

Covers:
  (a) 1000 T1 inserts → T2 promotion % + no T1 eviction starvation.
  (b) T4→T5 7-day TTL + cross-goal plan refs.
  (c) SHA-256 provenance chain: H(prev_state || event) linkage.
  (d) T1 size cap enforced on overflow.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import pytest

from noesis.memory.promotion import (
    TIER_GYAN,
    TIER_INDRIYA,
    TIER_SADHANA,
    TIER_SMRITI,
    TIER_YOJANA,
    GyānCorpus,
    PromotionController,
    PromotionThresholds,
    _entry_state_sha,
)
from noesis.memory.tiers import MemoryCitation, MemoryEntry


def _mk_entry(content: str, *, importance: float = 0.5, kind: str = "fact") -> MemoryEntry:
    return MemoryEntry(
        content=content,
        kind=kind,
        importance=importance,
        citations=[MemoryCitation(source="pytest://promo", snippet=content[:40])],
    )


def _access_n(pc: PromotionController, mid, n: int) -> None:
    """Simulate `n` accesses to a T1 entry (bump access_count + last_accessed)."""
    entry = pc.tiers[TIER_INDRIYA].get(mid)
    assert entry is not None
    for _ in range(n - 1):
        entry.access_count += 1
    entry.last_accessed_at = pc._now()
    pc.tiers[TIER_INDRIYA].put(entry)


# ---------------------------------------------------------------------------
# (a) 1000 T1 inserts → T2 promotion % + no T1 eviction starvation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_t1_1000_inserts_promotion_distribution_and_no_starvation():
    pc = PromotionController(thresholds=PromotionThresholds(t1_size_cap=1000))
    promoted_ids = []
    for i in range(1000):
        e = _mk_entry(f"memory entry index {i} of 1000 test corpus for promotion pipeline validation")
        mid = pc.insert_t1(e)
        if i % 2 == 0:
            _access_n(pc, mid, 4)
        promoted_ids.append(mid)

    stats = pc.promotion()
    t1_t2 = stats.count(f"{TIER_INDRIYA}->{TIER_SMRITI}")
    assert t1_t2 >= 200, f"Expected ≥200 T1→T2 promotions for 50% hot set, got {t1_t2}"
    pct = t1_t2 / 1000 * 100
    assert pct >= 20.0, f"T2 promotion rate {pct:.1f}% below 20% floor"

    t1_snap = pc._tier_snapshot(TIER_INDRIYA)
    cold_survivors = [mid for mid in promoted_ids[1::2] if mid in t1_snap]
    assert len(cold_survivors) >= 1, (
        "T1 starvation: zero cold entries remain in T1 after cap enforcement — "
        "LRU eviction is evicting *every* cold insert instead of oldest hot ones."
    )


# ---------------------------------------------------------------------------
# (b) T4→T5 TTL test: 7-day clock + cross-goal plan refs
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_t4_t5_ttl_seven_days_cross_goal():
    clock_0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    pc = PromotionController()
    pc.set_clock(clock_0)

    e = _mk_entry("cross-goal architecture pattern: event-sourced sagas for payment reconciliation")
    e.created_at = clock_0
    e.last_accessed_at = clock_0
    mid = e.memory_id

    pc.tiers[TIER_YOJANA].put(e)

    pc.add_plan_ref(mid, "goal_payments::plan_rollout")
    pc.add_plan_ref(mid, "goal_reconciliation::plan_monthly_close")

    pre = pc.promotion()
    assert pre.count(f"{TIER_YOJANA}->{TIER_SADHANA}") == 0, "T5 promotion before TTL must not happen"

    pc.advance_clock(timedelta(days=7, seconds=1))
    post = pc.promotion()
    assert post.count(f"{TIER_YOJANA}->{TIER_SADHANA}") == 1, "T4→T5 failed after 7-day TTL + cross-goal refs"
    assert pc.tiers[TIER_SADHANA].get(mid) is not None


# ---------------------------------------------------------------------------
# (c) SHA-256 provenance chain: H(prev_state + event) linkage
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_provenance_sha256_chain_linkage():
    from noesis.memory.promotion import PromotionStats

    corpus = GyānCorpus()
    corpus_fingerprint_text = "simhash overlap target phrase that will match promoted memory content exactly"
    corpus.ingest(text=corpus_fingerprint_text, label="gyān_seed")

    clock_0 = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    pc = PromotionController(gyan_corpus=corpus)
    pc.set_clock(clock_0)
    initial_tail = pc.provenance_tail_sha

    e = _mk_entry(corpus_fingerprint_text, importance=0.95)
    e.created_at = clock_0
    e.last_accessed_at = clock_0
    mid = e.memory_id

    pc.tiers[TIER_INDRIYA].put(e)
    _access_n(pc, mid, 4)

    stats1 = PromotionStats()
    pc._run_t1_t2(stats1)

    events_step1 = stats1.events
    assert len(events_step1) == 1, f"Expected exactly 1 T1→T2 event, got {len(events_step1)}"
    ev1 = events_step1[0]
    state_sha_1 = _entry_state_sha(e, TIER_INDRIYA)
    event_payload_1 = f"{TIER_INDRIYA}->{TIER_SMRITI}|{mid.hex}|{ev1.triggered_by}|{state_sha_1}|{initial_tail}"
    recomputed_ev1 = hashlib.sha256(event_payload_1.encode("utf-8")).hexdigest()
    assert recomputed_ev1 == ev1.event_sha, "Event 1 SHA mismatch (T1→T2 event_sha)"

    tail_after_1 = hashlib.sha256(f"{initial_tail}|{ev1.event_sha}".encode()).hexdigest()
    assert ev1.prev_sha == tail_after_1, "Event 1 .prev_sha tail mismatch"
    entry_t2 = pc.tiers[TIER_SMRITI].get(mid)
    assert entry_t2 is not None
    assert entry_t2.metadata["provenance_prev_sha"] == initial_tail, "Entry T2 provenance_prev_sha != initial_tail (chain broken after T1→T2)"
    assert entry_t2.metadata["provenance_event_sha"] == ev1.event_sha, "Entry T2 provenance_event_sha mismatch"

    field_names = MemoryEntry.__dataclass_fields__.keys()
    e2 = MemoryEntry(**{name: getattr(entry_t2, name) for name in field_names})
    e2.metadata = {k: v for k, v in entry_t2.metadata.items() if k not in {"provenance_prev_sha", "provenance_event_sha", "promoted_from"}}

    stats2 = PromotionStats()
    pc._run_t2_t3(stats2)
    assert len(stats2.events) == 1, f"Expected 1 T2→T3 event, got {len(stats2.events)}"
    ev2 = stats2.events[0]

    state_sha_2 = _entry_state_sha(e2, TIER_SMRITI)
    event_payload_2 = f"{TIER_SMRITI}->{TIER_GYAN}|{mid.hex}|{ev2.triggered_by}|{state_sha_2}|{tail_after_1}"
    recomputed_ev2 = hashlib.sha256(event_payload_2.encode("utf-8")).hexdigest()
    assert recomputed_ev2 == ev2.event_sha, "Event 2 SHA mismatch (T2→T3 event_sha)"

    tail_after_2 = hashlib.sha256(f"{tail_after_1}|{ev2.event_sha}".encode()).hexdigest()
    assert ev2.prev_sha == tail_after_2, "Event 2 .prev_sha tail mismatch"
    entry_t3 = pc.tiers[TIER_GYAN].get(mid)
    assert entry_t3 is not None
    assert entry_t3.metadata["provenance_prev_sha"] == tail_after_1, (
        "Entry T3 provenance_prev_sha != tail_after_1 — chain linkage between consecutive events broken"
    )
    assert entry_t3.metadata["provenance_event_sha"] == ev2.event_sha

    assert pc.provenance_tail_sha == tail_after_2, f"Controller tail drift: controller={pc.provenance_tail_sha[:16]} expected={tail_after_2[:16]}"


# ---------------------------------------------------------------------------
# (d) T1 size cap enforced
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_t1_size_cap_enforced():
    cap = 50
    pc = PromotionController(thresholds=PromotionThresholds(t1_size_cap=cap))
    overshoot = 175
    for i in range(cap + overshoot):
        e = _mk_entry(f"overflow probe entry {i}")
        pc.insert_t1(e)

    from noesis.memory.tiers import WorkingMemoryTier

    t1 = pc.tiers[TIER_INDRIYA]
    assert isinstance(t1, WorkingMemoryTier)
    with t1._lock:
        actual = len(t1._data)
    assert actual <= cap, f"T1 cap violated: {actual} > {cap}"

    probe = _mk_entry("probe after cap")
    probe_mid = pc.insert_t1(probe)
    with t1._lock:
        assert len(t1._data) <= cap
    assert t1.get(probe_mid) is not None, "Newest insert missing after cap — LRU pop wrong direction"
