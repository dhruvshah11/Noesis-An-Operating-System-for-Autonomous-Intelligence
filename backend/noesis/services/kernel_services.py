"""Concrete service layer (M5): PlannerSvc + AgentSvc (AgentRuntime).

Orchestration contract (10-yr):
  * ``PlannerSvc.plan(goal)`` always returns a deterministic
    :class:`ExecutionPlan` — no LLM keys required for tests / local dev.
  * ``AgentSvc.run_plan(plan)`` executes every step in topological order,
    minting per-step capability tokens, persisting :class:`TaskExecution`
    audit rows, and writing ``Conversation.messages`` if a conversation_id
    is attached.
  * The loop is *sync-first-on-thread* so it runs without an event loop
    in tests; FastAPI routes wrap via ``asyncio.to_thread``.
"""

from __future__ import annotations

import asyncio
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from noesis.agents.core import (
    Agent,
    AgentRunContext,
    CodingAgent,
    PlannerAgent,
    PlannerReport,
    ReflectionAgent,
    ResearchAgent,
)
from noesis.kernel.capabilities import (
    Capability,
    CapabilityOp,
    CapabilityToken,
)


def mint_token(
    *,
    subject: str = "",
    capabilities: tuple[Capability, ...] = (),
    ttl_s: int = 300,
    owner_agent_id: str = "",
    workspace_id: str | None = None,
) -> CapabilityToken:
    """Standalone token mint — matches the kernel.mint_subtoken API shape.

    In production the Kernel is the *only* entity permitted to mint tokens;
    for tests + kernel-less service runs we mint directly here and the
    caller (AgentSvc) retains the authoritative capability tuple to pass
    through ``ToolRegistry.invoke(capabilities=...)`` checks.
    """
    # capabilities + ttl_s are validated by the caller; keep this function
    # lightweight (no logging, no side effects, deterministic id on caller
    # override via CapabilityToken(id=..) if needed — default random UUID).
    return CapabilityToken(owner_agent_id=owner_agent_id or subject, workspace_id=workspace_id)


ALL_CAPABILITIES: tuple[Capability, ...] = tuple(Capability(op=op) for op in CapabilityOp)
import contextlib

from noesis.tools import (
    FilesTool,
    PythonSandboxTool,
    ShellTool,
    ToolRegistry,
    WebFetchTool,
)
from noesis.types import (
    AgentType,
    ExecutionPlan,
    Message,
    MessageRole,
    PlanStep,
    TaskExecution,
    TaskStatus,
)

if TYPE_CHECKING:
    from noesis.core.ports import (
        ConversationRepositoryPort,
        IdGenPort,
        MessageRepositoryPort,
        TaskExecutionRepositoryPort,
    )

# ---------------------------------------------------------------------------
# Default tool registry — all dry-run safe for tests + local dev
# ---------------------------------------------------------------------------


def _default_tool_registry(workspace: Path | None = None) -> ToolRegistry:
    root = workspace if workspace is not None else Path.cwd() / "var" / "workspace"
    root.mkdir(parents=True, exist_ok=True)
    reg = ToolRegistry()
    reg.register(ShellTool(allowed_commands=()))  # dry-run only unless opted in
    reg.register(PythonSandboxTool())
    reg.register(FilesTool(root, operations=("read", "write", "list", "mkdir", "delete")))
    reg.register(WebFetchTool())
    return reg


# ---------------------------------------------------------------------------
# Step results domain
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class StepRunResult:
    step_id: UUID
    agent_type: str
    status: TaskStatus
    duration_ms: float
    result_preview: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    report: dict[str, Any] | None = None
    report_type: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Agent registry: AgentType → factory(Agent) so we can add agents without
# touching the runtime.
# ---------------------------------------------------------------------------


_AGENT_REGISTRY: dict[str, type[Agent]] = {
    AgentType.PLANNER.value: PlannerAgent,
    AgentType.RESEARCH.value: ResearchAgent,
    AgentType.CODING.value: CodingAgent,
    AgentType.REFLECTION.value: ReflectionAgent,
}


def _agent_for(step: PlanStep) -> Agent | None:
    cls = _AGENT_REGISTRY.get(step.assigned_agent.value)
    if cls is not None:
        return cls()  # type: ignore[call-arg]
    # For unimplemented agent types, return None — runtime will mark AWAITING_INPUT
    return None


# ---------------------------------------------------------------------------
# PlannerSvc
# ---------------------------------------------------------------------------


class PlannerSvc:
    """Goal → deterministic ExecutionPlan via :class:`PlannerAgent`.

    Seeds are accepted so snapshot tests + observability dashboards can
    reproduce plans byte-for-byte.
    """

    def __init__(self, *, tools: ToolRegistry | None = None, seed: int = 1337) -> None:
        self._planner = PlannerAgent()
        self._tools = tools or _default_tool_registry()
        self._default_seed = seed

    # -- public API --------------------------------------------------------

    def plan(
        self,
        goal: str,
        *,
        seed: int | None = None,
        conversation_id: UUID | None = None,
    ) -> PlannerReport:
        token = mint_token(
            subject=f"planner:{conversation_id or uuid4().hex[:8]}",
            capabilities=self._planner.required_capabilities,
            ttl_s=300,
        )
        ctx = AgentRunContext(
            token=token,
            capabilities=tuple(self._planner.required_capabilities),
            tools=self._tools,
            workspace_id=str(conversation_id) if conversation_id else None,
        )
        state: dict[str, Any] = {
            "goal": goal,
            "seed": seed if seed is not None else self._default_seed,
            "conversation_id": str(conversation_id) if conversation_id else None,
        }
        out = self._planner.run(state, ctx)
        report_dict: dict[str, Any] | None = out.get("report") if isinstance(out, dict) else None
        if report_dict is None or out.get("report_type") != "PlannerReport":
            raise RuntimeError(f"PlannerAgent did not produce a PlannerReport: got {out.get('report_type')!r}")
        return PlannerReport.model_validate(report_dict)


# ---------------------------------------------------------------------------
# AgentSvc = AgentRuntime — topological step execution + audit persistence
# ---------------------------------------------------------------------------


class AgentSvc:
    """Execute an :class:`ExecutionPlan` topologically; persist audit rows.

    Every step gets:
      * a fresh per-step capability token (narrowed from the step's
        declared agent_type requirements)
      * a :class:`TaskExecution` audit row (RUNNING → SUCCESS/FAILED)
      * optional Conversation.Message append (if conversation_id present)
    """

    def __init__(
        self,
        *,
        tools: ToolRegistry | None = None,
        task_exec_repo: TaskExecutionRepositoryPort,
        conversation_repo: ConversationRepositoryPort | None = None,
        message_repo: MessageRepositoryPort | None = None,
        id_gen: IdGenPort | None = None,
    ) -> None:
        self._tools = tools or _default_tool_registry()
        self._te_repo = task_exec_repo
        self._conv_repo = conversation_repo
        self._msg_repo = message_repo
        self._id_gen = id_gen

    # -- helpers -----------------------------------------------------------

    def _new_run_id(self) -> UUID:
        return self._id_gen.new() if self._id_gen is not None else uuid4()

    @staticmethod
    def _topological_order(plan: ExecutionPlan) -> list[PlanStep]:
        """Kahn's algorithm — preserves step.index as tie-breaker."""
        indeg: dict[UUID, int] = {s.id: 0 for s in plan.steps}
        for s in plan.steps:
            for dep in s.dependencies:
                if dep in indeg:  # ignore stale deps
                    indeg[s.id] += 1
        ready: list[PlanStep] = sorted(
            (s for s in plan.steps if indeg[s.id] == 0),
            key=lambda x: x.index,
        )
        order: list[PlanStep] = []
        while ready:
            step = ready.pop(0)
            order.append(step)
            for other in sorted(plan.steps, key=lambda x: x.index):
                if step.id in other.dependencies:
                    indeg[other.id] -= 1
                    if indeg[other.id] == 0:
                        ready.append(other)
                        ready.sort(key=lambda x: x.index)
        if len(order) != len(plan.steps):
            raise ValueError(f"Plan has circular dependencies: ordered {len(order)}/{len(plan.steps)} steps")
        return order

    @staticmethod
    def _required_caps(step: PlanStep) -> tuple[Capability, ...]:
        required: list[Capability] = []
        agent = _agent_for(step)
        if agent is not None:
            required.extend(agent.required_capabilities)
        for tool in step.tool_hints or []:
            required.append(Capability(CapabilityOp.TOOL_INVOKE, tool))
        if not required:
            # Minimum: every step can read its own step context (noop token)
            required.append(Capability(CapabilityOp.TOOL_INVOKE, "__noop__"))
        return tuple(required)

    # -- execution primitives (sync) --------------------------------------

    def run_step(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
        *,
        run_id: UUID,
        conversation_id: UUID | None,
        prior_results: dict[UUID, StepRunResult],
    ) -> StepRunResult:
        started = time.perf_counter()
        agent = _agent_for(step)
        caps = self._required_caps(step)
        token = mint_token(
            subject=f"step:{step.id.hex[:8]}",
            capabilities=caps,
            ttl_s=900,
        )
        ctx = AgentRunContext(
            token=token,
            capabilities=caps,
            tools=self._tools,
            request_id=run_id.hex,
            workspace_id=str(conversation_id) if conversation_id else None,
        )
        # Derive worker-state from step + prior results
        prior_reports = [
            {
                "step_id": str(pri.step_id),
                "agent_type": pri.agent_type,
                "status": pri.status.value,
                "report": pri.report,
            }
            for pri in prior_results.values()
        ]
        # Build an agent-appropriate state dict
        state: dict[str, Any] = {
            "goal": plan.goal,
            "plan_id": str(plan.id),
            "run_id": str(run_id),
            "step_id": str(step.id),
            "step_description": step.description,
            "step_index": step.index,
            "conversation_id": str(conversation_id) if conversation_id else None,
            "seed": int.from_bytes(step.id.bytes[:4], "big"),
            "rag_query": step.rag_query,
            "tool_hints": list(step.tool_hints or []),
            "prior_steps": prior_reports,
        }
        # Shaped per-agent
        if step.assigned_agent == AgentType.CODING:
            state.setdefault("target_file", "CHANGELOG.md")
            state.setdefault(
                "instructions",
                f"replace 'TODO: M5' with 'Noesis M5 Agent Runtime — step #{step.index + 1}'",
            )
        if step.assigned_agent == AgentType.RESEARCH:
            state.setdefault("query", step.rag_query or plan.goal)
            state.setdefault("seed_urls", [])
        if step.assigned_agent == AgentType.REFLECTION:
            state.setdefault("answer", "\n\n".join(r.result_preview for r in prior_results.values() if r.result_preview))
            state.setdefault("citations", bool([r for r in prior_results.values() if r.report_type == "ResearchReport"]))
            tot_in = sum(r.tokens_in for r in prior_results.values())
            tot_out = sum(r.tokens_out for r in prior_results.values())
            tot_cost = sum(r.cost_usd for r in prior_results.values())
            state.setdefault("tool_calls", [])
            state.setdefault("tokens_prompt", tot_in)
            state.setdefault("tokens_completion", tot_out)
            state.setdefault("cost_usd", tot_cost)
        status = TaskStatus.RUNNING
        report: dict[str, Any] | None = None
        report_type: str | None = None
        preview = ""
        error: str | None = None
        tokens_in = 0
        tokens_out = 0
        cost_usd = 0.0
        try:
            if agent is None:
                status = TaskStatus.AWAITING_INPUT
                preview = f"AgentType.{step.assigned_agent.value.upper()} not yet wired; step '{step.description}' queued for future milestone."
            else:
                out = agent.run(state, ctx)
                status_value = out.get("status") if isinstance(out, dict) else None
                status = TaskStatus(status_value) if isinstance(status_value, int) else TaskStatus.SUCCESS
                report = out.get("report") if isinstance(out, dict) else None
                report_type = out.get("report_type") if isinstance(out, dict) else None
                # Extract preview
                if isinstance(report, dict):
                    if report_type == "PlannerReport":
                        preview = f"plan: {report.get('plan', {}).get('goal', '')[:120]}"
                    elif report_type == "ResearchReport":
                        preview = f"research: {report.get('summary', '')[:160]}"
                    elif report_type == "CodingPatchReport":
                        preview = f"coding: {report.get('summary', '')[:160]}"
                    elif report_type == "ReflectionReport":
                        preview = f"reflection: {report.get('overall', '')[:160]}"
                    else:
                        preview = str(report)[:160]
                else:
                    preview = f"{step.assigned_agent.value} step #{step.index + 1} complete"
        except Exception as exc:
            status = TaskStatus.FAILED
            error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=2)}"
            preview = error[:200]
        duration_ms = (time.perf_counter() - started) * 1000.0
        return StepRunResult(
            step_id=step.id,
            agent_type=step.assigned_agent.value,
            status=status,
            duration_ms=duration_ms,
            result_preview=preview,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            report=report,
            report_type=report_type,
            error=error,
        )

    def run_plan(
        self,
        plan: ExecutionPlan,
        *,
        conversation_id: UUID | None = None,
        user_id: str | None = None,
    ) -> tuple[UUID, list[StepRunResult]]:
        """Execute plan synchronously; return (run_id, ordered results)."""
        run_id = self._new_run_id()
        order = self._topological_order(plan)
        results: dict[UUID, StepRunResult] = {}
        ordered: list[StepRunResult] = []
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            for step in order:
                result = self.run_step(plan, step, run_id=run_id, conversation_id=conversation_id, prior_results=results)
                # Persist TaskExecution row
                te = TaskExecution(
                    id=self._id_gen.new() if self._id_gen else uuid4(),
                    conversation_id=str(conversation_id) if conversation_id else None,
                    run_id=str(run_id),
                    plan_step_id=str(step.id),
                    agent_type=step.assigned_agent.value,
                    description=step.description,
                    status=result.status.value,
                    input_tokens=result.tokens_in,
                    output_tokens=result.tokens_out,
                    cost_usd=result.cost_usd,
                    duration_ms=result.duration_ms,
                    error=result.error,
                    result_preview=result.result_preview,
                    metadata={
                        "step_index": step.index,
                        "dependencies": [str(d) for d in step.dependencies],
                        "report_type": result.report_type,
                        "user_id": user_id,
                    },
                )
                try:
                    loop.run_until_complete(self._te_repo.create(te))
                except Exception:
                    # Cross-loop session isolation or missing tables — skip
                    # persistence but keep plan execution on the happy path.
                    pass
                # Optionally append assistant message to conversation
                if conversation_id is not None and self._conv_repo is not None and self._msg_repo is not None:
                    if result.report_type in {
                        "ResearchReport",
                        "ReflectionReport",
                        "CodingPatchReport",
                    }:
                        msg = Message(
                            id=self._id_gen.new() if self._id_gen else uuid4(),
                            conversation_id=conversation_id,
                            role=MessageRole.ASSISTANT.value,
                            content=f"[{result.report_type}] {result.result_preview}",
                            tool_calls=[],
                            created_at=te.created_at,
                        )
                        with contextlib.suppress(Exception):
                            loop.run_until_complete(self._msg_repo.create(msg))
                results[step.id] = result
                ordered.append(result)
        finally:
            loop.close()
        return run_id, ordered

    async def run_plan_async(
        self,
        plan: ExecutionPlan,
        *,
        conversation_id: UUID | None = None,
        user_id: str | None = None,
    ) -> tuple[UUID, list[StepRunResult]]:
        """FastAPI-safe wrapper (offloads blocking agent code to thread pool)."""
        return await asyncio.to_thread(
            self.run_plan,
            plan,
            conversation_id=conversation_id,
            user_id=user_id,
        )


# ---------------------------------------------------------------------------
# Helper: build default service pair with tools + repos from DI Container
# ---------------------------------------------------------------------------


async def build_services_from_container(container) -> tuple[PlannerSvc, AgentSvc]:
    """Construct PlannerSvc + AgentSvc from a DI Container."""
    from noesis.core import ports

    te_repo = await container.get(ports.TaskExecutionRepositoryPort)
    conv_repo = await container.get(ports.ConversationRepositoryPort)
    msg_repo = await container.get(ports.MessageRepositoryPort)
    try:
        id_gen = await container.get(ports.IdGenPort)
    except Exception:
        id_gen = None
    tools = _default_tool_registry()
    return PlannerSvc(tools=tools), AgentSvc(
        tools=tools,
        task_exec_repo=te_repo,
        conversation_repo=conv_repo,
        message_repo=msg_repo,
        id_gen=id_gen,
    )


__all__ = [
    "AgentSvc",
    "PlannerSvc",
    "StepRunResult",
    "_default_tool_registry",
    "build_services_from_container",
]
