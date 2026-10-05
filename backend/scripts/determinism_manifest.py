"""
Noesis Determinism Manifest Generator.

Paper-claim C3 evidence generation:
  * For each (goal, seed) pair, run the noesis pipeline N times on the
    pure-Python deterministic path (--deterministic, 0 LLM calls, 0 tokens).
  * SHA-256 the canonicalised aggregate JSON of each run.
  * Record: run index, duration_ms, sha256(JSON canonical).
  * Produce a final manifest CSV + per-(goal,seed) identity matrix:
      cell[i,j] = 1 if sha(run i) == sha(run j) else 0.
  * Reproducibility score = (# identical pairs) / (# total runs ** 2).

C3 target: 100 runs × 5 goals × seed=42 => reproducibility_score = 1.0.

This module doubles as:
  * a pytest-fast determinism smoke (use --runs 3 via test_determinism_manifest.py)
  * the viva-demo audit script (--runs 20 to produce CODS-COMAD evidence)

Run from repo root (powershell):
  cd backend ; py scripts/determinism_manifest.py --runs 20 --output ../docs/eval/determinism_manifest_20260824.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Force utf-8 on stdout/stderr so Windows cp1252 doesn't choke on goal strings
# with unicode arrows / smart quotes. This is safe for CI and for viva demos
# that `| tee` unicode-heavy tables (§4 SE50 W-category tasks contain `→`).
# ONLY apply top-level wrapper when run as a script (`__main__`), NOT when
# imported by pytest — otherwise we destroy pytest's own capture streams and cause
# `I/O operation on closed file.` teardown errors.
if __name__ == "__main__":  # pragma: no cover - entry guard
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
    # Wrap into explicit buffer-backed TextIOWrapper so unicode surrogates pass through.
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        # Non-buffer stream (pytest capsys / StringIO): leave as-is
        pass

# ---------------------------------------------------------------------------
# Reproducibility helpers (no typer/cli heavy imports so this file can be
# `import`ed from pytest without launching a full sub-process).
# ---------------------------------------------------------------------------

DEFAULT_GOALS: tuple[str, ...] = (
    "Produce a Rust CLI todo list with add/list/done flags",
    "Refactor 3-file Python parser into visitor pattern",
    "Write a TypeScript Zod schema for a payments API",
    "Plan a 6-month 18-week capstone Gantt for Noesis",
    "Summarise the Noesis 6-tier memory T1 Indriya to T6 Tattva",
)

DEFAULT_SEEDS: tuple[int, ...] = (42, 7, 1337)


def _strip_wall_clock(obj: object) -> object:
    """Return a deep-copy that excludes wall-clock / non-deterministic keys so
    the manifest audit hash compares *semantic* output, not timing noise.

    Keys excluded: duration_ms / created_at / started_at / finished_at /
    latency_ms / request_id / workspace / token / id (when id is opaque UUID
    used only as local identity; real seeded IDs live nested in models so
    they remain preserved).
    """
    NON_DET_KEYS = {
        "duration_ms",
        "created_at",
        "started_at",
        "finished_at",
        "latency_ms",
        "request_id",
        "workspace",
        "workspace_id",
        "token",
        "owner_agent_id",
        # Agent-instance handles stored into state dict or returned by
        # _add_result_status: they are only containers carrying the
        # deterministic report we actually care about, and their per-run
        # object repr / memory-id breaks SHA-256 identity for no semantic
        # value (e.g. PlannerAgent.run rewrites state["memory_agent"] each
        # call with a fresh MemoryAgent instance).
        "memory_agent",
        "tools",
        "registry",
        "capabilities",
        "handle",
        "agent",
    }

    _WS_RE = re.compile(r"workspace[^=]*=['\"][^'\"]+['\"]")
    _TOKEN_RE = re.compile(r"Parent token=[0-9a-fA-F]{6,}")
    _AUDIT_RE = re.compile(r"Workspace write for audit:\s*['\"][^'\"]+['\"]")
    _CTX_RE = re.compile(r"ctx(?:[^A-Za-z0-9]?[0-9a-fA-F\-]{6,})+")

    def _scrub(val: object) -> object:
        if isinstance(val, str):
            val = _WS_RE.sub("workspace=<redacted>", val)
            val = _TOKEN_RE.sub("Parent token=<redacted>", val)
            val = _AUDIT_RE.sub("Workspace write for audit: <redacted>", val)
            val = _CTX_RE.sub("ctx=<redacted>", val)
            return val
        return val

    if isinstance(obj, dict):
        return {_scrub(k) if isinstance(k, str) else k: _strip_wall_clock(v) for k, v in obj.items() if k not in NON_DET_KEYS}
    if isinstance(obj, list):
        return [_strip_wall_clock(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_strip_wall_clock(v) for v in obj)
    if isinstance(obj, str):
        return _scrub(obj)
    return obj


def canonical_json(obj: object) -> bytes:
    return json.dumps(
        _strip_wall_clock(obj),
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def sha256_hex(obj: object) -> str:
    return hashlib.sha256(canonical_json(obj)).hexdigest()


# Run via an *in-process* pipeline helper — avoids subprocess overhead and
# keeps 100×20 manifest runs ≤ ~60s on a 40xx laptop.  Same contract as
# `noesis run -f json` but direct function call.


def _run_once_inprocess(goal: str, seed: int, *, workspace: str) -> dict:
    """Emulate the pure-Python path of cli.run() and return the JSON payload.

    All errors are captured as {status:FAILED, error_kind: ...} records so
    the manifest always finishes instead of aborting a 1000-run batch at row 513.
    """
    # Heavy imports kept local.
    try:
        import hashlib as _hashlib
        import random as _random

        from noesis.agents.core import (
            AgentRoster,
            AgentRunContext,
            OrchestratorReport,
            PlannerReport,
        )
        from noesis.kernel.capabilities import (
            Capability,
            CapabilityOp,
            CapabilityToken,
            PermissionDenied,
        )
        from noesis.tools import ToolRegistry
        from noesis.types import AgentType, TaskStatus
    except Exception as exc:  # pragma: no cover - environment failure
        return {
            "goal": goal,
            "seed": seed,
            "status": "IMPORT_ERROR",
            "error_kind": type(exc).__name__,
            "error": str(exc),
        }

    _random.seed(seed)
    owner = f"manifest-seed-{seed}"
    token = CapabilityToken(owner_agent_id=owner, workspace_id=workspace)
    registry = ToolRegistry()
    caps = tuple(Capability(op, "*") for op in CapabilityOp)
    ctx = AgentRunContext(
        token=token,
        capabilities=caps,
        tools=registry,
        request_id=f"manifest-{seed}-{_hashlib.md5(goal.encode()).hexdigest()[:8]}",
        workspace_id=workspace,
    )

    t0 = time.perf_counter()
    pipeline_status = TaskStatus.SUCCESS
    final_summary = ""
    aggregate: dict | None = None
    steps_run: list[dict] = []

    try:
        planner = AgentRoster.spawn(AgentType.PLANNER, ctx)
        plan_state: dict = {"goal": goal, "max_steps": 12, "seed": seed}
        plan_out = planner.run(plan_state, ctx)
        plan_report = PlannerReport(**plan_out["report"])
        steps_run.append(
            {
                "slot": 1,
                "agent": AgentType.PLANNER.value,
                "status": TaskStatus(plan_out["status"]).name,
                "report_type": "PlannerReport",
                "summary": (plan_report.plan.reasoning or plan_report.goal)[:140],
            }
        )
        if TaskStatus(plan_out["status"]) != TaskStatus.SUCCESS:
            pipeline_status = TaskStatus(plan_out["status"])
            final_summary = f"Planner failed: {(plan_report.plan.reasoning or plan_report.goal)[:160]}"
            aggregate = {"plan": plan_out}
            return {
                "goal": goal,
                "seed": seed,
                "workspace": workspace,
                "status": pipeline_status.name,
                "summary": final_summary,
                "duration_ms": round((time.perf_counter() - t0) * 1000, 3),
                "steps_run": steps_run,
                "report": aggregate,
            }

        orchestrator = AgentRoster.spawn(AgentType.ORCHESTRATOR, ctx)
        orch_workers = [s.assigned_agent for s in plan_report.plan.steps[:12]]
        orch_state = {
            "goal": goal,
            "seed": seed,
            "max_steps": 12,
            "workers": orch_workers,
            "join_policy": "all",
        }
        orch_out = orchestrator.run(orch_state, ctx)
        orch_report = OrchestratorReport(**orch_out["report"])
        steps_run.append(
            {
                "slot": len(steps_run) + 1,
                "agent": AgentType.ORCHESTRATOR.value,
                "status": TaskStatus(orch_out["status"]).name,
                "report_type": "OrchestratorReport",
                "summary": orch_report.summary[:160],
            }
        )

        dispatched = [AgentType(w) for w in orch_report.dispatched_to]
        results_by_worker: dict[str, dict] = {}
        for i, wtype in enumerate(dispatched, start=len(steps_run) + 1):
            worker = AgentRoster.spawn(wtype, ctx)
            wstate = {
                "goal": goal,
                "query": goal,
                "seed": seed,
                "max_steps": 12,
                "plan": plan_report.model_dump(mode="json"),
            }
            wout = worker.run(wstate, ctx)
            st = TaskStatus(wout["status"]).name
            steps_run.append(
                {
                    "slot": i,
                    "agent": wtype.value,
                    "status": st,
                    "report_type": wout.get("report_type"),
                }
            )
            results_by_worker[wtype.value] = wout
            if st != TaskStatus.SUCCESS.name:
                pipeline_status = TaskStatus.FAILED

        try:
            executor = AgentRoster.spawn(AgentType.EXECUTOR, ctx)
            signoff_candidates = [
                {
                    "worker": wt.value,
                    "report": results_by_worker[wt.value].get("report"),
                    "status": results_by_worker[wt.value].get("status"),
                }
                for wt in dispatched
            ]
            exec_out = executor.run(
                {
                    "goal": goal,
                    "seed": seed,
                    "candidate_reports": signoff_candidates,
                },
                ctx,
            )
            steps_run.append(
                {
                    "slot": len(steps_run) + 1,
                    "agent": AgentType.EXECUTOR.value,
                    "status": TaskStatus(exec_out["status"]).name,
                    "report_type": exec_out.get("report_type"),
                }
            )
            aggregate = {
                "goal": goal,
                "seed": seed,
                "workspace": workspace,
                "deterministic": True,
                "planner": plan_out,
                "orchestrator": orch_out,
                "workers": results_by_worker,
                "executor_signoff": exec_out,
                "steps_run": steps_run,
            }
            decision = (exec_out.get("report") or {}).get("decision") or "(no decision)"
            final_summary = f"Executor sign-off gate: {decision!r}."
            if str(decision).lower() == "reject":
                pipeline_status = TaskStatus.FAILED
        except PermissionDenied as pd:
            pipeline_status = TaskStatus.FAILED
            final_summary = f"Executor gate PD op={pd.op.value} target={pd.target}"
            aggregate = {"error": "EXECUTOR_GATE_DENIED", "details": str(pd)}

    except PermissionDenied as pd:
        pipeline_status = TaskStatus.FAILED
        final_summary = f"Spawn denied {pd.op.value}:{pd.target}"

    total_ms = round((time.perf_counter() - t0) * 1000, 3)
    return {
        "goal": goal,
        "seed": seed,
        "workspace": workspace,
        "status": pipeline_status.name,
        "summary": final_summary,
        "duration_ms": total_ms,
        "steps_run": steps_run,
        "report": aggregate,
    }


@dataclass(slots=True)
class ManifestRecord:
    goal_index: int
    seed_index: int
    run: int
    goal: str
    seed: int
    duration_ms: float
    sha256_json: str
    pipeline_status: str
    error: str = ""


@dataclass(slots=True)
class ManifestSummary:
    runs_total: int = 0
    goals_count: int = 0
    seeds_count: int = 0
    identical_pairs_within_group: int = 0
    total_pairs_within_group: int = 0
    reproducibility_score: float = 0.0
    per_goal: list[dict] = field(default_factory=list)
    per_seed: list[dict] = field(default_factory=list)
    per_group: list[dict] = field(default_factory=list)
    csv_rows: list[ManifestRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _identity_score(shas: list[str]) -> tuple[int, int, float]:
    n = len(shas)
    pairs = n * n
    identical = sum(1 for a in shas for b in shas if a == b)
    score = (identical / pairs) if pairs else 1.0
    return identical, pairs, round(score, 6)


def build_manifest(
    *,
    goals: tuple[str, ...] = DEFAULT_GOALS,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    runs_per_pair: int = 20,
    workspace_prefix: str = "manifest",
    progress: bool = False,
) -> ManifestSummary:
    summary = ManifestSummary(goals_count=len(goals), seeds_count=len(seeds))

    per_goal: dict[int, list[str]] = {i: [] for i in range(len(goals))}
    per_seed: dict[int, list[str]] = {j: [] for j in range(len(seeds))}
    group_shas: dict[tuple[int, int], list[str]] = {}
    all_shas: list[str] = []

    for gi, goal in enumerate(goals):
        for si, seed in enumerate(seeds):
            key = (gi, si)
            group_shas[key] = []
            for r in range(runs_per_pair):
                workspace = f"{workspace_prefix}-g{gi}-s{si}-r{r}"
                result = _run_once_inprocess(goal, seed, workspace=workspace)
                sha = sha256_hex(result.get("report") or result)
                rec = ManifestRecord(
                    goal_index=gi,
                    seed_index=si,
                    run=r,
                    goal=goal,
                    seed=seed,
                    duration_ms=float(result.get("duration_ms", 0) or 0),
                    sha256_json=sha,
                    pipeline_status=str(result.get("status", "UNKNOWN")),
                    error=(str(result.get("error")) if result.get("error") else ""),
                )
                summary.csv_rows.append(rec)
                per_goal[gi].append(sha)
                per_seed[si].append(sha)
                group_shas[key].append(sha)
                all_shas.append(sha)
                if progress:
                    bar = (
                        f"[g{gi + 1}/{len(goals)} s{si + 1}/{len(seeds)} "
                        f"r{r + 1}/{runs_per_pair}] {sha[:12]} "
                        f"status={rec.pipeline_status} {rec.duration_ms:6.2f}ms"
                    )
                    print(bar, file=sys.stderr)

    summary.runs_total = len(all_shas)
    total_ident = 0
    total_pairs = 0
    for (gi, si), shas in group_shas.items():
        idn, prs, sc = _identity_score(shas)
        total_ident += idn
        total_pairs += prs
        summary.per_group.append(
            {
                "goal_index": gi,
                "seed_index": si,
                "seed": seeds[si],
                "goal": goals[gi],
                "runs": len(shas),
                "identical_pairs": idn,
                "total_pairs": prs,
                "reproducibility_score": sc,
                "unique_sha256_count": len(set(shas)),
            }
        )
    summary.identical_pairs_within_group = total_ident
    summary.total_pairs_within_group = total_pairs
    summary.reproducibility_score = round(total_ident / total_pairs if total_pairs else 1.0, 6)

    for gi, shas in per_goal.items():
        idn, prs, sc = _identity_score(shas)
        summary.per_goal.append(
            {
                "goal_index": gi,
                "goal": goals[gi],
                "runs": len(shas),
                "identical_pairs": idn,
                "total_pairs": prs,
                "reproducibility_score": sc,
                "unique_sha256_count": len(set(shas)),
            }
        )

    for si, shas in per_seed.items():
        idn, prs, sc = _identity_score(shas)
        summary.per_seed.append(
            {
                "seed_index": si,
                "seed": seeds[si],
                "runs": len(shas),
                "identical_pairs": idn,
                "total_pairs": prs,
                "reproducibility_score": sc,
                "unique_sha256_count": len(set(shas)),
            }
        )

    return summary


CSV_HEADER: tuple[str, ...] = (
    "goal_index",
    "seed_index",
    "run",
    "goal",
    "seed",
    "duration_ms",
    "sha256_json",
    "pipeline_status",
    "error",
)


def write_csv(records: list[ManifestRecord], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(CSV_HEADER)
        for r in records:
            writer.writerow(
                [
                    r.goal_index,
                    r.seed_index,
                    r.run,
                    r.goal,
                    r.seed,
                    f"{r.duration_ms:.6f}",
                    r.sha256_json,
                    r.pipeline_status,
                    r.error,
                ]
            )


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Noesis C3 determinism manifest generator. Produces a CSV audit + JSON summary of bit-exact reproducibility.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=20,
        help="Runs per (goal, seed) pair. CODS-COMAD evidence: 20 => 5×3×20=300 runs. Pytest smoke: 3.",
    )
    parser.add_argument(
        "--goals",
        type=Path,
        default=None,
        help="Optional newline-delimited goals file. Default = 5 capstone sample goals.",
    )
    parser.add_argument(
        "--seeds",
        type=str,
        default="42",
        help="Comma-separated seed list. Default = '42' for single-seed CODS-COMAD evidence.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/eval/determinism_manifest.csv"),
        help="Output CSV path (summary JSON written alongside with .json suffix).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-run progress stderr.",
    )

    args = parser.parse_args(argv)

    if args.runs < 1:
        print("--runs must be >=1", file=sys.stderr)
        return 2

    goals: tuple[str, ...] = DEFAULT_GOALS
    if args.goals is not None:
        if not args.goals.is_file():
            print(f"--goals file not found: {args.goals}", file=sys.stderr)
            return 2
        goals = tuple(
            line.strip() for line in args.goals.read_text(encoding="utf-8").splitlines() if line.strip() and not line.strip().startswith("#")
        )
        if not goals:
            print("--goals file empty", file=sys.stderr)
            return 2

    try:
        seeds = tuple(int(s.strip()) for s in args.seeds.split(",") if s.strip())
    except ValueError:
        print("--seeds must be comma separated integers", file=sys.stderr)
        return 2
    if not seeds:
        print("--seeds empty", file=sys.stderr)
        return 2

    started = time.time()
    print(
        f"Starting manifest: goals={len(goals)} seeds={len(seeds)} runs/pair={args.runs} "
        f"=> total={len(goals) * len(seeds) * args.runs} (pure-Python 0 LLM calls)",
        file=sys.stderr,
    )
    manifest = build_manifest(
        goals=goals,
        seeds=seeds,
        runs_per_pair=args.runs,
        progress=not args.quiet,
    )
    output_path: Path = args.output.resolve()
    write_csv(manifest.csv_rows, output_path)
    summary_path = output_path.with_suffix(output_path.suffix + ".summary.json")
    summary_path.write_text(
        json.dumps(manifest.to_dict(), indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )

    elapsed = time.time() - started
    print(f"\nManifest wrote {output_path}", file=sys.stderr)
    print(f"Manifest summary wrote {summary_path}", file=sys.stderr)
    print(
        f"Reproducibility score = {manifest.reproducibility_score} "
        f"({manifest.identical_pairs_within_group}/{manifest.total_pairs_within_group} same-(goal,seed)-pairs) over "
        f"{manifest.runs_total} runs in {elapsed:.1f}s.",
        file=sys.stderr,
    )

    # Print human readable one-liners per goal/seed/group to stdout so viva demo
    # can | tee a log.
    for g in manifest.per_goal:
        print(f"[goal {g['goal_index']}] score={g['reproducibility_score']} unique_shas={g['unique_sha256_count']}/{g['runs']}")
    for s in manifest.per_seed:
        print(f"[seed {s['seed']}] score={s['reproducibility_score']} unique_shas={s['unique_sha256_count']}/{s['runs']}")
    for grp in manifest.per_group:
        print(
            f"[g{grp['goal_index']} s{grp['seed']}] seed={grp['seed']} "
            f"score={grp['reproducibility_score']} "
            f"unique_shas={grp['unique_sha256_count']}/{grp['runs']} "
            f"goal={grp['goal'][:52]!r}"
        )

    # Exit non-zero only if score < 1.0 (CI gating).
    return 0 if manifest.reproducibility_score >= 1.0 else 3


if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
    raise SystemExit(main())
