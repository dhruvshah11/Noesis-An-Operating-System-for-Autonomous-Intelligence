"""Service layer (M5.1): PlannerSvc + AgentSvc = PlannerAgent + AgentRuntime.

Usage::

    from noesis.core.di import build_default_container
    from noesis.services import build_services_from_container, PlannerSvc, AgentSvc

    async with build_default_container() as c:
        planner_svc, agent_svc = await build_services_from_container(c)
        report = planner_svc.plan("Summarise and cite a history of agentic systems.")
        run_id, results = await agent_svc.run_plan_async(report.plan)
"""

from noesis.services.kernel_services import (
    AgentSvc,
    PlannerSvc,
    StepRunResult,
    _default_tool_registry,
    build_services_from_container,
)

__all__ = [
    "AgentSvc",
    "PlannerSvc",
    "StepRunResult",
    "_default_tool_registry",
    "build_services_from_container",
]
