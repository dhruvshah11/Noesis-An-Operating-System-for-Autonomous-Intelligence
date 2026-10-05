"""
Unit regression for W2-C3 determinism claim.

Goal: a 3-goal × 2-seed × 2-run smoke (12 runs total) must produce
reproducibility_score = 1.0 and per-goal unique_sha count = 2/runs × goals?
No — per (goal, seed) group unique_count == 1/2 == exactly deterministic,
and across different (goal, seed) we allow sha to differ (discriminability).

Runs fast: ~0.2 s.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))


@pytest.mark.slow
def test_determinism_manifest_smoke_score_is_identity() -> None:
    """Paper C3 smoke: N runs × same (goal,seed) ⇒ sha all equal."""
    from scripts.determinism_manifest import build_manifest

    goals = (
        "Produce a Rust CLI todo list with add/list/done flags",
        "Plan a 6-month 18-week capstone Gantt for Noesis",
    )
    seeds = (42, 7)
    runs = 2
    manifest = build_manifest(
        goals=goals,
        seeds=seeds,
        runs_per_pair=runs,
        workspace_prefix="utest",
        progress=False,
    )

    assert manifest.reproducibility_score == pytest.approx(1.0, rel=0, abs=0)
    assert manifest.runs_total == len(goals) * len(seeds) * runs
    assert manifest.goals_count == len(goals)
    assert manifest.seeds_count == len(seeds)

    for grp in manifest.per_group:
        assert grp["reproducibility_score"] == 1.0, grp
        assert grp["unique_sha256_count"] == 1, grp
        assert grp["identical_pairs"] == grp["total_pairs"] == runs * runs, grp

    # Discriminability: different goals or different seeds ⇒ different sha
    group_rows_by_sha: dict[str, int] = {}
    for grp in manifest.per_group:
        sha = next(row.sha256_json for row in manifest.csv_rows if row.goal_index == grp["goal_index"] and row.seed_index == grp["seed_index"])
        group_rows_by_sha[sha] = group_rows_by_sha.get(sha, 0) + 1
    assert len(group_rows_by_sha) == len(goals) * len(seeds), (
        f"Expected distinct sha per (goal,seed) for C3 discriminability; got collisions sha→count: {group_rows_by_sha}"
    )
    for count in group_rows_by_sha.values():
        assert count == 1
