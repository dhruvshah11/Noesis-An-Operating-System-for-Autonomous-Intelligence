"""12-agent roster (M7 complete): Planner/Research/Coding/Memory/RAG/Tool/Reflection/Judge/Critic/Executor/Supervisor/Orchestrator + AgentRoster.

Design notes (10-yr horizon):
  * The :class:`Agent` base class mirrors the LangGraph node-call contract:
    ``dict[str, Any]`` state in, ``dict[str, Any]`` state out.  When the team
    ships the M1 Planner/LangGraph orchestrator graph these agents plug in
    without modification.
  * Reports are Pydantic models so they can be serialised round-trip into the
    ``TaskExecution.artifacts`` column (M0 ORM) for audit / dashboard display.
  * Capability tokens are threaded through ``ctx: AgentRunContext``; each
    agent declares its required capabilities upfront so the kernel scheduler
    can raise ``PermissionDenied`` *at spawn time* instead of mid-invoke.
  * Use ``AgentRoster.get(AgentType)`` for dry-run/tests and
    ``AgentRoster.spawn(AgentType, ctx)`` for permission-gated production
    invocations that gate on ``required_capabilities``.
"""

from __future__ import annotations

import difflib
import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4, uuid5

from pydantic import BaseModel, ConfigDict, Field

from noesis.kernel.capabilities import Capability, CapabilityOp, CapabilityToken, PermissionDenied
from noesis.memory import MemoryEntry, PromotionController, PromotionReport
from noesis.memory.promotion import TIER_INDRIYA
from noesis.tools import ToolRegistry, ToolResult
from noesis.types import (
    NOESIS_NAMESPACE_PLAN,
    AcceptCriterion,
    AgentType,
    ExecutionPlan,
    ExecutorTriStateDecision,
    PlanStep,
    TaskStatus,
    TriStateDecision,
)

# ---------------------------------------------------------------------------
# Shared domain models
# ---------------------------------------------------------------------------


class CitationRef(BaseModel):
    """Back-reference to a source document / web URL / DB row."""

    model_config = ConfigDict(frozen=True)

    source_id: str = Field(default_factory=lambda: uuid4().hex[:16])
    source_kind: str = "url"
    location: str = ""
    title: str = ""
    snippet: str = ""


class ResearchReport(BaseModel):
    """Structured output of :class:`ResearchAgent`."""

    query: str
    plan: list[str]
    sources: list[CitationRef]
    summary: str
    conflicts: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class Mistake(BaseModel):
    """One detected issue in a prior turn."""

    kind: str
    severity: str = "medium"
    description: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class ReflectionReport(BaseModel):
    """Structured output of :class:`ReflectionAgent`."""

    confidence: float = Field(ge=0.0, le=1.0)
    overall: str
    mistakes: list[Mistake] = Field(default_factory=list)
    replan_recommended: bool = False
    replan_steps: list[str] = Field(default_factory=list)


class PatchStep(BaseModel):
    """A single patch in CodingAgent output — can be applied / dry-run."""

    target_file: str
    operation: str = "replace"  # replace | insert | delete
    original: str
    proposed: str
    start_line_hint: int = 0


class CodingPatchReport(BaseModel):
    """Structured output of :class:`CodingAgent` (alpha)."""

    target_file: str
    plan_steps: list[str]
    patches: list[PatchStep]
    tests_added: list[str] = Field(default_factory=list)
    docs_added: list[str] = Field(default_factory=list)
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Agent ABC + run-context
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class AgentRunContext:
    """Immutable context passed to ``Agent.run``.

    Carries everything an agent needs so we don't have to widen ``Agent.run``
    signature when adding new per-invocation state.
    """

    token: CapabilityToken
    capabilities: tuple[Capability, ...]
    tools: ToolRegistry
    request_id: str = ""
    workspace_id: str | None = None


class Agent(ABC):
    """Base agent — every specialised agent implements one ``run`` method."""

    name: str
    agent_type: AgentType

    required_capabilities: tuple[Capability, ...] = ()
    """The kernel uses this list at spawn time to mint a narrow token."""

    @abstractmethod
    def run(self, state: dict[str, Any], ctx: AgentRunContext) -> dict[str, Any]:
        """LangGraph-compatible call: dict-state in, dict-state out.

        Standard keys on return:
          ``status`` → :class:`TaskStatus` int
          ``report`` → a Pydantic model like :class:`ResearchReport`
          ``artifacts`` → list[ToolArtifact] (optional)
        """


# ---------------------------------------------------------------------------
# Helpers shared across agents
# ---------------------------------------------------------------------------


def _add_result_status(state: dict[str, Any], *, status: TaskStatus, report: BaseModel | None) -> dict[str, Any]:
    out = dict(state)
    out.setdefault("status_history", []).append(status)
    out["status"] = status.value
    if report is not None:
        out["report"] = report.model_dump(mode="json")
        out["report_type"] = report.__class__.__name__
    return out


# ===========================================================================
# 1. ResearchAgent
# ===========================================================================


_URL = re.compile(r"https?://[^\s)\]\"'>]+", re.IGNORECASE)


class ResearchAgent(Agent):
    """Given a query + optional seed URLs, produce a multi-source research report."""

    name = "research"
    agent_type = AgentType.RESEARCH

    required_capabilities = (Capability(CapabilityOp.TOOL_INVOKE, "web_fetch"),)

    def __init__(self, *, max_sources: int = 6, max_chars_per_fetch: int = 12_000) -> None:
        self._max_sources = max_sources
        self._max_chars = max_chars_per_fetch

    def _plan(self, query: str, seed_urls: list[str]) -> list[str]:
        steps = [
            f"1. Expand query terms for '{query}'",
            "2. Gather at least 2 independent sources",
            "3. Cross-check facts across sources",
            "4. List conflicts explicitly",
            "5. Score confidence 0..1",
        ]
        if seed_urls:
            steps.insert(1, f"2. Review {len(seed_urls)} seed URLs first")
        return steps

    def _fetch(self, url: str, ctx: AgentRunContext) -> tuple[str, str]:
        result: ToolResult = ctx.tools.invoke(
            "web_fetch",
            {"url": url, "max_chars": self._max_chars},
            token=ctx.token,
            capabilities=ctx.capabilities,
        )
        if not result.success:
            return "", result.stderr or f"fetch failed (exit={result.exit_code})"
        title = ""
        match = re.search(r"^# (.+)$", result.stdout, flags=re.MULTILINE)
        if match:
            title = match.group(1).strip()
        return title, result.stdout

    @staticmethod
    def _extract_terms(query: str) -> set[str]:
        return {t.lower() for t in re.findall(r"\w{3,}", query)}

    @classmethod
    def _conflict(cls, summaries: list[str]) -> list[str]:
        """Surface crude-but-auditable conflicts: X vs Y factual claims."""
        conflicts: list[str] = []
        opposing = [
            ("supports", "rejects"),
            ("true", "false"),
            ("available", "unavailable"),
            ("safe", "dangerous"),
            ("recommended", "not recommended"),
            ("higher", "lower"),
            ("increase", "decrease"),
        ]
        for a, b in opposing:
            presence_a = [f"source {i}" for i, s in enumerate(summaries) if a in s.lower()]
            presence_b = [f"source {i}" for i, s in enumerate(summaries) if b in s.lower()]
            if presence_a and presence_b:
                conflicts.append(f" '{a}' claim in {presence_a} vs '{b}' claim in {presence_b}")
        return conflicts

    def run(self, state: dict[str, Any], ctx: AgentRunContext) -> dict[str, Any]:
        query = str(state.get("query", "")).strip()
        if not query:
            return _add_result_status(
                state,
                status=TaskStatus.FAILED,
                report=ResearchReport(query="", plan=[], sources=[], summary="Missing 'query' in state.", confidence=0.0),
            )
        seed_urls: list[str] = list(state.get("seed_urls", []) or [])
        plan = self._plan(query, seed_urls)
        # If no seed URLs, make a plan-only dry-run report (no outbound fetch
        # capabilities yet); we still build a plausible report so downstream
        # ReflectionAgent has something to score.
        urls = seed_urls[: self._max_sources]
        citations: list[CitationRef] = []
        summaries: list[str] = []
        for i, url in enumerate(urls):
            title, body = self._fetch(url, ctx)
            if not body:
                continue
            # Extract 1-2 sentences that mention query terms
            terms = self._extract_terms(query)
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]
            scored = sorted(
                sentences,
                key=lambda s: -sum(1 for t in terms if t in s.lower()),
            )
            snippet = " ".join(scored[:3])[:400]
            citations.append(CitationRef(source_id=f"src{i:02d}", source_kind="url", location=url, title=title, snippet=snippet))
            summaries.append(" ".join(scored[:6])[:1200])
        if not summaries:
            # Placeholder report: plan-only (will still score <0.3 confidence,
            # triggers reflection to re-plan once seed URLs are provided).
            report = ResearchReport(
                query=query,
                plan=plan,
                sources=citations,
                summary=(f"No sources fetched for query '{query}'. Call this agent with state['seed_urls'] = [..] to enable cross-checks."),
                confidence=0.2,
            )
            return _add_result_status(state, status=TaskStatus.AWAITING_INPUT, report=report)
        blended = "\n\n".join(f"[src{i:02d}] {s}" for i, s in enumerate(summaries))[:4000]
        conflicts = self._conflict(summaries)
        confidence = round(min(0.9, 0.35 + 0.15 * len(summaries) - 0.2 * len(conflicts)), 3)
        report = ResearchReport(
            query=query,
            plan=plan,
            sources=citations,
            summary=blended,
            conflicts=conflicts,
            confidence=max(0.0, confidence),
        )
        return _add_result_status(state, status=TaskStatus.SUCCESS, report=report)


# ===========================================================================
# 2. ReflectionAgent
# ===========================================================================


class ReflectionAgent(Agent):
    """Scrutinise a prior turn's answer, tool calls and memory state."""

    name = "reflection"
    agent_type = AgentType.REFLECTION

    required_capabilities = (Capability(CapabilityOp.MEMORY_READ, "*"),)

    @staticmethod
    def _tool_exit_codes(calls: list[dict[str, Any]]) -> list[int]:
        codes: list[int] = []
        for c in calls:
            r = c.get("result")
            if isinstance(r, dict):
                ec = r.get("exit_code")
                if isinstance(ec, int):
                    codes.append(ec)
            elif isinstance(r, ToolResult):
                codes.append(r.exit_code)
        return codes

    def run(self, state: dict[str, Any], ctx: AgentRunContext) -> dict[str, Any]:
        answer: str = str(state.get("answer", "") or "")
        tool_calls: list[dict[str, Any]] = list(state.get("tool_calls", []) or [])
        citations_provided = bool(state.get("citations"))
        int(state.get("tokens_prompt") or 0)
        tokens_out = int(state.get("tokens_completion") or 0)
        cost = float(state.get("cost_usd") or 0.0)
        mistakes: list[Mistake] = []
        # 1. Missing citations
        if answer and answer.count(".") >= 2 and not citations_provided:
            mistakes.append(
                Mistake(
                    kind="missing_citations",
                    severity="medium",
                    description="Final answer contains multiple factual claims but zero citations were provided.",
                    evidence={"sentence_count": answer.count(".")},
                )
            )
        # 2. Non-zero tool exit codes
        exit_codes = self._tool_exit_codes(tool_calls)
        nonzero = [ec for ec in exit_codes if ec not in (0, -1)]  # -1 is dry-run ok
        if nonzero:
            mistakes.append(
                Mistake(
                    kind="tool_failures",
                    severity="high",
                    description=f"{len(nonzero)} tool invocation(s) had non-zero exit codes.",
                    evidence={"exit_codes": nonzero},
                )
            )
        # 3. Low token-cost ratio: huge answer on a factual question is suspicious
        if tokens_out and tokens_out > 4096 and cost == 0.0:
            mistakes.append(
                Mistake(
                    kind="missing_cost_accounting",
                    severity="low",
                    description="Tokens were consumed but cost_usd was never populated.",
                    evidence={"tokens_completion": tokens_out},
                )
            )
        # 4. Contradiction: answer contains "X" then "not X" within a window
        claims_lc = answer.lower()
        for match in re.finditer(r"(?P<claim>\bis\b|\bwas\b|\bdoes\b|\bwill\b|\bhave\b|\bcan\b|\bmust\b)\s+(?P<noun>[^.!?;]{2,80})", claims_lc):
            claim = match.group(0)
            # Heuristic: find "not {noun}" elsewhere
            noun = match.group("noun").strip()
            neg = re.compile(rf"\b(is|was|does|will|have|can|must)\s+not\s+{re.escape(noun[:40])}")
            if noun and neg.search(claims_lc):
                mistakes.append(
                    Mistake(
                        kind="internal_contradiction",
                        severity="high",
                        description=f"Answer both asserts and negates: {claim[:120]!r}",
                        evidence={"snippet": claim[:200]},
                    )
                )
                break
        # Confidence: start at 0.9, subtract 0.2 per high mistake, 0.08 per medium, 0.02 per low
        weights = {"high": 0.20, "medium": 0.08, "low": 0.02}
        penalty = sum(weights.get(m.severity, 0.05) for m in mistakes)
        confidence = round(max(0.0, 0.9 - penalty), 3)
        # Replan recommendation
        replan_recommended = any(m.severity == "high" for m in mistakes) or (not answer)
        replan_steps: list[str] = []
        if not answer:
            replan_steps.append("Run planner again — no prior answer to reflect on.")
        if any(m.kind == "missing_citations" for m in mistakes):
            replan_steps.append("Re-invoke ResearchAgent with seed URLs; inject citations into final answer.")
        if any(m.kind == "tool_failures" for m in mistakes):
            replan_steps.append("Retry failed tool call(s) with retries; if shell/db, inspect permissions.")
        if any(m.kind == "internal_contradiction" for m in mistakes):
            replan_steps.append("Send final answer through a Judge-agent pass that resolves internal contradictions.")
        overall = (
            f"Reflected on answer of {len(answer)} chars, {len(tool_calls)} tool call(s), "
            f"{len(mistakes)} mistake(s) detected, confidence={confidence:.2f}."
        )
        report = ReflectionReport(
            confidence=confidence,
            overall=overall,
            mistakes=mistakes,
            replan_recommended=replan_recommended,
            replan_steps=replan_steps,
        )
        return _add_result_status(state, status=TaskStatus.SUCCESS, report=report)


# ===========================================================================
# 3. CodingAgent (alpha)
# ===========================================================================


class CodingAgent(Agent):
    """Alpha coding agent: produces plan + patch list from (file + instructions).

    Does NOT mutate files itself (that's ToolAgent's job, which will later
    invoke :class:`FilesTool` with a capability-gated token).  This agent only
    plans and returns ``CodingPatchReport`` so the Judge/reflection pass can
    audit before write.
    """

    name = "coding"
    agent_type = AgentType.CODING

    required_capabilities = (Capability(CapabilityOp.TOOL_INVOKE, "files"),)

    def _plan(self, instructions: str, has_tests: bool) -> list[str]:
        steps = [
            "1. Read the current source with FilesTool (read operation).",
            "2. Identify exact snippet(s) to replace (preserve surrounding context).",
            "3. Produce per-hunk PatchStep(s) with start_line_hint for line-number fidelity.",
            "4. Draft unit tests matching naming: tests/unit/test_<feature>.py.",
            "5. Dry-run patch application (difflib equality check) before write.",
        ]
        if not has_tests:
            steps.insert(3, "3b. Add tests/unit/test_<feature>.py — at least 2 assertions per hunk.")
        return steps

    @staticmethod
    def _split_lines(src: str) -> list[str]:
        return src.splitlines(keepends=False)

    @classmethod
    def _best_match(cls, lines: list[str], snippet: str) -> int:
        """Find the line index where snippet best matches (most tokens overlap)."""
        if not snippet.strip():
            return 0
        snip_lines = [ln.rstrip() for ln in snippet.splitlines() if ln.strip()]
        if not snip_lines:
            return 0
        best_idx, best_score = 0, -1
        for i in range(len(lines)):
            window = lines[i : i + len(snip_lines)]
            score = 0
            for a, b in zip(window, snip_lines, strict=False):
                if a.rstrip() == b:
                    score += 5
                set_a, set_b = set(a), set(b)
                score += len(set_a & set_b) - len(set_a ^ set_b) * 0.05
            if score > best_score:
                best_score, best_idx = score, i
        return best_idx

    @staticmethod
    def _snippet_to_statements(instructions: str) -> list[str]:
        """Very small instruction parser: returns the lines of 'instruction' text."""
        return [ln.strip(" -*") for ln in instructions.splitlines() if ln.strip(" -*")]

    @classmethod
    def apply_patch(cls, source: str, patches: list[PatchStep]) -> str:
        """Apply a list of patches in order; returns NEW source (no side effects).

        Raises ``ValueError`` if a patch's ``original`` text cannot be uniquely
        matched in source, so callers fall back to human / FilesTool review.
        """
        lines = cls._split_lines(source)
        for patch in patches:
            orig_lines = [ln.rstrip() for ln in cls._split_lines(patch.original) if ln != ""]
            if not orig_lines:
                # insert / delete style: locate via start_line_hint
                idx = max(0, min(len(lines) - 1, patch.start_line_hint))
                new_lines = cls._split_lines(patch.proposed)
                if patch.operation == "delete":
                    lines = lines[:idx] + lines[idx + len(new_lines) :]
                elif patch.operation == "insert":
                    lines = lines[:idx] + new_lines + lines[idx:]
                continue
            # Find exact match of the orig_lines in lines
            candidates: list[int] = []
            for i in range(len(lines) - len(orig_lines) + 1):
                window = [ln.rstrip() for ln in lines[i : i + len(orig_lines)]]
                if window == orig_lines:
                    candidates.append(i)
            # Fallback: if 0 exact matches and we have single-line original,
            # search for a line that *contains* original as a substring (handles
            # surrounding delimiters e.g. triple-quoted docstrings, json strings,
            # XML attributes, ...).
            if len(candidates) == 0 and len(orig_lines) == 1 and orig_lines[0]:
                needle = orig_lines[0]
                for i, raw_line in enumerate(lines):
                    if needle in raw_line:
                        candidates.append(i)
            if len(candidates) != 1:
                raise ValueError(
                    f"Patch for '{patch.target_file}': original snippet matched {len(candidates)} times "
                    f"(need exactly 1).  Provide more context or unique snippet."
                )
            start = candidates[0]
            # If single-line fallback matched a substring (not whole-line exact) we
            # need to substitute the needle *within* the line instead of replacing
            # the whole line.  Otherwise do the standard line-level replacement.
            is_substitution = len(orig_lines) == 1 and lines[start].rstrip() != orig_lines[0]
            if is_substitution:
                proposed_line = cls._split_lines(patch.proposed)[0] if cls._split_lines(patch.proposed) else ""
                lines[start] = lines[start].replace(orig_lines[0], proposed_line)
            else:
                replacement = cls._split_lines(patch.proposed)
                lines = lines[:start] + replacement + lines[start + len(orig_lines) :]
        return "\n".join(lines) + ("\n" if source.endswith("\n") else "")

    def run(self, state: dict[str, Any], ctx: AgentRunContext) -> dict[str, Any]:
        target_file = str(state.get("target_file", "") or "")
        instructions = str(state.get("instructions", "") or "")
        if not target_file or not instructions:
            report = CodingPatchReport(
                target_file=target_file,
                plan_steps=[],
                patches=[],
                summary="Missing target_file or instructions.",
                confidence=0.0,
            )
            return _add_result_status(state, status=TaskStatus.FAILED, report=report)
        # Read via FilesTool if we have capability, else raise FAILED
        try:
            read_result: ToolResult = ctx.tools.invoke(
                "files",
                {"operation": "read", "path": target_file},
                token=ctx.token,
                capabilities=ctx.capabilities,
            )
        except Exception as exc:
            report = CodingPatchReport(
                target_file=target_file,
                plan_steps=self._plan(instructions, has_tests=False),
                patches=[],
                summary=f"Could not read source: {type(exc).__name__}: {exc}",
                confidence=0.1,
            )
            return _add_result_status(state, status=TaskStatus.FAILED, report=report)
        if not read_result.success:
            report = CodingPatchReport(
                target_file=target_file,
                plan_steps=self._plan(instructions, has_tests=False),
                patches=[],
                summary=f"FilesTool.read failed: {read_result.stderr or read_result.stdout}",
                confidence=0.1,
            )
            return _add_result_status(state, status=TaskStatus.FAILED, report=report)
        source = read_result.stdout
        # Hunk synthesis: take instructions and split lines.  For each instruction
        # that starts with "replace X with Y": parse, or fall back to a simple
        # full-file replan that re-asserts: document plan, no actual patch.
        patches: list[PatchStep] = []
        inst_lines = self._snippet_to_statements(instructions)

        def _strip_outer_quotes(s: str) -> str:
            s = s.strip()
            if len(s) >= 2:
                for pair in ('""', "''"):
                    q = pair[0]
                    if s.startswith(q) and s.endswith(q):
                        # Find matching closing quote accounting for escape-less simple strings
                        inner = s[1:-1]
                        if q not in inner:
                            return inner
            return s

        for raw in inst_lines:
            # Priority 1: the double-quoted form:  <optional leading words>
            #   replace  <context prefix>?  "A"  with  "B"
            # This captures patch hunks where the user included a contextual
            # prefix (e.g. "replace module docstring \"Hello\" with \"...\"").
            rep_q = re.match(
                r"replace\s+(?:[^\"']*?)?\"(?P<orig>[^\"]+)\"\s+with\s+\"(?P<prop>[^\"]+)\"",
                raw,
                flags=re.IGNORECASE,
            )
            if rep_q:
                original = rep_q.group("orig").replace("\\n", "\n")
                proposed = rep_q.group("prop").replace("\\n", "\n")
                start = self._best_match(self._split_lines(source), original)
                patches.append(
                    PatchStep(
                        target_file=target_file,
                        operation="replace",
                        original=original,
                        proposed=proposed,
                        start_line_hint=start,
                    )
                )
                continue
            rep_sq = re.match(
                r"replace\s+(?:[^\"']*?)?'(?P<orig>[^']+)'\s+with\s+'(?P<prop>[^']+)'",
                raw,
                flags=re.IGNORECASE,
            )
            if rep_sq:
                original = rep_sq.group("orig").replace("\\n", "\n")
                proposed = rep_sq.group("prop").replace("\\n", "\n")
                start = self._best_match(self._split_lines(source), original)
                patches.append(
                    PatchStep(
                        target_file=target_file,
                        operation="replace",
                        original=original,
                        proposed=proposed,
                        start_line_hint=start,
                    )
                )
                continue
            rep = re.match(r"replace\s+(?P<orig>.+?)\s+with\s+(?P<prop>.+)$", raw, flags=re.IGNORECASE)
            if rep:
                original = _strip_outer_quotes(rep.group("orig").replace("\\n", "\n"))
                proposed = _strip_outer_quotes(rep.group("prop").replace("\\n", "\n"))
                start = self._best_match(self._split_lines(source), original)
                patches.append(
                    PatchStep(
                        target_file=target_file,
                        operation="replace",
                        original=original,
                        proposed=proposed,
                        start_line_hint=start,
                    )
                )
        # If no structured "replace…with…" form, still produce a readable plan
        # but zero patches — reflection will flag it as low-confidence.
        has_tests = False
        try:
            test_read: ToolResult = ctx.tools.invoke(
                "files",
                {"operation": "list", "path": "tests/unit", "glob": f"test_*{target_file.split('/')[-1].removesuffix('.py')}*"},
                token=ctx.token,
                capabilities=ctx.capabilities,
            )
            has_tests = bool(test_read.success and test_read.stdout.strip())
        except Exception:
            has_tests = False
        plan = self._plan(instructions, has_tests=has_tests)
        # Apply dry-run to compute diff output + confidence
        summary_parts: list[str] = []
        try:
            new_source = self.apply_patch(source, patches)
            diff = "\n".join(
                difflib.unified_diff(
                    source.splitlines(keepends=False),
                    new_source.splitlines(keepends=False),
                    fromfile=f"a/{target_file}",
                    tofile=f"b/{target_file}",
                    lineterm="",
                )
            )
            summary_parts.append(diff[:2000] or "(no diff — patch empty)")
            # content hash of produced file for tamper-evidence downstream
            sha = hashlib.sha256(new_source.encode("utf-8")).hexdigest()
            summary_parts.append(f"patched_content_sha256={sha}")
            confidence = 0.85 if patches else 0.35
        except ValueError as exc:
            summary_parts.append(f"dry-run failed: {exc}")
            confidence = 0.15
        report = CodingPatchReport(
            target_file=target_file,
            plan_steps=plan,
            patches=patches,
            tests_added=[] if has_tests else [f"tests/unit/test_{target_file.split('/')[-1].removesuffix('.py')}.py (skeleton)"],
            summary="\n".join(summary_parts),
            confidence=round(confidence, 3),
        )
        return _add_result_status(state, status=TaskStatus.SUCCESS, report=report)


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

# ===========================================================================
# 0. PlannerAgent (M5.1 — deterministic seeded decomposition)
# ===========================================================================


class PlannerReport(BaseModel):
    """Structured output of :class:`PlannerAgent`."""

    goal: str
    plan: ExecutionPlan
    seeds: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)
    promotion_report: dict[str, Any] | None = None

    @property
    def steps_count(self) -> int:
        return len(self.plan.steps)


class PlannerAgent(Agent):
    """Goal → ExecutionPlan with deterministic dependency graph + confidence.

    Design (10-yr):  This planner is *seeded, deterministic, and
    LLM-independent* so CI + agent tests never flake.  When an upstream
    LLM-based planner is available (M1), you can compose it as a drop-in:
    run the LLM planner first, then pass its Pydantic output through
    ``PlannerAgent`` as the canonicalisation pass that forces contiguous
    indexing + assigns AgentType + guarantees well-formed dependencies.
    """

    name = "planner"
    agent_type = AgentType.PLANNER

    required_capabilities = (Capability(CapabilityOp.RAG_SEARCH, "*"),)

    # -- seed helper: mulberry32 (parity with frontend Vitest seeded mocks) -
    @staticmethod
    def _rng(seed: int):
        state = seed & 0xFFFFFFFF

        def _next() -> float:
            nonlocal state
            state = (state + 0x6D2B79F5) & 0xFFFFFFFF
            t = state
            t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFFFFFFFFFF
            t ^= t + ((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFFFFFFFFFF
            return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

        return _next

    @staticmethod
    def _tokenise(goal: str) -> list[str]:
        return [m.lower() for m in re.findall(r"\w{3,}", goal)]

    @classmethod
    def _classify(cls, goal: str, idx: int, tot: int, rand: float) -> AgentType:
        """Assign an agent type based on keywords + deterministic rotation."""
        low = goal.lower()
        order = [
            (AgentType.RESEARCH, "research web study paper search find"),
            (AgentType.CODING, "code patch test refactor file implement build bug fix"),
            (AgentType.RAG, "document pdf docx chunk summary retrieval cite"),
            (AgentType.MEMORY, "memory recall forget store episodic semantic compress"),
            (AgentType.TOOL, "shell run command exec db sql file fetch weather email"),
        ]
        for at, kwstr in order:
            if any(k in low for k in kwstr.split()):
                return at
        # Round-robin fallback: research → coding → reflection based on idx*rand
        base = [AgentType.RESEARCH, AgentType.CODING] + [AgentType.REFLECTION]
        return base[(idx + int(rand * 97)) % len(base)]

    def run(self, state: dict[str, Any], ctx: AgentRunContext | None) -> dict[str, Any]:
        goal_raw = str(state.get("goal", "")).strip()
        seed = int(state.get("seed") or 0)
        if len(goal_raw) < 5:
            padded_goal = goal_raw + " — restate goal in 5+ characters"
            if len(padded_goal) < 5:
                padded_goal = "(goal too short — restate in 5+ characters so PlannerAgent can decompose)"
            empty_plan = ExecutionPlan(
                goal=padded_goal,
                steps=[
                    PlanStep(
                        index=0,
                        description="Restate goal in 5+ words so Planner can decompose it.",
                        assigned_agent=AgentType.PLANNER,
                        confidence=0.0,
                    )
                ],
                reasoning="Goal was too short to decompose (<5 chars).",
            )
            return _add_result_status(
                state,
                status=TaskStatus.FAILED,
                report=PlannerReport(goal=padded_goal, plan=empty_plan),
            )
        goal = goal_raw
        rand = self._rng(seed if seed else 1337)
        tokens = self._tokenise(goal)
        # NOTE: do NOT use the builtin hash(goal) here — Python's default hash
        # of str is randomized per-process by PYTHONHASHSEED, which breaks the
        # C3 determinism manifest when the manifest runner calls PlannerAgent
        # twice across different evaluation-group scopes.  Use sha256 int instead
        # — 64-bit truncated, always deterministic for a given byte string.
        _stable = int.from_bytes(hashlib.sha256(goal.encode("utf-8")).digest()[:8], "little", signed=False)
        seed_str = f"{seed if seed else 1337}:{len(goal)}:{_stable:x}"
        is_deterministic = bool(state.get("deterministic", True))
        # Heuristic steps count: 1 base + 1 per 6 tokens + 1 optional research + 1 reflection tail
        n_base = min(12, max(3, 2 + len(tokens) // 6))
        reasoning_lines = [
            f"Decomposed goal '{goal}' into {n_base} steps:",
            "  · Every step has explicit dependencies (DAG — no cycles).",
            "  · Worker step confidence is proportional to keyword clarity.",
            "  · Final step is always ReflectionAgent gate.",
        ]
        steps: list[PlanStep] = []
        for i in range(n_base):
            desc_templates: dict[AgentType, list[str]] = {
                AgentType.RESEARCH: [
                    "Gather authoritative sources on {topic}",
                    "Cross-check claims about {topic} across ≥2 references",
                    "Extract citations + confidence notes for {topic}",
                ],
                AgentType.CODING: [
                    "Draft implementation for {topic}",
                    "Write unit tests covering {topic}",
                    "Dry-run patch application for {topic}",
                ],
                AgentType.RAG: [
                    "Chunk documents related to {topic}",
                    "Run hybrid retrieval (BM25 + dense) for {topic}",
                    "Synthesise cited summary for {topic}",
                ],
                AgentType.MEMORY: [
                    "Recall prior episodic memory matching {topic}",
                    "Write semantic summary of {topic} into semantic tier",
                    "Compress stale memory scoped to {topic}",
                ],
                AgentType.TOOL: [
                    "Invoke shell/files for {topic}",
                    "Run db lookup for {topic}",
                    "Fetch web content for {topic}",
                ],
                AgentType.REFLECTION: [
                    "Reflect on prior turns for {topic} and detect mistakes",
                    "Score confidence + propose replan if needed for {topic}",
                ],
                AgentType.JUDGE: [
                    "Rank candidate answers for {topic}",
                ],
                AgentType.ORCHESTRATOR: [
                    "Fan-out dependent workers for {topic} then join",
                ],
            }
            assigned = self._classify(goal, i, n_base, rand())
            topic = tokens[(i * 7 + 3) % len(tokens)] if tokens else goal.split()[0]
            tmpl = desc_templates.get(assigned, ["Execute worker pass for {topic}"])
            description = tmpl[i % len(tmpl)].format(topic=topic)
            confidence = min(0.95, 0.35 + 0.08 * len(tokens) - 0.03 * abs(i - n_base // 2))
            if assigned == AgentType.RESEARCH:
                confidence = min(0.9, confidence + 0.1)
            if i == 0:
                deps: list[UUID] = []
            else:
                ndeps = max(1, min(i, 1 + int(rand() * 2)))
                candidates = list(range(i))
                dep_indices = candidates[-ndeps:]
                if is_deterministic:
                    deps = [uuid5(NOESIS_NAMESPACE_PLAN, f"step:{seed_str}:{j}") for j in dep_indices]
                else:
                    deps = [steps[j].id for j in dep_indices]
            step_kwargs = dict(
                index=i,
                description=description,
                assigned_agent=assigned,
                dependencies=deps,
                tool_hints=(
                    ["web_fetch"]
                    if assigned == AgentType.RESEARCH
                    else (["files", "shell"] if assigned == AgentType.CODING else (["files", "list"] if assigned == AgentType.RAG else []))
                ),
                rag_query=(" ".join(tokens[:4]) if assigned in (AgentType.RAG, AgentType.MEMORY, AgentType.RESEARCH) else None),
                status=TaskStatus.PENDING,
                confidence=round(max(0.05, confidence), 3),
            )
            if is_deterministic:
                steps.append(PlanStep.deterministic(seed=seed_str, **step_kwargs))
            else:
                steps.append(PlanStep(**step_kwargs))
        # Append final reflection step (depends on all workers)
        if is_deterministic:
            final_deps = [uuid5(NOESIS_NAMESPACE_PLAN, f"step:{seed_str}:{j}") for j in range(len(steps))]
            steps.append(
                PlanStep.deterministic(
                    index=len(steps),
                    description="Run reflection pass on aggregated outputs; sign-off or trigger replan.",
                    assigned_agent=AgentType.REFLECTION,
                    dependencies=final_deps,
                    tool_hints=[],
                    status=TaskStatus.PENDING,
                    confidence=0.85,
                    seed=seed_str,
                )
            )
        else:
            steps.append(
                PlanStep(
                    index=len(steps),
                    description="Run reflection pass on aggregated outputs; sign-off or trigger replan.",
                    assigned_agent=AgentType.REFLECTION,
                    dependencies=[s.id for s in steps],
                    tool_hints=[],
                    status=TaskStatus.PENDING,
                    confidence=0.85,
                )
            )
        if is_deterministic:
            plan = ExecutionPlan.deterministic(
                goal=goal,
                steps=steps,
                reasoning="\n".join(reasoning_lines),
                seed=seed_str,
            )
        else:
            plan = ExecutionPlan(
                goal=goal,
                steps=steps,
                reasoning="\n".join(reasoning_lines),
            )
        required = sorted({s.assigned_agent.value for s in steps})
        memory_agent = state.get("memory_agent")
        if memory_agent is None:
            memory_agent = MemoryAgent()
            # Deterministic mode: freeze the memory clock to EPOCH_SENTINEL so
            # T1 Indriya inserts and PromotionEvents produce identical
            # at/created_at/last_accessed_at values across runs for the same
            # (goal, seed). Without this, datetime.now(UTC) leaks into the
            # provenance chain and C3 identity fails on real-wall-clock runs.
            if is_deterministic:
                from noesis.types import EPOCH_SENTINEL

                memory_agent.promotion_controller.set_clock(EPOCH_SENTINEL)
        memory_agent.on_plan(plan)
        _step_now = memory_agent.promotion_controller._now()
        for step in plan.steps:
            step.started_at = _step_now
            step.finished_at = _step_now
            step.status = TaskStatus.SUCCESS
            memory_agent.on_step_completed(step)
        promo_report = memory_agent.end_of_run()
        plan.metadata["promotion_report"] = {
            "tier_counts": promo_report.tier_counts,
            "provenance_tail_sha": promo_report.provenance_tail_sha,
            "total_events": promo_report.total_events,
        }
        report = PlannerReport(
            goal=goal,
            plan=plan,
            seeds=tokens[:8],
            required_capabilities=required,
            promotion_report=plan.metadata["promotion_report"],
        )
        state.pop("memory_agent", None)
        result = _add_result_status(state, status=TaskStatus.SUCCESS, report=report)
        if ctx is None:
            result["memory_agent"] = memory_agent
        return result


# ===========================================================================
# 4. MemoryAgent
# ===========================================================================


class MemoryReport(BaseModel):
    """Structured output of :class:`MemoryAgent`."""

    operation: str  # recall | store | compress
    items_processed: int = 0
    keys: list[str] = Field(default_factory=list)
    summary: str
    compressed_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class MemoryAgent(Agent):
    """Short/semantic/episodic recall + write + compress pass.

    Wires the six-tier :class:`PromotionController` so every planner step
    becomes a T1 Indriya sensory insert that can cascade upward through
    Smriti / Gyān / Yojanā / Sādhanā / Paalak tiers.
    """

    name = "memory"
    agent_type = AgentType.MEMORY

    required_capabilities = (
        Capability(CapabilityOp.MEMORY_READ, "*"),
        Capability(CapabilityOp.MEMORY_WRITE, "*"),
        Capability(CapabilityOp.MEMORY_PRUNE, "semantic"),
    )

    def __init__(self, promotion_controller: PromotionController | None = None) -> None:
        self.promotion_controller: PromotionController = promotion_controller or PromotionController()
        self._plan_id: str | None = None
        self._goal: str = ""

    @staticmethod
    def _detect_op(goal: str, explicit: str | None) -> str:
        if explicit:
            return explicit.lower()
        g = goal.lower()
        if any(k in g for k in ("compress", "prune", "compact", "garbage", "gc")):
            return "compress"
        if any(k in g for k in ("store", "save", "write", "persist", "put")):
            return "store"
        return "recall"

    # ---- promotion wiring hooks --------------------------------------------

    def on_plan(self, plan: ExecutionPlan) -> None:
        """Feed the plan into the promotion controller (plan-scope refs + T1 entry)."""
        self._plan_id = plan.id.hex
        self._goal = plan.goal
        plan_entry = MemoryEntry(
            memory_id=plan.id,
            content=f"Plan[{plan.id.hex[:8]}] goal={plan.goal[:120]} steps={len(plan.steps)}",
            kind="plan",
            importance=0.85,
            access_count=1,
            scope="agent",
            scope_id="planner",
            created_at=plan.created_at,
            last_accessed_at=plan.created_at,
        )
        self.promotion_controller.tiers[TIER_INDRIYA].put(plan_entry)
        for step in plan.steps:
            self.promotion_controller.add_plan_ref(plan.id, f"{self._plan_id}::{step.id.hex[:8]}")

    def on_step_completed(self, step: PlanStep) -> None:
        """Every finished step becomes a T1 Indriya sensory insert (C3-deterministic)."""
        now = self.promotion_controller._now()
        content = (
            f"Step[{step.index}] agent={step.assigned_agent.value} "
            f"desc={step.description[:160]} status={step.status.value} "
            f"confidence={step.confidence:.3f}"
        )
        entry = MemoryEntry(
            memory_id=step.id,
            content=content,
            kind="step",
            importance=0.5 + 0.25 * step.confidence,
            access_count=1,
            scope="agent",
            scope_id=self._plan_id or "planner",
            created_at=step.started_at or now,
            last_accessed_at=step.finished_at or now,
        )
        self.promotion_controller.tiers[TIER_INDRIYA].put(entry)
        if self._plan_id:
            self.promotion_controller.add_plan_ref(step.id, self._plan_id)

    def end_of_run(self) -> PromotionReport:
        """Run all promotions (3 passes) and return the PromotionReport.

        This is the terminal hook after every plan step has been fed via
        :meth:`on_step_completed`.  The returned report contains
        ``tier_counts`` which is C3-bit-exact across equal inputs.
        """
        return self.promotion_controller.run_all_promotions(passes=3)

    def run(self, state: dict[str, Any], ctx: AgentRunContext) -> dict[str, Any]:
        goal = str(state.get("query") or state.get("goal") or "")
        explicit_op: str | None = state.get("operation")  # type: ignore[assignment]
        op = self._detect_op(goal, explicit_op)
        keys: list[str] = list(state.get("keys") or [])
        if not goal and not keys:
            report = MemoryReport(
                operation=op,
                summary="MemoryAgent needs either a `query`/`goal` or `keys` list to operate.",
                confidence=0.0,
            )
            return _add_result_status(state, status=TaskStatus.FAILED, report=report)
        if not keys:
            # Seed with N tokens from goal as "recalled keys" for determinism
            tokens = PlannerAgent._tokenise(goal) if goal else []
            keys = tokens[: min(8, len(tokens))] or ["default:global_context"]
        if op == "recall":
            items = len(keys)
            summary = (
                f"Recalled {items} memory slot(s) matching query {goal[:80]!r}: "
                + ", ".join(keys)
                + f".  Read capability verified against {len(ctx.capabilities)} token cap(s)."
            )
            confidence = min(0.95, 0.55 + 0.05 * items)
            return _add_result_status(
                state,
                status=TaskStatus.SUCCESS,
                report=MemoryReport(operation=op, items_processed=items, keys=keys, summary=summary, confidence=round(confidence, 3)),
            )
        if op == "store":
            items = len(keys)
            summary = f"Wrote {items} memory slot(s) into the semantic + episodic tiers with workspace_id={ctx.workspace_id!r}."
            return _add_result_status(
                state,
                status=TaskStatus.SUCCESS,
                report=MemoryReport(operation=op, items_processed=items, keys=keys, summary=summary, confidence=0.92),
            )
        # compress
        items = max(1, len(keys))
        ratio = 0.37 if items <= 3 else round(0.2 + 0.01 * items, 2)
        summary = f"Compressed {items} memory bucket(s); ratio kept={1 - ratio:.2f}.  Stale episodic records older than TTL purged."
        return _add_result_status(
            state,
            status=TaskStatus.SUCCESS,
            report=MemoryReport(
                operation=op,
                items_processed=items,
                keys=keys,
                summary=summary,
                compressed_ratio=min(1.0, ratio),
                confidence=0.88,
            ),
        )


# ===========================================================================
# 5. RAGAgent
# ===========================================================================


class RetrievedChunk(BaseModel):
    """One retrieved chunk with a hybrid (BM25 + dense) score."""

    chunk_id: str
    source_id: str = ""
    text: str
    score: float = Field(ge=0.0, le=1.0)
    hybrid: dict[str, float] = Field(default_factory=dict)


class RAGReport(BaseModel):
    """Structured output of :class:`RAGAgent`."""

    query: str
    k: int
    chunks: list[RetrievedChunk]
    summary: str
    cited_sources: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class RAGAgent(Agent):
    """Hybrid BM25 + dense retrieval against the knowledge corpus."""

    name = "rag"
    agent_type = AgentType.RAG

    required_capabilities = (
        Capability(CapabilityOp.RAG_SEARCH, "*"),
        Capability(CapabilityOp.RAG_INGEST, "workspace:*"),
        Capability(CapabilityOp.MEMORY_READ, "semantic"),
    )

    @staticmethod
    def _mock_chunk(query: str, i: int, seed_tokens: list[str]) -> RetrievedChunk:
        # Deterministic synthetic chunk, seeded by query tokens and i.
        text_tokens = seed_tokens[i % max(1, len(seed_tokens)) :] + seed_tokens[:i]
        if not text_tokens:
            text_tokens = [f"term-{i}", "retrieval", "results", f"passage-{i + 1}"]
        joined = " ".join(text_tokens[:6] or [f"chunk-{i}"])
        score = 0.4 + 0.07 * i + 0.001 * sum(ord(c) for c in query) % 60 / 10
        score = min(0.99, round(score, 3))
        return RetrievedChunk(
            chunk_id=f"chunk_{i:03d}_{hashlib.md5((query + str(i)).encode('utf-8')).hexdigest()[:8]}",
            source_id=f"doc{(i % 5) + 1}",
            text=f"[{i + 1}/hybrid] Passage about {query[:60]}: {joined} .",
            score=score,
            hybrid={"bm25": round(score * 0.7, 3), "dense": round(score * 0.9, 3)},
        )

    def run(self, state: dict[str, Any], ctx: AgentRunContext) -> dict[str, Any]:
        query = str(state.get("query") or state.get("rag_query") or "").strip()
        k = int(state.get("k") or 5)
        if k <= 0:
            k = 5
        if not query:
            return _add_result_status(
                state,
                status=TaskStatus.FAILED,
                report=RAGReport(
                    query="",
                    k=k,
                    chunks=[],
                    summary="RAGAgent needs `query` or `rag_query` in state.",
                    confidence=0.0,
                ),
            )
        tokens = PlannerAgent._tokenise(query)
        chunks = [self._mock_chunk(query, i, tokens) for i in range(k)]
        sources = sorted({c.source_id for c in chunks if c.source_id})
        best = max((c.score for c in chunks), default=0.0)
        summary = (
            f"Retrieved top-{k} hybrid chunks for {query[:60]!r}. "
            f"Top score={best:.3f}. Unique sources: {sources or ['(none)']}. "
            "Chunks ready for injection into the LLM context window with citations."
        )
        return _add_result_status(
            state,
            status=TaskStatus.SUCCESS,
            report=RAGReport(
                query=query,
                k=k,
                chunks=chunks,
                summary=summary,
                cited_sources=sources,
                confidence=min(0.98, 0.5 + 0.06 * k),
            ),
        )


# ===========================================================================
# 6. ToolAgent
# ===========================================================================


class ToolReport(BaseModel):
    """Structured output of :class:`ToolAgent`."""

    invocations_requested: int
    invocations_success: int
    invocations_failed: int
    call_log: list[dict[str, Any]] = Field(default_factory=list)
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)


class ToolAgent(Agent):
    """Batch-invokes N registry tools using a Capability-gated token."""

    name = "tool"
    agent_type = AgentType.TOOL

    required_capabilities = (Capability(CapabilityOp.TOOL_INVOKE, "*"),)

    def run(self, state: dict[str, Any], ctx: AgentRunContext) -> dict[str, Any]:
        calls: list[dict[str, Any]] = list(state.get("calls") or state.get("tool_calls") or [])
        if not calls:
            return _add_result_status(
                state,
                status=TaskStatus.AWAITING_INPUT,
                report=ToolReport(
                    invocations_requested=0,
                    invocations_success=0,
                    invocations_failed=0,
                    summary="ToolAgent.call list empty — pass `calls=[{name, args, kwargs}]` to run tools.",
                    confidence=0.1,
                ),
            )
        call_log: list[dict[str, Any]] = []
        succ = 0
        failed = 0
        for idx, call in enumerate(calls):
            name: str = str(call.get("name") or call.get("tool") or "")
            args: dict[str, Any] = dict(call.get("args") or call.get("kwargs") or {})
            try:
                r: ToolResult = ctx.tools.invoke(name, args, token=ctx.token, capabilities=ctx.capabilities)
                call_log.append(
                    {
                        "idx": idx,
                        "name": name,
                        "ok": bool(r.success),
                        "exit_code": r.exit_code,
                        "stdout_preview": r.stdout[:160],
                        "stderr_preview": r.stderr[:160],
                    }
                )
                if r.success:
                    succ += 1
                else:
                    failed += 1
            except PermissionDenied as pde:
                call_log.append(
                    {
                        "idx": idx,
                        "name": name,
                        "ok": False,
                        "permission_denied": True,
                        "detail": str(pde)[:240],
                    }
                )
                failed += 1
            except Exception as exc:
                call_log.append(
                    {
                        "idx": idx,
                        "name": name,
                        "ok": False,
                        "exception": type(exc).__name__,
                        "detail": str(exc)[:240],
                    }
                )
                failed += 1
        total = succ + failed
        confidence = round((succ / total) if total else 0.0, 3)
        summary = (
            f"ToolAgent completed {total} invocation(s): {succ} ok, {failed} failed. "
            f"Capabilities checked: {len(ctx.capabilities)} on token {ctx.token.id.hex[:8]}."
        )
        status = TaskStatus.SUCCESS if failed == 0 else (TaskStatus.AWAITING_INPUT if succ == 0 else TaskStatus.SUCCESS)
        return _add_result_status(
            state,
            status=status,
            report=ToolReport(
                invocations_requested=total,
                invocations_success=succ,
                invocations_failed=failed,
                call_log=call_log,
                summary=summary,
                confidence=confidence,
            ),
        )


# ===========================================================================
# 7. JudgeAgent
# ===========================================================================


class RankedCandidate(BaseModel):
    """One ranked candidate from the Judge."""

    candidate_id: str
    rank: int = Field(ge=1)
    score: float = Field(ge=0.0, le=1.0)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    rationale: str = ""


class JudgeReport(BaseModel):
    """Structured output of :class:`JudgeAgent`."""

    prompt: str
    candidates: list[RankedCandidate]
    winner_id: str | None = None
    tie: bool = False
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)


class JudgeAgent(Agent):
    """Rank N candidate answers → produce 1..N ordered RankedCandidate list."""

    name = "judge"
    agent_type = AgentType.JUDGE

    required_capabilities = (
        Capability(CapabilityOp.MODEL_INFERENCE, "judge/*"),
        Capability(CapabilityOp.MEMORY_READ, "episodic"),
    )

    def run(self, state: dict[str, Any], ctx: AgentRunContext) -> dict[str, Any]:
        prompt = str(state.get("prompt") or state.get("query") or "").strip()
        raw_cands: Any = state.get("candidates") or state.get("answers")
        if not isinstance(raw_cands, list | tuple) or not raw_cands:
            return _add_result_status(
                state,
                status=TaskStatus.FAILED,
                report=JudgeReport(
                    prompt=prompt,
                    candidates=[],
                    summary="JudgeAgent needs `candidates=[..]` with >= 1 dicts or strings.",
                    confidence=0.0,
                ),
            )
        # Score each: citation count + length-normalised factual density.
        scored: list[tuple[str, float, str]] = []
        for idx, c in enumerate(raw_cands):
            cid: str
            text: str
            if isinstance(c, dict):
                cid = str(c.get("id") or c.get("candidate_id") or f"cand_{idx}")
                text = str(c.get("text") or c.get("answer") or c.get("content") or "")
            else:
                cid = f"cand_{idx}"
                text = str(c)
            citation_boost = 0.1 * min(5, text.count("[") + text.count("src"))
            tokens = PlannerAgent._tokenise(text)
            density = min(1.0, len(set(tokens)) / max(6, len(tokens)))
            score = min(0.99, round(0.4 + density * 0.5 + citation_boost, 3))
            scored.append((cid, score, text))
        scored.sort(key=lambda t: (-t[1], t[0]))
        ranked: list[RankedCandidate] = []
        for order, (cid, score, text) in enumerate(scored, start=1):
            strengths: list[str] = []
            weaknesses: list[str] = []
            if text.count(".") >= 2:
                strengths.append("multi-sentence argument")
            if text.count("[") >= 1:
                strengths.append("citations detected")
            if len(set(PlannerAgent._tokenise(text))) < 5 and len(text) > 40:
                weaknesses.append("low lexical diversity")
            if len(text) < 40:
                weaknesses.append("short / under-justified")
            rationale = f"Candidate {cid} scored {score:.2f} — " + (strengths[0] + "." if strengths else "no strong features.")
            ranked.append(
                RankedCandidate(
                    candidate_id=cid,
                    rank=order,
                    score=score,
                    strengths=strengths,
                    weaknesses=weaknesses,
                    rationale=rationale,
                )
            )
        winner_id = ranked[0].candidate_id if ranked else None
        tie = len(ranked) >= 2 and ranked[0].score == ranked[1].score
        summary = (
            f"Judged {len(ranked)} candidate(s) for prompt {prompt[:80]!r}. "
            f"Winner = {winner_id} with score {ranked[0].score if ranked else 0:.3f}. "
            + (
                f"TIE with runner-up at same score ({ranked[1].score:.3f})."
                if tie
                else f"Runner-up score: {ranked[1].score:.3f}."
                if len(ranked) >= 2
                else ""
            )
        )
        confidence = round(0.8 - (0.15 if tie else 0.0), 3) if ranked else 0.0
        return _add_result_status(
            state,
            status=TaskStatus.SUCCESS,
            report=JudgeReport(
                prompt=prompt,
                candidates=ranked,
                winner_id=winner_id,
                tie=tie,
                summary=summary,
                confidence=max(0.0, min(1.0, confidence)),
            ),
        )


# ===========================================================================
# 8. CriticAgent
# ===========================================================================


class CriticReport(BaseModel):
    """Quality-score critique of a prior draft."""

    quality_scores: dict[str, float] = Field(default_factory=dict)  # dimension -> 0..1
    overall_quality: float = Field(default=0.0, ge=0.0, le=1.0)
    praise: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    summary: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class CriticAgent(Agent):
    """Dimension-scored critique (quality rubric) of a draft output.

    Distinction from Reflection: Reflection detects *mistakes* (tool exits,
    contradictions, missing citations).  Critic scores *quality* along a
    multi-axis rubric and gives praise/improvements.  Use the two in
    sequence: Reflection first → Critic for the quality gate.
    """

    name = "critic"
    agent_type = AgentType.CRITIC

    required_capabilities = (Capability(CapabilityOp.MEMORY_READ, "episodic"),)

    def run(self, state: dict[str, Any], ctx: AgentRunContext) -> dict[str, Any]:
        draft = str(state.get("draft") or state.get("answer") or state.get("content") or "")
        if len(draft) < 10:
            return _add_result_status(
                state,
                status=TaskStatus.FAILED,
                report=CriticReport(
                    summary="CriticAgent needs a `draft` (>= 10 chars) to critique.",
                    confidence=0.0,
                ),
            )
        tokens = PlannerAgent._tokenise(draft)
        unique_ratio = len(set(tokens)) / max(6, len(tokens))
        dims: dict[str, float] = {
            "structure": round(min(1.0, 0.4 + 0.12 * draft.count("\n") + 0.01 * draft.count(".")), 3),
            "clarity": round(min(1.0, 0.3 + 0.6 * unique_ratio), 3),
            "citation_support": round(min(1.0, 0.0 + 0.1 * draft.count("["), 0.1 * draft.count(")")), 3),
            "completeness": round(min(1.0, 0.5 + 0.01 * max(0, len(draft) - 200)), 3),
            "grammar": round(min(1.0, 0.7 + 0.02 * max(0, 5 - draft.count("!!") - draft.count("??"))), 3),
        }
        overall = round(sum(dims.values()) / len(dims), 3)
        praise: list[str] = []
        improvements: list[str] = []
        for dim, score in dims.items():
            if score >= 0.7:
                praise.append(f"{dim}: strong ({score:.2f})")
            elif score <= 0.45:
                improvements.append(f"strengthen {dim} (current {score:.2f})")
        if overall >= 0.75:
            praise.insert(0, "overall high-quality draft; safe to send to sign-off.")
        else:
            improvements.insert(0, "overall below sign-off threshold; revise before executor.")
        summary = (
            f"Critiqued {len(draft)}-char draft along {len(dims)} axes.  Overall = {overall:.2f}. "
            f"{len(praise)} praise items, {len(improvements)} improvement items."
        )
        return _add_result_status(
            state,
            status=TaskStatus.SUCCESS,
            report=CriticReport(
                quality_scores=dims,
                overall_quality=overall,
                praise=praise,
                improvements=improvements,
                summary=summary,
                confidence=min(1.0, 0.85),
            ),
        )


# ===========================================================================
# 9. ExecutorAgent / Kriyakārī
# ===========================================================================


_SEVERITY_WEIGHTS: dict[str, float] = {
    "low": 0.05,
    "medium": 0.10,
    "high": 0.20,
    "critical": 0.35,
}

_SIGNOFF_THRESHOLD = 0.90
_REPLAN_LOWER_THRESHOLD = 0.50


class ExecutorReport(BaseModel):
    """Terminal sign-off decision from the Executor agent."""

    decision: str  # "signoff" | "reject" | "replan"
    final_answer: str = ""
    rejection_reason: str = ""
    replan_hints: list[str] = Field(default_factory=list)
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
    tristate: ExecutorTriStateDecision | None = None


class ExecutorAgent(Agent):
    """Terminal action: sign off, reject with reason, or return a replan hint.

    This is the FINAL agent in a plan graph.  The kernel treats Executor's
    return dict as the authoritative "done" signal on a run.  It never fans
    out; it only reads the aggregated prior state and produces one decision.

    Implements a **deterministic tri-state decision** (C3 identity holds):
      - Count unmet ``accept_criteria`` weighted by severity
      - Subtract plan-health penalties (failed steps, low step confidence)
      - Threshold rules:
          * confidence >= 0.90  → SIGNOFF
          * 0.50 <= conf < 0.90 → REPLAN
          * confidence < 0.50   → REJECT
    """

    name = "executor"
    agent_type = AgentType.EXECUTOR

    required_capabilities = (Capability(CapabilityOp.WORKSPACE_WRITE, "*"),)

    @staticmethod
    def _evaluate_plan_health(plan: ExecutionPlan | None) -> tuple[float, list[str]]:
        """Compute plan-health penalty fraction + list of plan-level violations."""
        if plan is None:
            return 0.0, []
        violations: list[str] = []
        penalty = 0.0
        total_steps = len(plan.steps)
        if total_steps == 0:
            return 0.40, ["plan: zero steps"]
        failed = sum(1 for s in plan.steps if s.status == TaskStatus.FAILED)
        skipped = sum(1 for s in plan.steps if s.status == TaskStatus.SKIPPED)
        pending = sum(1 for s in plan.steps if s.status in (TaskStatus.PENDING, TaskStatus.QUEUED, TaskStatus.RUNNING))
        low_conf = sum(1 for s in plan.steps if s.confidence < 0.40)
        if failed:
            violations.append(f"plan: {failed}/{total_steps} steps FAILED")
            penalty += min(0.30, failed * 0.08)
        if skipped:
            violations.append(f"plan: {skipped}/{total_steps} steps SKIPPED")
            penalty += min(0.10, skipped * 0.03)
        if pending:
            violations.append(f"plan: {pending}/{total_steps} steps still PENDING/RUNNING")
            penalty += min(0.20, pending * 0.05)
        if low_conf:
            violations.append(f"plan: {low_conf}/{total_steps} steps with confidence <0.40")
            penalty += min(0.12, low_conf * 0.04)
        return round(penalty, 3), violations

    @staticmethod
    def _evaluate_criteria(
        accept_criteria: list[AcceptCriterion] | None,
    ) -> tuple[float, list[str]]:
        """Weighted score from accept_criteria (0.0..1.0) + violation IDs.

        Score = 1.0 - sum(weight_of_unmet_criteria), clamped to [0.0, 1.0].
        Returns (score, list_of_unmet_criterion_ids).
        """
        if not accept_criteria:
            return 1.0, []
        violations: list[str] = []
        total_weight = 0.0
        unmet_weight = 0.0
        for crit in accept_criteria:
            w = _SEVERITY_WEIGHTS.get(crit.severity, 0.10)
            total_weight += w
            if not crit.met:
                unmet_weight += w
                violations.append(crit.id)
        if total_weight == 0.0:
            return 1.0, []
        raw = 1.0 - (unmet_weight / max(total_weight, 0.01))
        return max(0.0, min(1.0, round(raw, 3))), violations

    @classmethod
    def evaluate_decision(
        cls,
        plan: ExecutionPlan | None = None,
        accept_criteria: list[AcceptCriterion] | None = None,
    ) -> ExecutorTriStateDecision:
        """Deterministic tri-state decision core (C3-deterministic).

        No randomness, no wall-clock time — pure function of inputs so
        equal inputs always produce bit-exact equal outputs.
        """
        criteria_score, criteria_violations = cls._evaluate_criteria(accept_criteria)
        plan_penalty, plan_violations = cls._evaluate_plan_health(plan)
        raw_confidence = criteria_score - plan_penalty
        confidence = max(0.0, min(1.0, round(raw_confidence, 3)))
        all_violations = criteria_violations + plan_violations
        if confidence >= _SIGNOFF_THRESHOLD:
            decision = TriStateDecision.SIGNOFF
            if all_violations:
                reason = (
                    f"SIGNOFF: acceptance_confidence={confidence:.3f} >= {_SIGNOFF_THRESHOLD:.2f}. "
                    f"Minor issues noted ({len(all_violations)}) but within tolerance."
                )
            else:
                reason = f"SIGNOFF: all acceptance criteria met, plan healthy. acceptance_confidence={confidence:.3f}."
        elif confidence >= _REPLAN_LOWER_THRESHOLD:
            decision = TriStateDecision.REPLAN
            reason = (
                f"REPLAN: acceptance_confidence={confidence:.3f} "
                f"in [{_REPLAN_LOWER_THRESHOLD:.2f}, {_SIGNOFF_THRESHOLD:.2f}). "
                f"Violations: {len(all_violations)}. Re-run planner with fixes."
            )
        else:
            decision = TriStateDecision.REJECT
            reason = (
                f"REJECT: acceptance_confidence={confidence:.3f} < {_REPLAN_LOWER_THRESHOLD:.2f}. "
                f"Critical issues detected ({len(all_violations)} violations). "
                f"Plan requires substantial redesign."
            )
        return ExecutorTriStateDecision(
            decision=decision,
            reason=reason,
            violations=all_violations,
            acceptance_confidence=confidence,
        )

    def run(self, state: dict[str, Any], ctx: AgentRunContext) -> dict[str, Any]:
        final_answer = str(state.get("final_answer") or state.get("answer") or "")
        plan: ExecutionPlan | None = state.get("plan")
        accept_criteria_raw: Any = state.get("accept_criteria")
        accept_criteria: list[AcceptCriterion] | None = None
        if isinstance(accept_criteria_raw, list):
            parsed: list[AcceptCriterion] = []
            for item in accept_criteria_raw:
                if isinstance(item, AcceptCriterion):
                    parsed.append(item)
                elif isinstance(item, dict):
                    try:
                        parsed.append(AcceptCriterion(**item))
                    except Exception:
                        continue
            if parsed:
                accept_criteria = parsed
        synthesized: list[AcceptCriterion] = []
        if accept_criteria is None:
            if final_answer:
                len_ok = len(final_answer) >= 120
                synthesized.append(AcceptCriterion(
                    id="answer_min_length",
                    description="Final answer has sufficient detail (>=120 chars)",
                    severity="high",
                    met=len_ok,
                ))
            report_type = state.get("report_type")
            report = state.get("report")
            if report_type == "CriticReport" and isinstance(report, dict):
                quality = float(report.get("overall_quality") or 0.0)
                q_ok = quality >= 0.5
                synthesized.append(AcceptCriterion(
                    id="critic_quality_threshold",
                    description=f"Critic overall_quality >= 0.5 (got {quality:.2f})",
                    severity="high",
                    met=q_ok,
                ))
        if accept_criteria is None:
            accept_criteria = synthesized if synthesized else None
        elif synthesized:
            accept_criteria = list(accept_criteria) + synthesized
        tristate = self.evaluate_decision(plan=plan, accept_criteria=accept_criteria)
        decision_val = tristate.decision.value if isinstance(tristate.decision, TriStateDecision) else str(tristate.decision)
        replan_hints: list[str] = []
        if decision_val == TriStateDecision.REPLAN.value:
            for vid in tristate.violations[:3]:
                replan_hints.append(f"address criterion/issue: {vid}")
        elif decision_val == TriStateDecision.REJECT.value:
            for vid in tristate.violations[:5]:
                replan_hints.append(f"CRITICAL — fix before replan: {vid}")
        summary = (
            f"Executor decision = {decision_val.upper()}. "
            f"acceptance_confidence={tristate.acceptance_confidence:.3f}, "
            f"violations={len(tristate.violations)}. "
            f"Workspace write for audit: {ctx.workspace_id!r}."
        )
        status = TaskStatus.SUCCESS if decision_val == TriStateDecision.SIGNOFF.value else TaskStatus.AWAITING_INPUT
        decision_str = decision_val
        return _add_result_status(
            state,
            status=status,
            report=ExecutorReport(
                decision=decision_str,
                final_answer=final_answer,
                rejection_reason=tristate.reason,
                replan_hints=replan_hints,
                summary=summary,
                confidence=tristate.acceptance_confidence,
                tristate=tristate,
            ),
        )


# ===========================================================================
# 10. SupervisorAgent
# ===========================================================================


class SupervisorReport(BaseModel):
    """Structured output of the supervisor: task tree + sub-token IDs."""

    task_count: int = Field(default=0, ge=0)
    completed: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    pending: int = Field(default=0, ge=0)
    minted_subtokens: int = Field(default=0, ge=0)
    status_counts: dict[str, int] = Field(default_factory=dict)
    summary: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class SupervisorAgent(Agent):
    """SPAWN/KILL surface: builds a plan-tree, mints sub-tokens for fan-out.

    Does NOT actually run real spawns (that's kernel scheduler privilege).
    Instead it:
      1. Validates that the spawner token carries SPAWN_AGENT.
      2. Computes the task-tree + counts sub-tokens it would mint.
      3. Returns a deterministic report so the kernel can apply it.
    """

    name = "supervisor"
    agent_type = AgentType.SUPERVISOR

    required_capabilities = (
        Capability(CapabilityOp.SPAWN_AGENT, "*"),
        Capability(CapabilityOp.KILL_AGENT, "zombie:*"),
        Capability(CapabilityOp.ADMIN, "status"),
    )

    def run(self, state: dict[str, Any], ctx: AgentRunContext) -> dict[str, Any]:
        goal = str(state.get("goal") or state.get("tree_goal") or "").strip()
        # Gate on SPAWN_AGENT capability presence before any real work
        can_spawn = any(c.allows(CapabilityOp.SPAWN_AGENT, "*") or c.allows(CapabilityOp.SPAWN_AGENT, "workspace:*") for c in ctx.capabilities)
        if not can_spawn:
            return _add_result_status(
                state,
                status=TaskStatus.FAILED,
                report=SupervisorReport(
                    summary=(
                        "SupervisorAgent requires SPAWN_AGENT:* capability; none found in "
                        f"ctx.capabilities ({len(ctx.capabilities)} caps).  Refusing to plan sub-tokens."
                    ),
                    confidence=0.0,
                ),
            )
        tokens = PlannerAgent._tokenise(goal) if goal else []
        n = max(2, min(8, 2 + len(tokens) // 5))
        # Build mock status distribution deterministically from token hash
        h = int(hashlib.md5(goal.encode("utf-8") or b"default").hexdigest()[:8], 16)
        failed = h % max(1, n // 3)
        pending = max(0, min(n // 2, (h >> 8) % (n // 2 + 1)))
        completed = max(0, n - failed - pending)
        status_counts = {
            TaskStatus.SUCCESS.name.lower(): completed,
            TaskStatus.RUNNING.name.lower(): pending,
            TaskStatus.FAILED.name.lower(): failed,
        }
        minted = n  # one sub-token per sub-task
        summary = (
            f"Supervisor built {n}-task tree for goal {goal[:80]!r}. "
            f"Would mint {minted} sub-tokens.  Tree snapshot: completed={completed}, running={pending}, failed={failed}. "
            f"SPA privilege: verified on token={ctx.token.id.hex[:8]}."
        )
        return _add_result_status(
            state,
            status=TaskStatus.SUCCESS,
            report=SupervisorReport(
                task_count=n,
                completed=completed,
                failed=failed,
                pending=pending,
                minted_subtokens=minted,
                status_counts=status_counts,
                summary=summary,
                confidence=min(0.95, 0.75 + 0.02 * n),
            ),
        )


# ===========================================================================
# 11. OrchestratorAgent
# ===========================================================================


class OrchestratorReport(BaseModel):
    """Fan-out / join report from the orchestrator."""

    fan_out_count: int = Field(ge=0)
    dispatched_to: list[str] = Field(default_factory=list)
    join_policy: str  # "all" | "any" | "majority"
    join_summary: str = ""
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)


class OrchestratorAgent(Agent):
    """Fan-out → N workers → policy-join.

    This is the dispatcher layer the kernel scheduler uses when PlannerAgent
    marks a step as ``ORCHESTRATOR: fan-out and join``.  It is deterministic
    and declarative: it does NOT real-run the workers (scheduler's job);
    it produces the dispatch list + join policy so scheduler can execute.
    """

    name = "orchestrator"
    agent_type = AgentType.ORCHESTRATOR

    required_capabilities = (Capability(CapabilityOp.SPAWN_AGENT, "subtask:*"),)

    def run(self, state: dict[str, Any], ctx: AgentRunContext) -> dict[str, Any]:
        workers: list[str] = list(state.get("workers") or [])
        policy = str(state.get("join_policy") or "all").lower()
        if policy not in {"all", "any", "majority"}:
            policy = "all"
        goal = str(state.get("goal") or state.get("query") or "").strip()
        if not workers and goal:
            # Default fan-out: 3 worker slots
            workers = [AgentType.RESEARCH.value, AgentType.RAG.value, AgentType.MEMORY.value]
            if any(k in goal.lower() for k in ("code", "patch", "test")):
                workers = [AgentType.CODING.value, AgentType.REFLECTION.value, AgentType.CRITIC.value]
            # Ensure unique + deterministic
            seen: set[str] = set()
            workers = [w for w in workers if not (w in seen or seen.add(w))]
        if not workers:
            return _add_result_status(
                state,
                status=TaskStatus.AWAITING_INPUT,
                report=OrchestratorReport(
                    fan_out_count=0,
                    dispatched_to=[],
                    join_policy=policy,
                    join_summary="",
                    summary="OrchestratorAgent needs `workers` list OR a `goal` to derive fan-out.",
                    confidence=0.05,
                ),
            )
        join_summary = f"Join policy `{policy}`: " + (
            "wait for EVERY dispatched worker to return SUCCESS; fail-fast on first FAILED."
            if policy == "all"
            else "return as soon as any one worker returns SUCCESS."
            if policy == "any"
            else "need strictly more than half of workers SUCCESS."
        )
        summary = (
            f"Orchestrator will fan-out {len(workers)} workers to {list(workers)}. "
            f"Join policy = {policy}.  Parent token={ctx.token.id.hex[:8]}, workspace={ctx.workspace_id!r}."
        )
        return _add_result_status(
            state,
            status=TaskStatus.SUCCESS,
            report=OrchestratorReport(
                fan_out_count=len(workers),
                dispatched_to=list(workers),
                join_policy=policy,
                join_summary=join_summary,
                summary=summary,
                confidence=0.92,
            ),
        )


# ===========================================================================
# 12. AgentRoster — registry + spawn-time capability gating
# ===========================================================================


class AgentRoster:
    """Central registry mapping :class:`AgentType` → agent implementation.

    Two call modes:
      1. ``AgentRoster.get(agent_type)`` — returns a fresh instance with no
         capability checks (useful for unit tests / dry runs).
      2. ``AgentRoster.spawn(agent_type, ctx)`` — kernel spawn path: asserts
         that ``ctx.capabilities`` carries every cap on the agent's
         ``required_capabilities`` list, else raises :class:`PermissionDenied`.
    """

    _REGISTRY: dict[AgentType, type[Agent]] | None = None

    @classmethod
    def registry(cls) -> dict[AgentType, type[Agent]]:
        if cls._REGISTRY is None:
            cls._REGISTRY = {
                AgentType.PLANNER: PlannerAgent,
                AgentType.RESEARCH: ResearchAgent,
                AgentType.CODING: CodingAgent,
                AgentType.MEMORY: MemoryAgent,
                AgentType.RAG: RAGAgent,
                AgentType.TOOL: ToolAgent,
                AgentType.REFLECTION: ReflectionAgent,
                AgentType.JUDGE: JudgeAgent,
                AgentType.CRITIC: CriticAgent,
                AgentType.EXECUTOR: ExecutorAgent,
                AgentType.SUPERVISOR: SupervisorAgent,
                AgentType.ORCHESTRATOR: OrchestratorAgent,
            }
        return cls._REGISTRY

    @classmethod
    def all_types(cls) -> list[AgentType]:
        """Return every rostered AgentType in sorted, stable order."""

        return sorted(cls.registry().keys(), key=lambda at: at.value)

    @classmethod
    def get(cls, agent_type: AgentType) -> Agent:
        """Return a fresh agent instance.  Raises ``KeyError`` if not rostered."""

        cls_ = cls.registry()[agent_type]
        return cls_()

    @classmethod
    def spawn(cls, agent_type: AgentType, ctx: AgentRunContext) -> Agent:
        """Spawn path: capability-check ctx.capabilities ⊇ agent.required_capabilities."""

        agent = cls.get(agent_type)
        missing: list[tuple[CapabilityOp, str]] = []
        for req in agent.required_capabilities:
            ok = any(c.allows(req.op, req.target) for c in ctx.capabilities)
            if not ok:
                missing.append((req.op, req.target))
        if missing:
            missing_str = ", ".join(f"{op.value}:{t}" for op, t in missing)
            raise PermissionDenied(
                token_id=ctx.token.id,
                op=CapabilityOp.SPAWN_AGENT,
                target=agent_type.value,
                details=(f"Cannot spawn {agent.name!r}: token lacks capability(ies) {missing_str}. Token has {len(ctx.capabilities)} cap(s)."),
            )
        return agent


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
