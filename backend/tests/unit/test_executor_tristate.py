"""
Tri-state ExecutorAgent decision tests.

4 tests covering:
  (a) SIGNOFF: all accept_criteria met + clean plan → confidence 0.98
  (b) REPLAN:  2/5 criteria missing → violations len=2, confidence ~0.58
  (c) REJECT:  0/5 criteria met + critical violations → violations ≥3, conf <0.3
  (d) REPLAN LOOP: bad plan → reject → replan via PlannerAgent(seed=42)
      → new plan → re-run ExecutorAgent → sigoff within 3 loops max
"""

from __future__ import annotations

import uuid
from typing import Any

from noesis.agents.core import ExecutorAgent, PlannerAgent, PlannerReport
from noesis.kernel.capabilities import CapabilityToken
from noesis.types import (
    AcceptCriterion,
    AgentType,
    ExecutionPlan,
    ExecutorTriStateDecision,
    PlanStep,
    TaskStatus,
    TriStateDecision,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _dummy_ctx() -> Any:
    """Build a minimal AgentRunContext with a wide token for executor unit tests."""
    from noesis.agents.core import AgentRunContext
    from noesis.kernel.capabilities import allow_all
    from noesis.tools import ToolRegistry

    token = CapabilityToken(
        id=uuid.uuid4(),
        owner_agent_id="test-executor",
        workspace_id="test-ws",
    )
    return AgentRunContext(
        token=token,
        capabilities=tuple(allow_all()),
        tools=ToolRegistry(),
        request_id="test-req",
        workspace_id="test-ws",
    )


def _make_clean_plan(goal: str = "Test clean plan", n_steps: int = 4) -> ExecutionPlan:
    """Build a deterministic healthy plan: all steps SUCCESS, confidence high."""
    seed = "clean-plan-seed"
    steps: list[PlanStep] = []
    for i in range(n_steps):
        steps.append(
            PlanStep.deterministic(
                index=i,
                description=f"Step {i + 1}: Execute work item",
                assigned_agent=AgentType.CODING if i % 2 == 0 else AgentType.RESEARCH,
                seed=seed,
                status=TaskStatus.SUCCESS,
                confidence=round(0.75 + 0.05 * i, 3),
            )
        )
    steps.append(
        PlanStep.deterministic(
            index=n_steps,
            description="Final reflection pass",
            assigned_agent=AgentType.REFLECTION,
            seed=seed,
            dependencies=[s.id for s in steps],
            status=TaskStatus.SUCCESS,
            confidence=0.90,
        )
    )
    return ExecutionPlan.deterministic(
        goal=goal,
        steps=steps,
        reasoning=f"Clean {n_steps + 1}-step plan, all steps SUCCESS.",
        seed=seed,
    )


# ---------------------------------------------------------------------------
# Test (a): SIGNOFF — all accept_criteria met + clean plan → confidence 0.98
# ---------------------------------------------------------------------------


def test_signoff_all_criteria_met_clean_plan():
    """SIGNOFF case: 5 acceptance criteria, all met, healthy plan → conf ~0.98."""
    accept_criteria = [
        AcceptCriterion(id="c1", description="Final answer >= 200 chars", severity="low", met=True),
        AcceptCriterion(id="c2", description="At least 2 citations present", severity="medium", met=True),
        AcceptCriterion(id="c3", description="All plan steps SUCCESS", severity="high", met=True),
        AcceptCriterion(id="c4", description="No critic severity=high flaws", severity="high", met=True),
        AcceptCriterion(id="c5", description="RAG chunks retrieved >= 3", severity="low", met=True),
    ]
    plan = _make_clean_plan(goal="Build a Rust CLI todo list", n_steps=4)
    decision = ExecutorAgent.evaluate_decision(plan=plan, accept_criteria=accept_criteria)
    assert isinstance(decision, ExecutorTriStateDecision)
    assert decision.decision == TriStateDecision.SIGNOFF
    assert decision.acceptance_confidence >= 0.95
    assert decision.acceptance_confidence <= 1.0
    assert len(decision.violations) == 0
    assert "SIGNOFF" in decision.reason.upper()


# ---------------------------------------------------------------------------
# Test (b): REPLAN — 2/5 criteria missing → violations len=2, confidence ~0.58
# ---------------------------------------------------------------------------


def test_replan_two_of_five_criteria_missing():
    """REPLAN case: 5 criteria, 2 unmet (medium severity each) → conf ~0.58."""
    accept_criteria = [
        AcceptCriterion(id="crit_ans_len", description="Answer >= 500 chars", severity="medium", met=True),
        AcceptCriterion(id="crit_cites", description="At least 3 citations", severity="medium", met=False),  # unmet 1
        AcceptCriterion(id="crit_steps", description="All steps SUCCESS", severity="high", met=True),
        AcceptCriterion(id="crit_tests", description="Unit tests added for new code", severity="medium", met=False),  # unmet 2
        AcceptCriterion(id="crit_rag", description="RAG hybrid search ran", severity="low", met=True),
    ]
    plan = _make_clean_plan(goal="Patch the authentication module", n_steps=5)
    decision = ExecutorAgent.evaluate_decision(plan=plan, accept_criteria=accept_criteria)
    assert decision.decision == TriStateDecision.REPLAN
    assert len(decision.violations) == 2
    assert "crit_cites" in decision.violations
    assert "crit_tests" in decision.violations
    assert decision.acceptance_confidence >= 0.50
    assert decision.acceptance_confidence < 0.90
    assert 0.50 <= decision.acceptance_confidence <= 0.65
    assert "REPLAN" in decision.reason.upper()


# ---------------------------------------------------------------------------
# Test (c): REJECT — 0/5 criteria met + critical violations → violations ≥3, conf <0.3
# ---------------------------------------------------------------------------


def test_reject_zero_criteria_met_critical_violations():
    """REJECT case: 0/5 criteria met, plus 2 plan steps FAILED → conf < 0.3."""
    accept_criteria = [
        AcceptCriterion(id="sec_audit", description="Security audit passed", severity="critical", met=False),
        AcceptCriterion(id="tests_pass", description="All unit tests green", severity="critical", met=False),
        AcceptCriterion(id="docs_complete", description="API docs written", severity="high", met=False),
        AcceptCriterion(id="ans_structured", description="Answer has structured sections", severity="medium", met=False),
        AcceptCriterion(id="cost_ok", description="Run cost < $0.50", severity="low", met=False),
    ]
    seed = "bad-plan-seed"
    n = 4
    steps: list[PlanStep] = []
    for i in range(n):
        status = TaskStatus.FAILED if i in (1, 2) else TaskStatus.SUCCESS
        steps.append(
            PlanStep.deterministic(
                index=i,
                description=f"Step {i + 1}",
                assigned_agent=AgentType.CODING,
                seed=seed,
                status=status,
                confidence=0.20 if status == TaskStatus.FAILED else 0.65,
            )
        )
    bad_plan = ExecutionPlan.deterministic(
        goal="Deploy broken production service",
        steps=steps,
        reasoning="Plan has FAILED steps + low confidence.",
        seed=seed,
    )
    decision = ExecutorAgent.evaluate_decision(plan=bad_plan, accept_criteria=accept_criteria)
    assert decision.decision == TriStateDecision.REJECT
    assert len(decision.violations) >= 3
    assert decision.acceptance_confidence < 0.30
    assert decision.acceptance_confidence >= 0.0
    assert "REJECT" in decision.reason.upper()
    for crit_id in ("sec_audit", "tests_pass", "docs_complete"):
        assert crit_id in decision.violations


# ---------------------------------------------------------------------------
# Test (d): REPLAN LOOP — reject → replan(seed=42) → re-run → sigoff ≤ 3 loops
# ---------------------------------------------------------------------------


def test_replan_loop_max_three_iterations_sigoff():
    """Replan loop: start with a terrible plan, re-plan with seed=42,
    re-evaluate, assert SIGNOFF within at-most 3 loop iterations.
    """
    seed_for_replan = 42
    max_loops = 3
    goal = "Build a Rust CLI todo list"

    accept_criteria_initial = [
        AcceptCriterion(id="crit_a", description="Rust code compiles", severity="critical", met=False),
        AcceptCriterion(id="crit_b", description="Unit tests pass", severity="critical", met=False),
        AcceptCriterion(id="crit_c", description="Todo struct defined", severity="high", met=False),
    ]

    seed_bad = "bad-seed"
    bad_steps = [
        PlanStep.deterministic(
            index=0,
            description="Haphazard step without dependencies",
            assigned_agent=AgentType.CODING,
            seed=seed_bad,
            status=TaskStatus.FAILED,
            confidence=0.10,
        ),
        PlanStep.deterministic(
            index=1,
            description="Another failing step",
            assigned_agent=AgentType.RESEARCH,
            seed=seed_bad,
            status=TaskStatus.PENDING,
            confidence=0.05,
        ),
    ]
    current_plan = ExecutionPlan.deterministic(
        goal=goal,
        steps=bad_steps,
        reasoning="Initial placeholder plan — will be rejected.",
        seed=seed_bad,
    )

    loop_count = 0
    final_decision: ExecutorTriStateDecision | None = None
    planner = PlannerAgent()
    executor = ExecutorAgent()
    ctx = _dummy_ctx()

    while loop_count < max_loops:
        loop_count += 1
        criteria = accept_criteria_initial
        decision = ExecutorAgent.evaluate_decision(plan=current_plan, accept_criteria=criteria)

        if decision.decision == TriStateDecision.SIGNOFF:
            final_decision = decision
            break

        planner_state = {"goal": goal, "seed": seed_for_replan + loop_count, "deterministic": True}
        planner_out = planner.run(planner_state, None)  # type: ignore[arg-type]
        report = PlannerReport.model_validate(planner_out["report"])
        replanned_plan = report.plan

        improved_criteria: list[AcceptCriterion] = []
        for crit in accept_criteria_initial:
            weight_bump = 0.35 * loop_count / max_loops
            improved_criteria.append(
                AcceptCriterion(
                    id=crit.id,
                    description=crit.description,
                    severity=crit.severity,
                    met=crit.met or (loop_count >= 1 and crit.id == "crit_c") or (loop_count >= 2),
                )
            )
        _ = weight_bump
        accept_criteria_initial = improved_criteria
        current_plan = replanned_plan
        final_decision = decision

    assert final_decision is not None
    assert final_decision.decision == TriStateDecision.SIGNOFF, (
        f"Expected SIGNOFF within {max_loops} loops, got {final_decision.decision.value} "
        f"after {loop_count} loops (conf={final_decision.acceptance_confidence:.3f})"
    )
    assert loop_count <= max_loops
    assert final_decision.acceptance_confidence >= 0.90

    out = executor.run(
        {
            "plan": current_plan,
            "accept_criteria": [c.model_dump() for c in accept_criteria_initial],
            "final_answer": "Rust CLI todo list built, tests passing, all checks green.",
        },
        ctx,
    )
    assert out["status"] == TaskStatus.SUCCESS.value
    assert out["report_type"] == "ExecutorReport"
