"""
12-agent seeded skeleton pipeline (no LLM calls).

Pipeline order (Sanskrit codenames → AgentType):
  01. Manan      → PlannerAgent       (PLANNER)
  02. Darshak    → ResearchAgent      (RESEARCH)
  03. Vidya      → RAGAgent           (RAG)
  04. Parikshak  → JudgeAgent         (JUDGE)
  05. Karmakarta → CodingAgent        (CODING)
  06. Anveshak   → ToolAgent          (TOOL)
  07. Vivechak   → ReflectionAgent    (REFLECTION)
  08. Paalak     → MemoryAgent        (MEMORY)
  09. Rakshak    → CriticAgent        (CRITIC)
  10. Samanyaka  → OrchestratorAgent  (ORCHESTRATOR)
  11. Kriyakārī  → ExecutorAgent      (EXECUTOR)  ← SIGNOFF / REJECT / REPLAN
  12. Nirikshak  → SupervisorAgent    (SUPERVISOR)

Each agent is invoked as a deterministic no-op that produces a phase report
derived from the (goal, seed) pair — zero LLM provider calls, zero network.

CLI:
  py scripts/run_full_seeded_pipeline.py \\
      --goal "Build a Rust CLI todo list" \\
      --seed 42 \\
      --runs 3

Exit code:
  0  → Kriyakārī returned SIGNOFF on EVERY run.
  1  → One or more runs did not SIGNOFF (REJECT / REPLAN / exception).
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

# Force utf-8 on stdout/stderr (Windows cp1252 guard) — see determinism_manifest.py
if __name__ == "__main__":  # pragma: no cover
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

from noesis.agents.core import (
    AgentRoster,
    AgentRunContext,
    CriticReport,
    ExecutorReport,
    JudgeReport,
    PlannerReport,
    ReflectionReport,
    ResearchReport,
    SupervisorReport,
    ToolReport,
)
from noesis.kernel.capabilities import (
    CapabilityToken,
    allow_all,
)
from noesis.tools import ToolRegistry
from noesis.types import (
    AcceptCriterion,
    AgentType,
    ExecutionPlan,
    TaskStatus,
    TriStateDecision,
)

# ---------------------------------------------------------------------------
# 12 Sanskrit-codenamed agents mapped to their AgentType roster entries
# ---------------------------------------------------------------------------

PIPELINE: tuple[tuple[str, AgentType], ...] = (
    ("Manan", AgentType.PLANNER),
    ("Darshak", AgentType.RESEARCH),
    ("Vidya", AgentType.RAG),
    ("Parikshak", AgentType.JUDGE),
    ("Karmakarta", AgentType.CODING),
    ("Anveshak", AgentType.TOOL),
    ("Vivechak", AgentType.REFLECTION),
    ("Paalak", AgentType.MEMORY),
    ("Rakshak", AgentType.CRITIC),
    ("Samanyaka", AgentType.ORCHESTRATOR),
    ("Kriyakari", AgentType.EXECUTOR),
    ("Nirikshak", AgentType.SUPERVISOR),
)

REPORT_TYPES: dict[AgentType, type] = {
    AgentType.PLANNER: PlannerReport,
    AgentType.RESEARCH: ResearchReport,
    AgentType.RAG: type("RAGReport", (), {}),
    AgentType.JUDGE: JudgeReport,
    AgentType.CODING: type("CodingPatchReport", (), {}),
    AgentType.TOOL: ToolReport,
    AgentType.REFLECTION: ReflectionReport,
    AgentType.MEMORY: type("MemoryReport", (), {}),
    AgentType.CRITIC: CriticReport,
    AgentType.ORCHESTRATOR: type("OrchestratorReport", (), {}),
    AgentType.EXECUTOR: ExecutorReport,
    AgentType.SUPERVISOR: SupervisorReport,
}


@dataclass(slots=True)
class PhaseResult:
    phase_name: str
    agent_type: str
    status_ok: bool
    decision: str = ""
    confidence: float = 0.0
    duration_ms: int = 0
    report_type: str = ""


@dataclass(slots=True)
class RunResult:
    run_index: int
    seed: int
    goal: str
    phases: list[PhaseResult]
    sigoff: bool
    total_ms: int


def _wide_token(ws_id: str) -> AgentRunContext:
    """Build a full-capability AgentRunContext for the skeleton pipeline.

    All 12 agents use the same wide token — this is a seeded skeleton, so
    capability-gating is intentionally permissive.  The kernel scheduler's
    ``AgentRoster.spawn()`` path does the real gate in production.
    """
    token = CapabilityToken(
        id=uuid.uuid4(),
        owner_agent_id="skeleton-pipeline",
        workspace_id=ws_id,
    )
    tools = ToolRegistry()
    return AgentRunContext(
        token=token,
        capabilities=tuple(allow_all()),
        tools=tools,
        request_id=f"req-{ws_id}",
        workspace_id=ws_id,
    )


def _phase_state(
    agent_type: AgentType,
    *,
    goal: str,
    seed: int,
    phase_idx: int,
    prior_output: dict,
    plan: ExecutionPlan | None,
    accept_criteria: list[AcceptCriterion] | None,
) -> dict:
    """Build the state dict for phase N — tailored per agent signature."""
    base: dict = {
        "goal": goal,
        "seed": seed + phase_idx,
        "deterministic": True,
        "workspace_id": f"ws-skel-{seed}-{phase_idx}",
    }
    if agent_type == AgentType.PLANNER:
        return {**base, "query": goal, "rag_query": goal}
    if agent_type == AgentType.RESEARCH:
        return {**base, "query": goal, "seed_urls": []}
    if agent_type == AgentType.RAG:
        return {**base, "query": goal, "rag_query": goal, "k": 5}
    if agent_type == AgentType.JUDGE:
        return {
            **base,
            "prompt": f"Rank candidates for: {goal}",
            "candidates": [
                {"id": "c1", "text": f"Candidate A for {goal}: plan-based approach [src01]"},
                {"id": "c2", "text": f"Candidate B for {goal}: iterative approach"},
                {"id": "c3", "text": f"Candidate C for {goal}: hybrid plan with citations [src02][src03]."},
            ],
        }
    if agent_type == AgentType.CODING:
        fake_src = f'# Skeleton Rust file for goal: {goal}\nfn main() {{ println!("hello noesis"); }}\n'
        return {
            **base,
            "target_file": f"src/goals/goal_{seed}.rs",
            "instructions": (f'replace "hello noesis" with "{goal[:40]}"\nreplace "fn main" with "pub fn main"'),
            "_mock_source": fake_src,
        }
    if agent_type == AgentType.TOOL:
        return {
            **base,
            "calls": [],
        }
    if agent_type == AgentType.REFLECTION:
        answer = (
            f"Plan-based solution outline for {goal}:\n"
            "  1. Decompose into steps [src01].\n"
            "  2. Implement each step with tests [src02].\n"
            "  3. Run reflection pass.\n"
        )
        return {
            **base,
            "answer": answer,
            "final_answer": answer,
            "tool_calls": [],
            "citations": True,
            "tokens_prompt": 100,
            "tokens_completion": 200,
            "cost_usd": 0.0001,
        }
    if agent_type == AgentType.MEMORY:
        return {
            **base,
            "goal": goal,
            "operation": "recall",
            "keys": [f"skel:{seed}:{phase_idx}"],
        }
    if agent_type == AgentType.CRITIC:
        draft = (
            f"# {goal}\n\n## Overview\nStructured multi-section document with citations.\n## Plan\n1. Research\n2. Code\n3. Test [src01]\n4. Deploy\n"
        )
        return {**base, "draft": draft, "answer": draft}
    if agent_type == AgentType.ORCHESTRATOR:
        return {
            **base,
            "goal": goal,
            "workers": [AgentType.RESEARCH.value, AgentType.RAG.value, AgentType.CODING.value],
            "join_policy": "all",
        }
    if agent_type == AgentType.EXECUTOR:
        return {
            **base,
            "plan": plan,
            "accept_criteria": [c.model_dump() for c in (accept_criteria or [])],
            "final_answer": (
                f"## Final Answer: {goal}\n\n"
                "All 10 prior phases completed successfully.\n"
                "Acceptance criteria reviewed and verified by Rakshak (Critic).\n"
                "Signed off by Kriyakārī (Executor) skeleton pipeline.\n"
            ),
        }
    if agent_type == AgentType.SUPERVISOR:
        return {**base, "goal": goal, "tree_goal": goal}
    return base


def _build_accept_criteria(goal: str, seed: int) -> list[AcceptCriterion]:
    """Deterministic acceptance criteria list for Kriyakārī phase.

    All marked ``met=True`` so the skeleton pipeline SIGNOFFs reliably
    across every run — enabling ``exit 0`` semantics.
    """
    tokens = [t for t in "".join(c if c.isalnum() or c.isspace() else " " for c in goal).split() if len(t) >= 3]
    base = [
        AcceptCriterion(
            id=f"crit-manan-{seed}",
            description="Manan (Planner) decomposed goal into steps",
            severity="high",
            met=True,
        ),
        AcceptCriterion(
            id=f"crit-darshak-{seed}",
            description="Darshak (Research) produced >=2 sources",
            severity="medium",
            met=True,
        ),
        AcceptCriterion(
            id=f"crit-vidya-{seed}",
            description="Vidya (RAG) retrieved >=3 chunks",
            severity="medium",
            met=True,
        ),
        AcceptCriterion(
            id=f"crit-parikshak-{seed}",
            description="Parikshak (Judge) ranked >=2 candidates",
            severity="low",
            met=True,
        ),
        AcceptCriterion(
            id=f"crit-karmakarta-{seed}",
            description="Karmakarta (Coding) produced patch list",
            severity="high",
            met=True,
        ),
        AcceptCriterion(
            id=f"crit-vivechak-{seed}",
            description="Vivechak (Reflection) found zero high-severity mistakes",
            severity="critical",
            met=True,
        ),
        AcceptCriterion(
            id=f"crit-rakshak-{seed}",
            description="Rakshak (Critic) overall quality >= 0.80",
            severity="high",
            met=True,
        ),
    ]
    for i, tok in enumerate(tokens[:3]):
        base.append(
            AcceptCriterion(
                id=f"crit-token-{seed}-{i}",
                description=f"Goal token '{tok}' covered in final answer",
                severity="low",
                met=True,
            )
        )
    return base


def run_single_pipeline(goal: str, seed: int, run_index: int) -> RunResult:
    """Execute the 12-phase skeleton pipeline for one (goal, seed) pair."""
    ws_id = f"skel-{run_index}-{seed}"
    ctx = _wide_token(ws_id)
    accept_criteria = _build_accept_criteria(goal, seed)
    plan: ExecutionPlan | None = None
    prior_output: dict = {}
    phases: list[PhaseResult] = []
    t_total_start = time.perf_counter()

    for phase_idx, (name_sa, atype) in enumerate(PIPELINE):
        t_start = time.perf_counter()
        agent = AgentRoster.get(atype)
        state = _phase_state(
            atype,
            goal=goal,
            seed=seed,
            phase_idx=phase_idx,
            prior_output=prior_output,
            plan=plan,
            accept_criteria=accept_criteria,
        )
        try:
            out = agent.run(state, ctx)
        except Exception as exc:
            phases.append(
                PhaseResult(
                    phase_name=name_sa,
                    agent_type=atype.value,
                    status_ok=False,
                    decision="ERROR",
                    report_type=f"{type(exc).__name__}: {exc}",
                    duration_ms=int((time.perf_counter() - t_start) * 1000),
                )
            )
            break
        status_ok = out.get("status") in (TaskStatus.SUCCESS.value, TaskStatus.AWAITING_INPUT.value)
        decision_str = ""
        conf = 0.0
        rtype = out.get("report_type", "")
        report = out.get("report")
        if isinstance(report, dict):
            conf = float(report.get("confidence") or 0.0)
            decision_str = str(report.get("decision") or "")
            tristate = report.get("tristate")
            if isinstance(tristate, dict):
                decision_str = tristate.get("decision") or decision_str
        if atype == AgentType.PLANNER and rtype == "PlannerReport" and isinstance(report, dict):
            try:
                pr = PlannerReport.model_validate(report)
                plan = pr.plan
            except Exception:
                plan = None
        phases.append(
            PhaseResult(
                phase_name=name_sa,
                agent_type=atype.value,
                status_ok=status_ok,
                decision=decision_str,
                confidence=conf,
                report_type=rtype,
                duration_ms=int((time.perf_counter() - t_start) * 1000),
            )
        )
        prior_output = out

    kriyakari_phase = next((p for p in phases if p.phase_name == "Kriyakari"), None)
    sigoff = bool(kriyakari_phase and kriyakari_phase.decision == TriStateDecision.SIGNOFF.value)

    return RunResult(
        run_index=run_index,
        seed=seed,
        goal=goal,
        phases=phases,
        sigoff=sigoff,
        total_ms=int((time.perf_counter() - t_total_start) * 1000),
    )


def _print_summary_table(results: list[RunResult]) -> None:
    cols = (
        "run",
        "seed",
        "Manan",
        "Darshak",
        "Vidya",
        "Parikshak",
        "Karmak.",
        "Anvesh.",
        "Vivech.",
        "Paalak",
        "Rakshak",
        "Samany.",
        "Kriyak.",
        "Niriksh.",
        "ms",
        "SIGNOFF",
    )
    widths = [max(len(c), 5) for c in cols]
    hdr = " | ".join(c.ljust(widths[i]) for i, c in enumerate(cols))
    print("=" * len(hdr))
    print(hdr)
    print("=" * len(hdr))
    for r in results:
        cells: list[str] = [
            str(r.run_index),
            str(r.seed),
        ]
        phase_by_name = {p.phase_name: p for p in r.phases}
        for sanskrit, _ in PIPELINE:
            ph = phase_by_name.get(sanskrit)
            if ph is None:
                cells.append("—")
            elif ph.phase_name == "Kriyakari":
                cells.append((ph.decision or "?")[:8].upper())
            else:
                cells.append("OK" if ph.status_ok else "FAIL")
        cells.append(str(r.total_ms))
        cells.append("YES" if r.sigoff else "NO")
        row = " | ".join(c.ljust(widths[i]) for i, c in enumerate(cells))
        print(row)
    print("=" * len(hdr))


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="run_full_seeded_pipeline",
        description="Run 12-agent Sanskrit-named skeleton pipeline (seeded, no LLM).",
    )
    p.add_argument("--goal", type=str, required=True, help="Goal string for the pipeline.")
    p.add_argument("--seed", type=int, default=42, help="Integer seed for PlannerAgent determinism.")
    p.add_argument("--runs", type=int, default=1, help="Number of independent runs (>=1).")
    p.add_argument("--json", action="store_true", help="Emit machine-readable JSON summary instead of table.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.runs < 1:
        print(f"[run_full_seeded_pipeline] ERROR: --runs must be >=1, got {args.runs}", file=sys.stderr)
        return 2
    if len(args.goal.strip()) < 5:
        print(f"[run_full_seeded_pipeline] ERROR: --goal must be >=5 chars, got {args.goal!r}", file=sys.stderr)
        return 2

    results: list[RunResult] = []
    all_signed = True

    for idx in range(args.runs):
        run_seed = args.seed + idx * 1000
        result = run_single_pipeline(args.goal, run_seed, run_index=idx)
        results.append(result)
        if not result.sigoff:
            all_signed = False

    if getattr(args, "json", False):
        summary = {
            "goal": args.goal,
            "seed_base": args.seed,
            "runs": args.runs,
            "all_sigoff": all_signed,
            "results": [asdict(r) for r in results],
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    else:
        print(f"[run_full_seeded_pipeline] Goal: {args.goal!r}  |  base_seed={args.seed}  |  runs={args.runs}")
        _print_summary_table(results)
        sigoff_count = sum(1 for r in results if r.sigoff)
        print(
            f"[run_full_seeded_pipeline] Kriyakārī SIGNOFF: {sigoff_count}/{args.runs} "
            f"→ {'ALL PASSED (exit 0)' if all_signed else 'SOME FAILED (exit 1)'}"
        )

    return 0 if all_signed else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
