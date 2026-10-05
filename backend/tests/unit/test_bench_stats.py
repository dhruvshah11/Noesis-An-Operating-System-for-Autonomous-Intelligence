"""Unit tests for noesis.benchmarks.stats — MS8 McNemar + pass@k module."""

from __future__ import annotations

import json

import pytest

from noesis.benchmarks.stats import (
    AblationTables,
    BenchSummary,
    aggregate_se50_summary,
    generate_ablation_tables,
    mcnemar_pvalue,
    pass_at_k,
)


def test_pass_at_k_basic_edge_cases():
    """Test 1: Pass@1=0 for 0/20 correct, Pass@1=1.0 for 20/20 correct, Pass@5 > Pass@1."""
    assert pass_at_k(20, 0, 1) == 0.0
    assert pass_at_k(20, 20, 1) == 1.0

    n, c = 20, 12
    p1 = pass_at_k(n, c, 1)
    p5 = pass_at_k(n, c, 5)
    assert p5 > p1, f"pass@5 ({p5}) should be > pass@1 ({p1})"
    assert 0.0 <= p1 <= 1.0
    assert 0.0 <= p5 <= 1.0


def test_mcnemar_extreme_cases():
    """Test 2: McNemar (0, 0) → 1.0 p; (50, 0) → p < 1e-6."""
    p_eq, warn_eq = mcnemar_pvalue(0, 0)
    assert p_eq == 1.0
    assert warn_eq == ""

    p_extreme, warn_ext_unused = mcnemar_pvalue(50, 0)
    del warn_ext_unused
    assert p_extreme < 1e-6, f"expected p<1e-6, got {p_extreme}"
    assert 0.0 <= p_extreme <= 1.0

    p_balanced, warn_bal_unused = mcnemar_pvalue(10, 10)
    del warn_bal_unused
    assert p_balanced > 0.5, f"balanced discordants should have high p, got {p_balanced}"


def test_bootstrap_ci_midpoint_near_half():
    """Test 3: Bootstrap CI for 20 successes out of 40 → width > 0 and midpoint ≈ 0.5."""
    flags = [True] * 20 + [False] * 20
    rows = [{"category": "cat", "difficulty": "med", "tristate": "signoff" if f else "replan"} for f in flags]
    summary = aggregate_se50_summary(rows, bootstrap_seed=7)

    assert isinstance(summary, BenchSummary)
    assert summary.n_total == 40
    assert summary.n_correct == 20

    width = summary.overall_ci_high - summary.overall_ci_low
    assert width > 0.0, f"CI width should be > 0, got {width}"

    midpoint = (summary.overall_ci_low + summary.overall_ci_high) / 2.0
    assert 0.35 <= midpoint <= 0.65, f"midpoint {midpoint} should be near 0.5"

    assert 0.0 <= summary.overall_pass_at_1 <= 1.0


def test_se50_aggregation_smoke():
    """Test 4: SE50 aggregation with 5 rows (2 SIGNOFF, 3 REPLAN) → pass@1=0.4."""
    rows = [
        {"task_id": "T01", "category": "code_gen", "difficulty": "easy", "tristate": "signoff", "duration_ms": 1200, "plan_sha": "a1"},
        {"task_id": "T02", "category": "code_gen", "difficulty": "easy", "tristate": "signoff", "duration_ms": 1500, "plan_sha": "b2"},
        {"task_id": "T03", "category": "refactor", "difficulty": "medium", "tristate": "replan", "duration_ms": 2000, "plan_sha": "c3"},
        {"task_id": "T04", "category": "refactor", "difficulty": "medium", "tristate": "replan", "duration_ms": 2500, "plan_sha": "d4"},
        {"task_id": "T05", "category": "testing", "difficulty": "hard", "tristate": "replan", "duration_ms": 3000, "plan_sha": "e5"},
    ]
    summary = aggregate_se50_summary(rows, bootstrap_seed=42)

    assert summary.n_total == 5
    assert summary.n_correct == 2
    assert abs(summary.overall_pass_at_1 - 0.4) < 1e-9

    cats = {pc.category: pc for pc in summary.per_category}
    assert "code_gen" in cats
    assert cats["code_gen"].pass_at_1 == 1.0
    assert "refactor" in cats
    assert cats["refactor"].pass_at_1 == 0.0

    diffs = {dr.difficulty: dr for dr in summary.per_difficulty}
    assert "easy" in diffs
    assert diffs["easy"].pass_at_1 == 1.0


def test_ablation_tables_smoke():
    """Test 5: Ablation tables produces JSON dump with 3 expected column keys."""
    results_a = {
        "overall_pass_at_1": 0.22,
        "per_category": [
            {"category": "code_gen", "pass_at_1": 0.25},
            {"category": "refactor", "pass_at_1": 0.20},
        ],
    }
    results_b = {
        "overall_pass_at_1": 0.31,
        "per_category": [
            {"category": "code_gen", "pass_at_1": 0.34},
            {"category": "refactor", "pass_at_1": 0.28},
        ],
    }
    results_c = {
        "overall_pass_at_1": 0.40,
        "per_category": [
            {"category": "code_gen", "pass_at_1": 0.44},
            {"category": "refactor", "pass_at_1": 0.36},
        ],
    }
    ablation = generate_ablation_tables(results_a, results_b, results_c)

    assert isinstance(ablation, AblationTables)
    assert ablation.variant_keys == ("baseline_nomem", "baseline_nomac", "full_noesis")
    assert len(ablation.rows) >= 3  # OVERALL + at least 2 categories

    dump = json.loads(ablation.model_dump_json())
    assert "variant_keys" in dump
    assert dump["variant_keys"] == ["baseline_nomem", "baseline_nomac", "full_noesis"]
    assert "rows" in dump
    for row in dump["rows"]:
        for k in ("baseline_nomem", "baseline_nomac", "full_noesis"):
            assert k in row, f"row missing key {k}: {row}"

    assert "c1_gain_full_vs_nomem_pp" in ablation.notes


def test_pass_at_k_validates_inputs():
    """Extra validation test: pass_at_k rejects bad args."""
    with pytest.raises(ValueError):
        pass_at_k(10, -1, 1)
    with pytest.raises(ValueError):
        pass_at_k(10, 11, 1)
    with pytest.raises(ValueError):
        pass_at_k(10, 5, 0)
    with pytest.raises(ValueError):
        pass_at_k(10, 5, 11)


def test_mcnemar_accepts_symmetry():
    """Symmetric (b=c) with large N → p → 1.0; p grows monotonically with N."""
    results = []
    for b_val in (5, 10, 50, 200, 5000):
        p, _ = mcnemar_pvalue(b_val, b_val)
        results.append((b_val, p))
    for i in range(1, len(results)):
        prev_p = results[i - 1][1]
        cur_p = results[i][1]
        assert cur_p >= prev_p - 1e-9, f"p should be non-decreasing as N grows: {results[i - 1]} -> {results[i]}"
    assert results[-1][1] > 0.95, f"large symmetric b=c should give p→1.0, got {results[-1]}"
    for _, p in results:
        assert 0.0 <= p <= 1.0


def test_aggregate_accepts_fallback_keys():
    """aggregate_se50_summary should tolerate 'decision' or 'correct' fallback keys."""
    rows = [
        {"category": "a", "difficulty": "easy", "decision": "signoff"},
        {"category": "a", "difficulty": "easy", "correct": True},
        {"category": "a", "difficulty": "easy", "correct": 1},
        {"category": "a", "difficulty": "easy", "tristate": "reject"},
    ]
    s = aggregate_se50_summary(rows, bootstrap_seed=1)
    assert s.n_correct == 3
    assert s.n_total == 4
