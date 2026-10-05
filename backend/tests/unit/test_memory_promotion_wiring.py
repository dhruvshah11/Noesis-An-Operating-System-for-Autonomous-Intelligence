"""
Unit tests for MemoryAgent <-> PromotionController <-> PlannerAgent wiring.

Covers (C3 determinism manifest):
  (a) 5-step plan (seed=42) → T1 count equals 5 after end_of_run promotions.
  (b) Identical plan + seed executed 3× → promotion_report.tier_counts is
      bit-exact across all 3 runs (C3 identity property).
"""

from __future__ import annotations

from copy import deepcopy

import pytest

from noesis.agents.core import MemoryAgent, PlannerAgent, PlannerReport
from noesis.memory.promotion import TIER_INDRIYA, TIER_NAMES
from noesis.types import TaskStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_planner(goal: str, seed: int) -> tuple[PlannerReport, MemoryAgent]:
    """Run PlannerAgent once with (goal, seed); return report + MemoryAgent."""
    agent = PlannerAgent()
    state = {"goal": goal, "seed": seed, "deterministic": True}
    out = agent.run(state, None)  # type: ignore[arg-type]
    assert out["status"] == TaskStatus.SUCCESS.value
    report = PlannerReport.model_validate(out["report"])
    mem: MemoryAgent = out["memory_agent"]
    return report, mem


# ===========================================================================
# (a) 5-step plan (seed=42) → T1 count = 5 after end_of_run
# ===========================================================================


@pytest.mark.unit
def test_five_step_plan_seed42_t1_count_equals_five():
    """Deterministic plan (seed=42) yields T1 count = 5 after end_of_run.

    6-token goal → n_base=3 workers + 1 reflection = 4 plan steps; 1 plan entry
    plus 4 step entries = 5 sensory inserts into T1 Indriya.  All entries carry
    access_count=1 (below T1→T2 threshold of 3), so nothing promotes during
    the 3-pass cascade.  Result: T1 count stabilises at 5.
    """
    goal = "alpha beta gamma delta epsilon zeta"
    seed = 42

    report, mem = _run_planner(goal, seed)
    plan_steps = len(report.plan.steps)
    assert plan_steps == 4, (
        f"Expected exactly 4 plan steps (3 workers + 1 reflection) with 6-token goal + seed={seed}, "
        f"got {plan_steps}. Step indices: {[s.index for s in report.plan.steps]}"
    )

    promo = mem.end_of_run()
    t1_count = promo.tier_counts[TIER_INDRIYA]

    assert t1_count == 5, f"Expected T1 (Indriya) count = 5 after 3 promotion passes, got {t1_count}. Full tier_counts: {promo.tier_counts}"
    assert all(t in promo.tier_counts for t in TIER_NAMES), "All 6 tiers must be present in tier_counts"
    non_zero_tiers = [t for t, c in promo.tier_counts.items() if c > 0]
    assert len(non_zero_tiers) == 1 and non_zero_tiers[0] == TIER_INDRIYA, (
        f"Only T1 must be non-empty (access_count < 3 for everything); got {promo.tier_counts}"
    )
    assert promo.total_events == 0, "Zero promotion events expected when no entry meets thresholds"
    assert report.promotion_report is not None, "PlannerReport must carry promotion_report"
    assert report.promotion_report["tier_counts"][TIER_INDRIYA] == 5, "PlannerReport.promotion_report tier_counts[T1] must equal 5"
    assert "promotion_report" in report.plan.metadata, "ExecutionPlan metadata must contain promotion_report"


# ===========================================================================
# (b) C3 identity: same plan + seed × 3 runs → bit-exact tier_counts
# ===========================================================================


@pytest.mark.unit
def test_c3_identity_same_seed_three_runs_tier_counts_bit_exact():
    """C3 determinism: identical inputs must produce identical tier_counts."""
    goal = "Research cross-goal memory promotion pipeline deterministic cascade checks"
    seed = 42

    tier_counts_runs: list[dict[str, int]] = []
    sha_runs: list[str] = []
    events_runs: list[int] = []

    for _trial in range(3):
        _, mem = _run_planner(goal, seed)
        promo = mem.end_of_run()
        tier_counts_runs.append(deepcopy(promo.tier_counts))
        sha_runs.append(promo.provenance_tail_sha)
        events_runs.append(promo.total_events)

    for t in TIER_NAMES:
        values_across_runs = {tc[t] for tc in tier_counts_runs}
        assert len(values_across_runs) == 1, (
            f"C3 FAIL: tier {t} counts drift across runs: run0={tier_counts_runs[0][t]} run1={tier_counts_runs[1][t]} run2={tier_counts_runs[2][t]}"
        )

    assert len(set(sha_runs)) == 1, f"C3 FAIL: provenance_tail_sha not bit-exact across 3 runs: {sha_runs}"
    assert len(set(events_runs)) == 1, f"C3 FAIL: total_events not identical across runs: {events_runs}"

    baseline = tier_counts_runs[0]
    for i in range(1, 3):
        assert tier_counts_runs[i] == baseline, f"C3 FAIL: tier_counts dict not equal between run 0 and run {i}"
