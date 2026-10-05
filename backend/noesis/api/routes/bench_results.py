"""Benchmark Results Hub endpoint — feeds frontend /benchmarks page LIVE data.

Fetches latest run results from docs/eval/w7_weekend_results OR latest in docs/eval/*
by mtime and returns BenchmarkResults JSON mirroring frontend Zod schema exactly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from noesis.api.deps import ok_envelope
from noesis.api.middleware.capability_gate import requires_capabilities
from noesis.config import get_settings
from noesis.logging import get_logger
from noesis.types import APIEnvelope

log = get_logger(__name__)
router = APIRouter(prefix="/api/bench", tags=["benchmarks"])


class BenchmarkRow(BaseModel):
    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    task_id: str = Field(min_length=1)
    category: str = "UNCATEGORIZED"
    difficulty: Literal["trivial", "easy", "medium", "hard", "expert"] = "medium"
    tristate: Literal["signoff", "reject", "replan"] = "replan"
    duration_ms: int = Field(ge=0, default=0)
    plan_sha: str = Field(min_length=1, default="sha-placeholder")
    kriyakari_conf: float = Field(ge=0.0, le=1.0, default=0.5)
    samples: int | None = Field(ge=0, default=None)


class CategoryPass1(BaseModel):
    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    category: str
    n_total: int = Field(ge=0)
    n_correct: int = Field(ge=0)
    pass_at_1: float = Field(ge=0.0, le=1.0)
    ci_low: float = Field(ge=0.0, le=1.0)
    ci_high: float = Field(ge=0.0, le=1.0)


class DifficultyRow(BaseModel):
    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    difficulty: str
    n_total: int = Field(ge=0)
    n_correct: int = Field(ge=0)
    pass_at_1: float = Field(ge=0.0, le=1.0)


class BenchmarkSummary(BaseModel):
    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    overall_pass_at_1: float = Field(ge=0.0, le=1.0)
    overall_ci_low: float = Field(ge=0.0, le=1.0)
    overall_ci_high: float = Field(ge=0.0, le=1.0)
    n_total: int = Field(ge=0)
    n_correct: int = Field(ge=0)
    per_category: list[CategoryPass1] = Field(default_factory=list)
    per_difficulty: list[DifficultyRow] = Field(default_factory=list)


class AblationTable(BaseModel):
    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    variant_keys: tuple[str, str, str]
    rows: list[dict[str, Any]] = Field(default_factory=list)
    notes: dict[str, Any] = Field(default_factory=dict)


class HumanEvalBucket(BaseModel):
    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    task_id: str = Field(min_length=1)
    codename: str = Field(min_length=1)
    pass_rate: float = Field(ge=0.0, le=1.0)
    n_samples: int = Field(ge=0)
    rank: int | None = Field(ge=0, default=None)


class MBPPBucket(BaseModel):
    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    bucket: str = Field(min_length=1)
    difficulty: int = Field(ge=1, le=5)
    pass_at_1: float = Field(ge=0.0, le=1.0)
    n_tasks: int = Field(ge=0)


class BenchmarkResults(BaseModel):
    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    se50: BenchmarkSummary
    se50_rows: list[BenchmarkRow] = Field(default_factory=list)
    humaneval_pass_at_1: float = Field(ge=0.0, le=1.0, default=0.0)
    humaneval_buckets: list[HumanEvalBucket] = Field(default_factory=list)
    mbpp_pass_at_1: float = Field(ge=0.0, le=1.0, default=0.0)
    mbpp_buckets: list[MBPPBucket] = Field(default_factory=list)
    ablation_table: AblationTable
    signoff_avg_conf: float = Field(ge=0.0, le=1.0, default=0.85)


def _demo_benchmark_results() -> BenchmarkResults:
    return BenchmarkResults(
        se50=BenchmarkSummary(
            overall_pass_at_1=0.40,
            overall_ci_low=0.28,
            overall_ci_high=0.53,
            n_total=50,
            n_correct=20,
            per_category=[
                CategoryPass1(
                    category="UNCATEGORIZED",
                    n_total=50,
                    n_correct=20,
                    pass_at_1=0.40,
                    ci_low=0.28,
                    ci_high=0.53,
                ),
            ],
            per_difficulty=[
                DifficultyRow(
                    difficulty="medium",
                    n_total=50,
                    n_correct=20,
                    pass_at_1=0.40,
                ),
            ],
        ),
        se50_rows=[],
        humaneval_pass_at_1=0.0,
        humaneval_buckets=[],
        mbpp_pass_at_1=0.0,
        mbpp_buckets=[],
        ablation_table=AblationTable(
            variant_keys=("baseline_nomem", "baseline_nomac", "full_noesis"),
            rows=[
                {
                    "metric": "OVERALL pass@1",
                    "baseline_nomem": 0.22,
                    "baseline_nomac": 0.31,
                    "full_noesis": 0.40,
                },
            ],
            notes={
                "demo_mode": True,
            },
        ),
        signoff_avg_conf=0.85,
    )


def _resolve_eval_root() -> Path:
    settings = get_settings()
    raw = settings.eval_root
    p = Path(raw)
    if not p.is_absolute():
        project_root = Path(__file__).resolve().parents[4]
        p = project_root / p
    return p


def _find_latest_tables_json(eval_root: Path) -> Path | None:
    candidates: list[Path] = []
    if eval_root.exists() and eval_root.is_dir():
        for p in eval_root.rglob("tables_for_paper.json"):
            if p.is_file():
                candidates.append(p)
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _auto_detect_result_dirs(eval_root: Path) -> tuple[Path | None, Path | None, Path | None, Path | None]:
    se50_csv: Path | None = None
    he_csv: Path | None = None
    mbpp_csv: Path | None = None
    outdir: Path | None = None

    if eval_root.exists() and eval_root.is_dir():
        for p in eval_root.rglob("se50_results.csv"):
            if p.is_file():
                if se50_csv is None or p.stat().st_mtime > se50_csv.stat().st_mtime:
                    se50_csv = p
        for p in eval_root.rglob("humaneval_pass1.csv"):
            if p.is_file():
                if he_csv is None or p.stat().st_mtime > he_csv.stat().st_mtime:
                    he_csv = p
        for p in eval_root.rglob("mbpp_results.csv"):
            if p.is_file():
                if mbpp_csv is None or p.stat().st_mtime > mbpp_csv.stat().st_mtime:
                    mbpp_csv = p

    if se50_csv is not None:
        outdir = se50_csv.parent
    elif he_csv is not None:
        outdir = he_csv.parent
    elif mbpp_csv is not None:
        outdir = mbpp_csv.parent
    else:
        outdir = eval_root / "stats_out"

    return se50_csv, he_csv, mbpp_csv, outdir


def _transform_tables_to_results(tables_data: dict[str, Any]) -> BenchmarkResults:
    se50_raw = tables_data.get("se50") or {
        "overall_pass_at_1": 0.0,
        "overall_ci_low": 0.0,
        "overall_ci_high": 0.0,
        "n_total": 0,
        "n_correct": 0,
        "per_category": [],
        "per_difficulty": [],
    }
    se50 = BenchmarkSummary(**se50_raw)

    se50_rows_raw = tables_data.get("se50_rows") or []
    se50_rows: list[BenchmarkRow] = []
    for r in se50_rows_raw:
        try:
            se50_rows.append(BenchmarkRow(**r))
        except Exception:
            pass

    humaneval_raw = tables_data.get("humaneval") or {}
    humaneval_pass_at_1 = float(humaneval_raw.get("pass_at_1", 0.0))
    humaneval_buckets_raw = tables_data.get("humaneval_buckets") or []
    humaneval_buckets: list[HumanEvalBucket] = []
    for b in humaneval_buckets_raw:
        try:
            humaneval_buckets.append(HumanEvalBucket(**b))
        except Exception:
            pass

    mbpp_raw = tables_data.get("mbpp") or {}
    mbpp_pass_at_1 = float(mbpp_raw.get("pass_at_1", 0.0))
    mbpp_buckets_raw = tables_data.get("mbpp_buckets") or []
    mbpp_buckets: list[MBPPBucket] = []
    for b in mbpp_buckets_raw:
        try:
            mbpp_buckets.append(MBPPBucket(**b))
        except Exception:
            pass

    ablation_raw = tables_data.get("ablation") or {
        "variant_keys": ("baseline_nomem", "baseline_nomac", "full_noesis"),
        "rows": [],
        "notes": {},
    }
    ablation_table = AblationTable(**ablation_raw)

    signoff_avg_conf = float(tables_data.get("signoff_avg_conf", 0.85))

    return BenchmarkResults(
        se50=se50,
        se50_rows=se50_rows,
        humaneval_pass_at_1=humaneval_pass_at_1,
        humaneval_buckets=humaneval_buckets,
        mbpp_pass_at_1=mbpp_pass_at_1,
        mbpp_buckets=mbpp_buckets,
        ablation_table=ablation_table,
        signoff_avg_conf=signoff_avg_conf,
    )


@router.get("/results", response_model=APIEnvelope[dict], dependencies=[Depends(requires_capabilities("bench.results.read"))])
async def get_bench_results(
    refresh: bool = Query(False, description="Recompute stats from CSV files on disk"),
) -> APIEnvelope[object]:
    """Fetch latest benchmark results for the frontend /benchmarks page.

    Returns **BenchmarkResults** matching the frontend Zod schema
    ``BenchmarkResultsSchema`` (schemas.ts:209).

    When real ``tables_for_paper.json`` exists under ``eval_root`` (default:
    ``docs/eval``) the latest copy (by mtime) is served.  Otherwise a
    demo-mode placeholder with ``overall_pass_at_1=0.40`` is returned and
    ``meta.demo`` = ``true`` is flagged in the envelope.

    Pass ``?refresh=true`` to regenerate ``tables_for_paper.json`` from any
    ``se50_results.csv`` / ``humaneval_pass1.csv`` / ``mbpp_results.csv``
    auto-discovered under ``eval_root`` before re-reading.

    See also the older sibling endpoint ``GET /llm/benchmark`` which measures
    live provider token-throughput and first-token latency
    (``noesis.api.routes.llm_benchmark.llm_benchmark``).
    """
    eval_root = _resolve_eval_root()

    source_note = "demo: no tables_for_paper.json found on disk, run run_w7_weekend.py to populate"

    if refresh:
        try:
            se50_csv, he_csv, mbpp_csv, outdir = _auto_detect_result_dirs(eval_root)
            if outdir is not None and (se50_csv or he_csv or mbpp_csv):
                from noesis.benchmarks.stats import aggregate_explicit_csvs_and_write_json

                aggregate_explicit_csvs_and_write_json(
                    se50_csv=str(se50_csv) if se50_csv else None,
                    humaneval_csv=str(he_csv) if he_csv else None,
                    mbpp_csv=str(mbpp_csv) if mbpp_csv else None,
                    outdir=str(outdir),
                )
        except Exception as exc:
            log.warning("bench.results.refresh_failed", error=str(exc)[:200])

    tables_path = _find_latest_tables_json(eval_root)

    if tables_path is None:
        demo = _demo_benchmark_results()
        return ok_envelope(
            demo.model_dump(mode="json"),
            meta={
                "demo": True,
                "source": source_note,
                "eval_root": str(eval_root),
            },
        )

    try:
        with tables_path.open(encoding="utf-8") as f:
            tables_data = json.load(f)
        results = _transform_tables_to_results(tables_data)
        return ok_envelope(
            results.model_dump(mode="json"),
            meta={
                "demo": False,
                "source": str(tables_path),
                "generated_at": tables_data.get("generated_at"),
            },
        )
    except Exception as exc:
        log.warning("bench.results.read_failed", error=str(exc)[:200], path=str(tables_path))
        demo = _demo_benchmark_results()
        return ok_envelope(
            demo.model_dump(mode="json"),
            meta={
                "demo": True,
                "source": f"{source_note} (parse error: {type(exc).__name__})",
                "eval_root": str(eval_root),
            },
        )
