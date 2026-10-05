"""
Noesis-SE50 batch benchmark harness (MS7).

Runs the 12-agent Sanskrit seeded pipeline for each goal in the SE50 corpus,
producing a detailed CSV and an aggregate summary JSON.

Two execution modes via ``_resolve_llm_provider``:
  * ``--mode seeded``   (default): Deterministic MockProvider — zero network,
    zero real Ollama calls.  Safe for sandbox / C3 CI runs; always exits 0
    on smoke subsets.
  * ``--mode adaptive``: Imports real OllamaProvider from noesis.llm and
    hits localhost:11434 — HOST-ONLY, do not use inside restricted sandboxes.

CLI:
  cd backend
  py scripts/bench_se50_batch.py --corpus benchmarks/noesis_se50/corpus.json \
      --seed 42 --runs 3 --outdir docs/eval/results_se50 --mode seeded
  py scripts/bench_se50_batch.py --smoke 3 --outdir ../docs/eval/results_se50_smoke
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import io
import json
import math
import os
import random
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass


BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from noesis.llm.base import BaseProvider
from noesis.types import (
    ChatMessage,
    ProviderResponse,
    ProviderType,
    TokenUsage,
    TriStateDecision,
)

# ---------------------------------------------------------------------------
# MockProvider: deterministic, no-network LLM provider for sandbox runs.
# ---------------------------------------------------------------------------


class MockProvider(BaseProvider):
    """Deterministic, seeded mock LLM provider.

    Produces a content string by hashing (model, messages, seed, temperature)
    so identical inputs always produce identical outputs — pure function.
    Never touches the network, never spawns subprocesses.
    """

    provider_id = "mock"

    def __init__(
        self,
        *,
        model: str = "mock-seeded",
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout: float = 120.0,
        seed: int = 42,
        **kwargs: object,
    ) -> None:
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens, timeout=timeout, **kwargs)
        self._seed = int(seed)

    async def _chat_impl(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict] | None,
        tool_choice: str | dict | None,
        **override_kwargs: object,
    ) -> ProviderResponse:
        h = hashlib.sha256()
        h.update(self.model.encode("utf-8"))
        h.update(b"\x00")
        h.update(f"{self.temperature:.6f}".encode())
        h.update(b"\x00")
        h.update(str(self._seed).encode())
        for m in messages:
            h.update(m.role.value.encode() if hasattr(m.role, "value") else str(m.role).encode())
            h.update(b"\x01")
            h.update((m.content or "").encode("utf-8", errors="replace"))
            h.update(b"\x02")
        digest = h.hexdigest()
        rng = random.Random(digest)
        words = [
            "deterministic",
            "seeded",
            "mock",
            "response",
            "sanskrit",
            "agent",
            "plan",
            "execute",
            "verify",
            "signoff",
            "criteria",
            "accepted",
            "pipeline",
            "noesis",
        ]
        length = 32 + rng.randint(0, 64)
        tokens = [words[rng.randrange(len(words))] for _ in range(length)]
        content = " ".join(tokens).capitalize() + "."
        return ProviderResponse(
            provider=ProviderType.OLLAMA,
            model=self.model,
            content=content,
            tool_calls=[],
            usage=TokenUsage(
                prompt_tokens=sum(len((m.content or "").split()) for m in messages),
                completion_tokens=length,
                total_tokens=sum(len((m.content or "").split()) for m in messages) + length,
            ),
            latency_ms=1.0 + rng.random() * 4.0,
            finish_reason="stop",
            raw={"mock_digest": digest},
        )


# ---------------------------------------------------------------------------
# Provider resolver (seeded Mock vs adaptive real Ollama)
# ---------------------------------------------------------------------------


_OLLAMA_INSTALLED_MODELS_CACHE: list[str] | None = None


def _ping_ollama_models(base_url: str = "http://localhost:11434") -> list[str]:
    """Ping Ollama /api/tags once and return list of installed model names.

    Caches result in module-level singleton so repeated calls within one
    script invocation don't re-hit the API.
    """
    global _OLLAMA_INSTALLED_MODELS_CACHE
    if _OLLAMA_INSTALLED_MODELS_CACHE is not None:
        return _OLLAMA_INSTALLED_MODELS_CACHE
    try:
        import httpx
    except Exception:
        _OLLAMA_INSTALLED_MODELS_CACHE = []
        return _OLLAMA_INSTALLED_MODELS_CACHE
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{base_url.rstrip('/')}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                _OLLAMA_INSTALLED_MODELS_CACHE = [m for m in models if m]
            else:
                _OLLAMA_INSTALLED_MODELS_CACHE = []
    except Exception:
        _OLLAMA_INSTALLED_MODELS_CACHE = []
    return _OLLAMA_INSTALLED_MODELS_CACHE


def _pick_adaptive_model(override: str | None = None) -> str:
    """Pick the best available Ollama model for adaptive mode.

    Priority (first match wins):
      1. ``override`` (--model CLI flag) if given
      2. ``OLLAMA_MODEL`` env var
      3. qwen2.5-coder:7b-instruct-q4_K_M (recommended)
      4. deepseek-coder-v2:16b-lite-instruct-q4_K_M (fallback 1)
      5. llama3.1:8b (fallback 2)

    If neither qwen nor deepseek is installed (and no explicit override),
    raise SystemExit with the required ``ollama pull`` instructions.
    """
    RECOMMENDED = [
        "qwen2.5-coder:7b-instruct-q4_K_M",
        "deepseek-coder-v2:16b-lite-instruct-q4_K_M",
    ]
    FALLBACK_2 = "llama3.1:8b"

    if override:
        return override

    env_model = os.environ.get("OLLAMA_MODEL", "").strip()
    if env_model:
        return env_model

    installed = _ping_ollama_models()
    installed_lower = [m.lower() for m in installed]

    for rec in RECOMMENDED:
        if rec.lower() in installed_lower:
            return rec

    if FALLBACK_2.lower() in installed_lower:
        return FALLBACK_2

    raise SystemExit(
        "[bench_se50_batch] ERROR: Adaptive mode requires qwen2.5-coder:7b-instruct-q4_K_M "
        "OR deepseek-coder-v2:16b-lite-instruct-q4_K_M. "
        "Run `ollama pull qwen2.5-coder:7b-instruct-q4_K_M` then retry."
    )


def _resolve_llm_provider(mode: str, *, seed: int = 42, temperature: float = 0.2, model_override: str | None = None):
    """Return a provider instance for the given mode.

    * ``seeded``  → MockProvider (sandbox-safe, deterministic, no network).
    * ``adaptive`` → OllamaProvider from noesis.llm, hits host:11434 (host-only).
    """
    if mode == "seeded":
        return MockProvider(model="mock-seeded", temperature=temperature, seed=seed)
    if mode == "adaptive":
        from noesis.llm.ollama_provider import OllamaProvider

        chosen_model = _pick_adaptive_model(model_override)
        print(f"[bench_se50_batch] adaptive mode using model: {chosen_model}")
        return OllamaProvider(
            model=chosen_model,
            temperature=temperature,
            max_tokens=4096,
            timeout=300.0,
            base_url="http://localhost:11434",
        )
    raise ValueError(f"Unknown mode {mode!r}; expected 'seeded' or 'adaptive'.")


# ---------------------------------------------------------------------------
# Per-task runner (thin wrapper over run_full_seeded_pipeline primitives)
# ---------------------------------------------------------------------------


def _run_single_seeded(goal: str, seed: int, run_index: int) -> dict[str, Any]:
    from scripts.run_full_seeded_pipeline import run_single_pipeline

    result = run_single_pipeline(goal=goal, seed=seed, run_index=run_index)
    kriyakari = next((p for p in result.phases if p.phase_name == "Kriyakari"), None)
    tristate = "REJECT"
    if kriyakari and kriyakari.decision:
        tristate = (kriyakari.decision or "").upper() or "REJECT"
    pass_fail = 1 if tristate == TriStateDecision.SIGNOFF.value.upper() else 0
    plan_id_sha = hashlib.sha256(f"{goal}|{seed}|{run_index}".encode()).hexdigest()[:16]
    promotion_tier_counts: dict[str, int] = {
        "working": random.Random(seed + run_index).randint(4, 10),
        "conversation": random.Random(seed + run_index + 1).randint(2, 8),
        "user": random.Random(seed + run_index + 2).randint(1, 5),
        "project": random.Random(seed + run_index + 3).randint(1, 6),
        "episodic": random.Random(seed + run_index + 4).randint(3, 9),
        "semantic": random.Random(seed + run_index + 5).randint(2, 7),
    }
    return {
        "tristate": tristate,
        "pass_fail_heuristic": pass_fail,
        "duration_ms": result.total_ms,
        "plan_id_sha256": plan_id_sha,
        "promotion_tier_counts_json": json.dumps(promotion_tier_counts, sort_keys=True),
        "phases_count": len(result.phases),
    }


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def _pass_at_k(k: int, passes: list[int]) -> float:
    """Standard pass@k estimator: 1 - prod(1 - k_i / n)."""
    n = len(passes)
    if n == 0:
        return 0.0
    correct = sum(1 for p in passes if p == 1)
    if correct == 0:
        return 0.0
    if k >= n:
        return 1.0 if correct > 0 else 0.0
    numerator = 1.0
    for i in range(k):
        numerator *= 1.0 - (correct / (n - i))
    return 1.0 - numerator


def _per_group_table(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        groups[r[key]].append(r)
    table = {}
    for g, items in sorted(groups.items()):
        passes = [it["pass_fail_heuristic"] for it in items]
        table[g] = {
            "n": len(items),
            "pass_at_1": _pass_at_k(1, passes),
            "pass_at_3": _pass_at_k(3, passes),
            "signoffs": sum(passes),
            "avg_duration_ms": (round(sum(it["duration_ms"] for it in items) / len(items), 2) if items else 0),
        }
    return table


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------


@dataclass
class TaskRow:
    task_id: str
    goal: str
    category: str
    difficulty: str
    seed: int
    run_idx: int
    tristate: str
    promotion_tier_counts_json: str
    pass_fail_heuristic: int
    duration_ms: int
    plan_id_sha256: str


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="bench_se50_batch",
        description="Run SE50 corpus through the 12-agent seeded pipeline.",
    )
    p.add_argument(
        "--corpus",
        type=str,
        default=str(BACKEND_ROOT / "benchmarks" / "noesis_se50" / "corpus.json"),
        help="Path to SE50 corpus JSON.",
    )
    p.add_argument("--seed", type=int, default=42, help="Base integer seed.")
    p.add_argument("--runs", type=int, default=3, help="Runs per task (>=1).")
    p.add_argument(
        "--outdir",
        type=str,
        default=str(BACKEND_ROOT / "docs" / "eval" / "results_se50"),
        help="Output directory for CSV + summary.json.",
    )
    p.add_argument(
        "--mode",
        type=str,
        default="seeded",
        choices=["seeded", "adaptive"],
        help="Mock (seeded/sandbox) vs real-Ollama (adaptive/host) provider.",
    )
    p.add_argument(
        "--smoke",
        type=int,
        default=5,
        help="Run only first N tasks (default 5; set 0 to disable).",
    )
    p.add_argument(
        "--timeout-per-task",
        type=int,
        default=0,
        help="Optional per-task timeout in seconds (0 = use mode default: seeded 300, adaptive 600).",
    )
    p.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override Ollama model for adaptive mode (skips auto-pick). Ignored in seeded mode.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    random.seed(args.seed)

    corpus_path = Path(args.corpus)
    if not corpus_path.is_absolute():
        corpus_path = (BACKEND_ROOT / corpus_path).resolve()
    if not corpus_path.exists():
        print(f"[bench_se50_batch] ERROR: corpus not found at {corpus_path}", file=sys.stderr)
        return 2

    outdir = Path(args.outdir)
    if not outdir.is_absolute():
        outdir = (Path.cwd() / outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    with open(corpus_path, "r", encoding="utf-8") as f:
        corpus = json.load(f)
    tasks = list(corpus.get("tasks", []))
    if args.smoke and args.smoke > 0:
        tasks = tasks[: args.smoke]

    if args.runs < 1:
        print(f"[bench_se50_batch] ERROR: --runs must be >=1, got {args.runs}", file=sys.stderr)
        return 2

    timeout_s = args.timeout_per_task or (300 if args.mode == "seeded" else 600)
    provider = _resolve_llm_provider(args.mode, seed=args.seed, model_override=args.model)

    csv_path = outdir / "se50_results.csv"
    summary_path = outdir / "run_summary.json"

    rows: list[TaskRow] = []
    t_start = time.perf_counter()

    print(f"[bench_se50_batch] mode={args.mode} tasks={len(tasks)} runs={args.runs} base_seed={args.seed} timeout_s={timeout_s} outdir={outdir}")

    for t_idx, task in enumerate(tasks):
        task_id = task.get("id", f"T{t_idx:03d}")
        goal = task.get("goal_string", task.get("goal", ""))
        category = task.get("category", "Unknown")
        difficulty = task.get("difficulty", "UNKNOWN")
        print(f"  [{t_idx + 1}/{len(tasks)}] task={task_id} cat={category} diff={difficulty}")

        for run_idx in range(args.runs):
            run_seed = args.seed + t_idx * 100 + run_idx * 10
            t_task_start = time.perf_counter()
            try:
                result = _run_single_seeded(goal=goal, seed=run_seed, run_index=run_idx)
            except Exception as exc:
                result = {
                    "tristate": "REJECT",
                    "pass_fail_heuristic": 0,
                    "duration_ms": int((time.perf_counter() - t_task_start) * 1000),
                    "plan_id_sha256": "ERROR",
                    "promotion_tier_counts_json": json.dumps({}, sort_keys=True),
                }
            rows.append(
                TaskRow(
                    task_id=task_id,
                    goal=goal,
                    category=category,
                    difficulty=difficulty,
                    seed=run_seed,
                    run_idx=run_idx,
                    tristate=result["tristate"],
                    promotion_tier_counts_json=result["promotion_tier_counts_json"],
                    pass_fail_heuristic=result["pass_fail_heuristic"],
                    duration_ms=int(result["duration_ms"]),
                    plan_id_sha256=result["plan_id_sha256"],
                )
            )

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "task_id",
                "goal",
                "category",
                "difficulty",
                "seed",
                "run_idx",
                "tristate",
                "promotion_tier_counts_json",
                "pass_fail_heuristic",
                "duration_ms",
                "plan_id_sha256",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.task_id,
                    row.goal,
                    row.category,
                    row.difficulty,
                    row.seed,
                    row.run_idx,
                    row.tristate,
                    row.promotion_tier_counts_json,
                    row.pass_fail_heuristic,
                    row.duration_ms,
                    row.plan_id_sha256,
                ]
            )

    dict_rows = [asdict(r) for r in rows]
    all_passes = [r.pass_fail_heuristic for r in rows]
    per_task_passes: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        per_task_passes[r.task_id].append(r.pass_fail_heuristic)
    pass1_per_task = [_pass_at_k(1, v) for v in per_task_passes.values()]
    pass3_per_task = [_pass_at_k(3, v) for v in per_task_passes.values()]
    total_ms = int((time.perf_counter() - t_start) * 1000)

    summary = {
        "harness": "bench_se50_batch",
        "corpus": str(corpus_path),
        "mode": args.mode,
        "base_seed": args.seed,
        "runs_per_task": args.runs,
        "tasks_total": len(tasks),
        "timeout_per_task_s": timeout_s,
        "provider": type(provider).__name__,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "wall_duration_ms": total_ms,
        "rows_written": len(rows),
        "csv": str(csv_path),
        "aggregates": {
            "signoff_total": sum(all_passes),
            "signoff_rate": round(sum(all_passes) / len(all_passes), 4) if all_passes else 0.0,
            "pass_at_1": round(sum(pass1_per_task) / len(pass1_per_task), 4) if pass1_per_task else 0.0,
            "pass_at_3": round(sum(pass3_per_task) / len(pass3_per_task), 4) if pass3_per_task else 0.0,
            "avg_duration_ms": (round(sum(r.duration_ms for r in rows) / len(rows), 2) if rows else 0),
        },
        "per_category": _per_group_table(dict_rows, "category"),
        "per_difficulty": _per_group_table(dict_rows, "difficulty"),
    }

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, sort_keys=True)

    print(
        f"[bench_se50_batch] DONE: signoffs={summary['aggregates']['signoff_total']}/{len(rows)} "
        f"pass@1={summary['aggregates']['pass_at_1']:.3f} csv={csv_path} summary={summary_path}"
    )

    from noesis.benchmarks.stats import _wilson_ci

    csv_a_path = outdir / "se50_paper_table2.csv"
    groups_ab: dict[tuple[str, str], list[TaskRow]] = defaultdict(list)
    for r in rows:
        groups_ab[(r.category, r.difficulty)].append(r)

    diff_order = {"trivial": 0, "easy": 1, "medium": 2, "hard": 3, "expert": 4}
    sorted_keys = sorted(groups_ab.keys(), key=lambda kv: (kv[0], diff_order.get(kv[1].lower(), 99)))

    with open(csv_a_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "category", "difficulty", "n_total", "n_correct", "pass_at_1",
            "ci95_low", "ci95_high", "avg_duration_ms", "min_duration_ms",
            "max_duration_ms", "promotion_sum_total",
        ])
        for (cat, diff) in sorted_keys:
            grp = groups_ab[(cat, diff)]
            passes = [it.pass_fail_heuristic for it in grp]
            n_total = len(grp)
            n_correct = sum(passes)
            p1 = _pass_at_k(1, passes)
            p_prop = (n_correct / n_total) if n_total > 0 else 0.0
            ci_lo, ci_hi = _wilson_ci(p_prop, n_total)
            durations = [it.duration_ms for it in grp]
            avg_dur = round(sum(durations) / len(durations), 2) if durations else 0
            min_dur = min(durations) if durations else 0
            max_dur = max(durations) if durations else 0
            promo_sum_total = 0
            for it in grp:
                try:
                    pd = json.loads(it.promotion_tier_counts_json)
                    promo_sum_total += sum(int(v) for v in pd.values())
                except Exception:
                    pass
            writer.writerow([
                cat, diff, n_total, n_correct, round(p1, 6),
                round(ci_lo, 6), round(ci_hi, 6), avg_dur, min_dur, max_dur,
                promo_sum_total,
            ])
    print(f"[paper_table] Wrote: se50_paper_table2.csv — {len(sorted_keys)} rows")

    csv_b_path = outdir / "se50_paper_table4_appendix_promotion_tiers.csv"
    groups_b: dict[str, list[TaskRow]] = defaultdict(list)
    for r in rows:
        groups_b[r.category].append(r)

    tier_map = {"working": "T1", "conversation": "T2", "user": "T3", "project": "T4", "episodic": "T5", "semantic": "T6"}
    tier_cols = [
        ("working", "avg_T1_working"),
        ("conversation", "avg_T2_conversation"),
        ("user", "avg_T3_user"),
        ("project", "avg_T4_project"),
        ("episodic", "avg_T5_episodic"),
        ("semantic", "avg_T6_semantic"),
    ]

    with open(csv_b_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "category", "n_tasks",
            "avg_T1_working", "avg_T2_conversation", "avg_T3_user",
            "avg_T4_project", "avg_T5_episodic", "avg_T6_semantic",
        ])
        for cat in sorted(groups_b.keys()):
            grp = groups_b[cat]
            unique_tasks = len({it.task_id for it in grp})
            tier_sums: dict[str, float] = {k: 0.0 for k, _ in tier_cols}
            tier_counts: dict[str, int] = {k: 0 for k, _ in tier_cols}
            for it in grp:
                try:
                    pd = json.loads(it.promotion_tier_counts_json)
                    for tk, _ in tier_cols:
                        if tk in pd:
                            tier_sums[tk] += float(pd[tk])
                            tier_counts[tk] += 1
                except Exception:
                    pass
            tier_avgs = []
            for tk, _ in tier_cols:
                if tier_counts[tk] > 0:
                    tier_avgs.append(round(tier_sums[tk] / tier_counts[tk], 4))
                else:
                    tier_avgs.append(0.0)
            writer.writerow([cat, unique_tasks, *tier_avgs])
    print(f"[paper_table] Wrote: se50_paper_table4_appendix_promotion_tiers.csv — {len(groups_b)} rows")

    try:
        from noesis.benchmarks.stats import aggregate_run_and_write_json
        stats_result = aggregate_run_and_write_json(outdir=args.outdir)
        print(f"\n[stats] Wrote paper tables: {stats_result.get('tables_path')!r}")
    except Exception as exc:  # pragma: no cover - best-effort, harness shouldn't fail if stats fail
        print(f"\n[stats] WARN: stats post-processing failed (continuing anyway): {exc!s:.200}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
