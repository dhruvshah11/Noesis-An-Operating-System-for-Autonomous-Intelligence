"""Coverage-boosting tests for noesis.benchmarks.stats fallback branches."""

from __future__ import annotations

import json
from pathlib import Path

from noesis.benchmarks.stats import (
    _cli_aggregate_runner,
    _wilson_ci,
    aggregate_run_and_write_json,
)


def test_aggregate_run_and_write_json_empty_outdir(tmp_path: Path) -> None:
    """Empty outdir (no CSVs) → writes fallback tables_for_paper.json with defaults."""
    result = aggregate_run_and_write_json(tmp_path)
    tables_path = Path(result["tables_path"])
    assert tables_path.exists()

    payload = json.loads(tables_path.read_text(encoding="utf-8"))
    assert payload["se50"]["overall_pass_at_1"] == 0.0
    assert payload["se50"]["n_total"] == 0
    assert payload["humaneval_pass_at_1"] == 0.0
    assert payload["mbpp_pass_at_1"] == 0.0
    assert payload["signoff_avg_conf"] == 0.85
    assert "rows" in payload["ablation_table"]


def test_cli_aggregate_runner_no_csvs_writes_payload(tmp_path: Path) -> None:
    """_cli_aggregate_runner with all-None CSVs → still writes tables_for_paper.json."""
    out = _cli_aggregate_runner(
        se50_csv=None,
        humaneval_csv=None,
        mbpp_csv=None,
        outdir=str(tmp_path / "stats_out"),
    )
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "generated_at" in data
    assert "seed" in data


def test_wilson_ci_edge_cases() -> None:
    """Wilson CI: n<=0 → (0,0); standard 0.95 confidence returns valid range."""
    assert _wilson_ci(0.5, 0) == (0.0, 0.0)
    assert _wilson_ci(0.5, -5) == (0.0, 0.0)
    lo, hi = _wilson_ci(0.5, 100)
    assert 0.0 <= lo <= 0.5 <= hi <= 1.0
    assert hi > lo
