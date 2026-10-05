"""
Prompt registry + Jinja2-free string templates.

Goals:
  1. Every prompt used by Noesis lives in ONE place so we can version them,
     compare deltas, and regress against a golden dataset (benchmarks §18).
  2. Templates support **variables** via ``{name}`` — safe subset of
     str.format() — no arbitrary code execution (audit §10 prompt injection).
  3. Each prompt declares its *output-schema contract* so callers know how to
     parse.  The pipeline ties into :mod:`astra.llm.parse`.

Usage::

    from noesis.llm.prompts import registry
    tpl = registry.get("planner.draft_plan")
    prompt = tpl.render(objective="Build a FastAPI server…", max_steps=5)
    print(tpl.version, tpl.tags)   # v1 | {"planner", "reasoning"}
"""

from __future__ import annotations

import string
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, ClassVar

from noesis.logging import get_logger

log = get_logger(__name__)


class OutputKind(StrEnum):
    """Declares what format the LLM is instructed to return."""

    TEXT = "text"
    JSON = "json"
    JSONL = "jsonl"
    YAML = "yaml"
    MARKDOWN = "markdown"
    PYDANTIC = "pydantic"  # expects a Pydantic class; see parse.parse_structured_output


@dataclass(frozen=True)
class PromptTemplate:
    """One prompt template with explicit contract metadata."""

    name: str
    text: str
    output_kind: OutputKind = OutputKind.TEXT
    output_schema: dict[str, Any] | None = None  # JSONSchema or None for free text
    version: str = "v1"
    tags: frozenset[str] = frozenset()
    description: str = ""

    # Cache parsed Formatter results for speed — dict order is preserved.
    _field_names: tuple[str, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        names: list[str] = []
        seen: set[str] = set()
        for _, field_name, _, _ in string.Formatter().parse(self.text):
            if field_name and field_name not in seen:
                # Split off ".idx" (we don't support attributes in templates).
                base = field_name.split(".", 1)[0].split("[", 1)[0]
                seen.add(base)
                names.append(base)
        # Cannot assign to frozen self directly; use the thaw loophole.
        object.__setattr__(self, "_field_names", tuple(names))

    @property
    def variables(self) -> tuple[str, ...]:
        """Return the list of variable names referenced by this template."""
        return self._field_names

    def render(self, **variables: object) -> str:
        """Render the template.  Raises KeyError on missing variables."""
        try:
            return self.text.format_map(variables)
        except KeyError as exc:
            raise KeyError(
                f"Prompt template {self.name!r} is missing required variable {exc!s}. Declared variables: {list(self.variables)}"
            ) from None
        except ValueError as exc:
            raise ValueError(f"Malformed template {self.name!r}: {exc}") from exc


class PromptRegistry:
    """Collection of every prompt in the system."""

    def __init__(self) -> None:
        self._prompts: dict[str, PromptTemplate] = {}

    def register(self, template: PromptTemplate) -> PromptTemplate:
        if template.name in self._prompts:
            log.warning("prompt.overwritten", name=template.name, prev_version=self._prompts[template.name].version)
        self._prompts[template.name] = template
        return template

    def get(self, name: str) -> PromptTemplate:
        if name not in self._prompts:
            raise KeyError(f"Prompt {name!r} is not registered.  Available: {sorted(self._prompts.keys())!r}")
        return self._prompts[name]

    def __contains__(self, name: object) -> bool:
        return name in self._prompts

    def list_all(self, *, tag: str | None = None) -> list[PromptTemplate]:
        items = list(self._prompts.values())
        if tag:
            items = [p for p in items if tag in p.tags]
        return sorted(items, key=lambda p: p.name)


# ---------------------------------------------------------------------------
# Default registry with all Milestone-0 prompts wired in.  Each prompt below
# is a real one that will be used by the corresponding agent in M1.
# ---------------------------------------------------------------------------

registry: ClassVar[PromptRegistry] = PromptRegistry()  # type: ignore[assignment]
registry = PromptRegistry()


# --- Common system messages ------------------------------------------------

registry.register(
    PromptTemplate(
        name="system.common.astra_identity",
        text=(
            "You are Noesis, an autonomous multi-agent research & engineering "
            "orchestrator built by Noesis contributors. Be precise, cite sources, "
            "and think step-by-step before acting.  Always follow the structured "
            "output schema requested.\n"
            "Operating context: {context}"
        ),
        tags=frozenset({"system", "identity"}),
        description="Prepended to every conversation: Noesis canonical system identity.",
    )
)

# --- Planner ---------------------------------------------------------------

registry.register(
    PromptTemplate(
        name="planner.draft_plan",
        output_kind=OutputKind.PYDANTIC,
        tags=frozenset({"planner", "reasoning"}),
        description=("Given a high-level objective, decompose it into 3–12 ordered steps, each with a concrete tool the executor can run."),
        text=(
            "You are Noesis Planner.  Produce a detailed execution plan to "
            "achieve the user's objective.\n\n"
            "Objective: {objective}\n"
            "User context: {context}\n"
            "Maximum allowed steps: {max_steps}\n\n"
            "Output rules\n"
            "------------\n"
            "Return STRICTLY a JSON object matching this JSONSchema:\n"
            "{json_schema}\n\n"
            "Each step description MUST be a full English sentence.\n"
            "If the objective requires research, insert a research step BEFORE "
            "the build / coding steps.  If the objective is already small enough, "
            "emit 1–3 steps and set the plan's summary accordingly."
        ),
    )
)

# --- Researcher ------------------------------------------------------------

registry.register(
    PromptTemplate(
        name="research.draft_queries",
        output_kind=OutputKind.JSON,
        tags=frozenset({"research", "search"}),
        description="Turn a research topic into 3-8 Web search / RAG queries.",
        text=(
            "You are Noesis Research Agent.  For the topic below, propose "
            "{query_count} search queries.  Phrase each as a precise natural-language "
            "question.\n\n"
            "Topic: {topic}\n"
            "Existing knowledge: {prior_knowledge}\n\n"
            "Return a JSON array of strings."
        ),
    )
)

# --- Coder -----------------------------------------------------------------

registry.register(
    PromptTemplate(
        name="coder.implement_plan_step",
        output_kind=OutputKind.PYDANTIC,
        tags=frozenset({"coder", "execution"}),
        description="Given one plan step, emit a list of file-level edits.",
        text=(
            "You are Noesis Coder.  Implement plan step #{step_index} below.  "
            "Produce a list of edits — each edit must be one of: CREATE_FILE, "
            "EDIT_FILE (with exact replacement), RUN_COMMAND, RENAME_FILE.\n\n"
            "Full objective: {objective}\n"
            "Step #{step_index}: {step_description}\n"
            "Files already available (use their contents from tool results, do not "
            "ask the user):\n{file_list}\n\n"
            "Output JSONSchema:\n{json_schema}"
        ),
    )
)

# --- Critic ---------------------------------------------------------------

registry.register(
    PromptTemplate(
        name="critic.review_response",
        output_kind=OutputKind.JSON,
        tags=frozenset({"critic", "quality"}),
        description="Given a candidate agent output, grade correctness + list flaws.",
        text=(
            "You are Noesis Critic.  Grade the candidate response below against "
            "the rubric.  Be harsh — if the response makes unsupported claims, "
            "mark it down.  If the code would not compile, mark it down.\n\n"
            "Rubric: {rubric}\n"
            "Original task: {objective}\n"
            "Candidate response:\n{candidate}\n\n"
            "Return JSON: {score: int 0..10, flaws: string[], suggested_fix: string}"
        ),
    )
)

# --- Judge ----------------------------------------------------------------

registry.register(
    PromptTemplate(
        name="judge.choose_best_response",
        output_kind=OutputKind.JSON,
        tags=frozenset({"judge", "ranking"}),
        description="Given N candidate answers, pick the best and explain the ranking.",
        text=(
            "You are Noesis Judge.  Read the following {count} candidate answers "
            "to the same question and rank them from best to worst.\n\n"
            "Question: {objective}\n"
            "Candidates:\n{candidates}\n\n"
            "Return JSON: {ranking: [0..{last_idx}], explanation: string, winner_score: 0..10}"
        ),
    )
)


__all__ = ["OutputKind", "PromptRegistry", "PromptTemplate", "registry"]
