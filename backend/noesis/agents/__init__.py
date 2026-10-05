"""Agent implementations + roster registry.

Public surface:
  - :class:`Agent` ABC — every specialised agent implements one ``run`` method
    (dict state in, dict state out — LangGraph node-call compatible).
  - 12 concrete agents matching every slot in :class:`AgentType`.
  - Report DTOs for every agent's structured output.
  - :class:`AgentRoster` central registry with spawn-time capability gating.

Use the roster instead of importing concrete classes directly when code needs
to dispatch by AgentType enum value.
"""

from __future__ import annotations

from noesis.agents.core import (
    Agent,
    AgentRoster,
    AgentRunContext,
    CitationRef,
    CodingAgent,
    CodingPatchReport,
    CriticAgent,
    CriticReport,
    ExecutorAgent,
    ExecutorReport,
    JudgeAgent,
    JudgeReport,
    MemoryAgent,
    MemoryReport,
    Mistake,
    OrchestratorAgent,
    OrchestratorReport,
    PatchStep,
    PlannerAgent,
    PlannerReport,
    RAGAgent,
    RAGReport,
    RankedCandidate,
    ReflectionAgent,
    ReflectionReport,
    ResearchAgent,
    ResearchReport,
    RetrievedChunk,
    SupervisorAgent,
    SupervisorReport,
    ToolAgent,
    ToolReport,
)

__all__ = [
    "Agent",
    "AgentRoster",
    "AgentRunContext",
    "CitationRef",
    "CodingAgent",
    "CodingPatchReport",
    "CriticAgent",
    "CriticReport",
    "ExecutorAgent",
    "ExecutorReport",
    "JudgeAgent",
    "JudgeReport",
    "MemoryAgent",
    "MemoryReport",
    "Mistake",
    "OrchestratorAgent",
    "OrchestratorReport",
    "PatchStep",
    "PlannerAgent",
    "PlannerReport",
    "RAGAgent",
    "RAGReport",
    "RankedCandidate",
    "ReflectionAgent",
    "ReflectionReport",
    "ResearchAgent",
    "ResearchReport",
    "RetrievedChunk",
    "SupervisorAgent",
    "SupervisorReport",
    "ToolAgent",
    "ToolReport",
]
