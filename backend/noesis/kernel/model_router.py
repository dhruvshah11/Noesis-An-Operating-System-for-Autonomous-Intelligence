"""
Model Router — decides *which* LLM / embedding model runs each inference.

Problem
-------
LangChain/LangGraph force you to bind one LLM to each agent.  That's a $100M+
mistake in production: you want fast cheap models for tool-parameter parsing
and slow strong models for reasoning, you want Claude 3 Opus for legal text,
Llama 3.1 405B via Together for on-prem data, and GPT-Vision for images.

Alternative designs we considered:
  1. **Per-agent static binding.**  Simpler but costly — bad for cost.
  2. **A/B trial per call.**  Best for quality but high latency due to
     shadow-traffic.  Addressed as Future work (SH-MAPO).
  3. **Score-based weighted ranking with constraint filters.**  Our pick.
     Weights are tunable via config; constraints (e.g. vision required)
     filter first, then we sort by the weighted composite score, returning
     the top-N for a router supervisor to try if the primary times out.

Failure modes / risks
---------------------
  - All candidates filtered out: we fall back to ``default_model`` with a
    log warning (never drop a call).
  - Score drifts: router exposes ``record_outcome`` so a policy-learner can
    adjust weights over time (stub API implemented; learner is §20.FUTURE).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from noesis.types import ProviderType


class ModelClass(StrEnum):
    """Category of model — used by constraint filters."""

    CHAT_FAST = "chat_fast"
    CHAT_BALANCED = "chat_balanced"
    CHAT_STRONG = "chat_strong"
    CHAT_VERY_STRONG = "chat_very_strong"
    VISION = "vision"
    AUDIO = "audio"
    EMBEDDING = "embedding"
    CODE = "code"
    TOOL_USE = "tool_use"


@dataclass(slots=True)
class LatencySla:
    p50_ms: float | None = None
    p95_ms: float | None = None
    timeout_ms: float | None = None


@dataclass(slots=True)
class ModelProfile:
    """Static card for a single model variant + provider."""

    provider: ProviderType
    model_id: str
    model_class: ModelClass
    # 0..1 score profiles — higher = better
    quality: float = 0.5
    reasoning: float = 0.5
    code: float = 0.5
    tool_use: float = 0.5
    vision: float = 0.0
    audio: float = 0.0
    multimodal: float = 0.0
    # Resources
    context_tokens: int = 128_000
    max_output_tokens: int = 4096
    # Cost ($) per 1k tokens
    input_cost_per_1k: float = 0.0
    output_cost_per_1k: float = 0.0
    # Baseline latency profile
    latency: LatencySla = field(default_factory=LatencySla)
    # Local execution constraints
    requires_gpu: bool = False
    vram_gb_required: float = 0.0
    # Context-aware caching supported?
    supports_prompt_caching: bool = False
    # Tags for routing rules
    capabilities: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    def has(self, capability: str) -> bool:
        return capability in self.capabilities


@dataclass(slots=True)
class RoutingConstraint:
    """Caller-supplied routing hints."""

    required_class: ModelClass | None = None
    required_capabilities: tuple[str, ...] = ()
    max_cost_per_1k_input: float | None = None
    max_p95_latency_ms: float | None = None
    min_context_tokens: int | None = None
    min_quality: float | None = None
    min_reasoning: float | None = None
    provider_preference: ProviderType | None = None
    forbid_providers: tuple[ProviderType, ...] = ()
    allow_local_only: bool = False
    allow_remote_only: bool = False


@dataclass(slots=True)
class ScoredModel:
    profile: ModelProfile
    score: float
    cost_estimate: float
    components: dict[str, float]  # breakdown of the score for debug UI


@dataclass(slots=True)
class ModelSchedulingDecision:
    """The final verdict of a single ``route()`` call."""

    call_id: UUID
    primary: ScoredModel
    fallbacks: list[ScoredModel]
    constraint: RoutingConstraint
    reason: str
    generated_at_ns: int


DEFAULT_WEIGHTS = {
    "quality": 0.30,
    "reasoning": 0.15,
    "tool_use": 0.15,
    "code": 0.05,
    "vision": 0.05,
    "multimodal": 0.05,
    "inverse_cost": 0.15,
    "inverse_latency": 0.10,
}


class ModelRouter:
    """Weighted-score + filter model router."""

    def __init__(
        self,
        profiles: list[ModelProfile] | None = None,
        *,
        weights: dict[str, float] | None = None,
        default_model: tuple[ProviderType, str] | None = None,
    ) -> None:
        self._profiles: list[ModelProfile] = list(profiles or [])
        self._weights = weights or dict(DEFAULT_WEIGHTS)
        self._default_model = default_model or (ProviderType.OPENAI, "gpt-4o-mini")
        # For future model-routing A/B learning.
        self._outcome_buffer: list[dict[str, Any]] = []

    # ---------------------------------------------------------- Registry

    def register(self, profile: ModelProfile) -> None:
        # De-duplicate by (provider, model_id) so re-registration refreshes cards.
        self._profiles = [p for p in self._profiles if (p.provider, p.model_id) != (profile.provider, profile.model_id)]
        self._profiles.append(profile)

    # ---------------------------------------------------------- Routing

    def route(
        self,
        *,
        constraint: RoutingConstraint,
        estimated_input_tokens: int = 0,
        estimated_output_tokens: int = 1024,
        top_n_fallbacks: int = 2,
    ) -> ModelSchedulingDecision:
        """Return a primary + N fallback model selections."""
        candidates = [p for p in self._profiles if self._matches(p, constraint)]
        if not candidates:
            # Fallback: relax every non-critical constraint and just choose default
            provider, model_id = self._default_model
            fallback_profile = next(
                (p for p in self._profiles if p.provider == provider and p.model_id == model_id),
                ModelProfile(provider=provider, model_id=model_id, model_class=ModelClass.CHAT_BALANCED),
            )
            if fallback_profile not in self._profiles:
                self._profiles.append(fallback_profile)
            scored = self._score(fallback_profile, estimated_input_tokens, estimated_output_tokens)
            return ModelSchedulingDecision(
                call_id=uuid4(),
                primary=scored,
                fallbacks=[],
                constraint=constraint,
                reason="constraints.filtered_all_candidates_used_fallback",
                generated_at_ns=__import__("time").perf_counter_ns(),
            )
        scored_candidates = sorted(
            (self._score(p, estimated_input_tokens, estimated_output_tokens) for p in candidates),
            key=lambda s: s.score,
            reverse=True,
        )
        primary = scored_candidates[0]
        fallbacks = scored_candidates[1 : 1 + top_n_fallbacks]
        reason_parts = [
            f"primary={primary.profile.provider.value}:{primary.profile.model_id}",
            f"score={primary.score:.3f}",
            f"candidates_filtered={len(scored_candidates)}",
        ]
        return ModelSchedulingDecision(
            call_id=uuid4(),
            primary=primary,
            fallbacks=fallbacks,
            constraint=constraint,
            reason=" | ".join(reason_parts),
            generated_at_ns=__import__("time").perf_counter_ns(),
        )

    # ---------------------------------------------------------- Learning hooks

    def record_outcome(
        self,
        decision: ModelSchedulingDecision,
        *,
        total_tokens: int,
        latency_ms: float,
        success: bool,
        quality_feedback: float | None = None,
    ) -> None:
        """Append a result to the outcome buffer for offline ML training."""
        self._outcome_buffer.append(
            {
                "call_id": str(decision.call_id),
                "primary": (decision.primary.profile.provider.value, decision.primary.profile.model_id),
                "total_tokens": total_tokens,
                "latency_ms": latency_ms,
                "success": success,
                "quality_feedback": quality_feedback,
            }
        )

    # ---------------------------------------------------------- Internals

    def _matches(self, p: ModelProfile, c: RoutingConstraint) -> bool:
        if c.required_class is not None and p.model_class != c.required_class:
            return False
        if c.provider_preference is not None and p.provider != c.provider_preference:
            return False
        if p.provider in c.forbid_providers:
            return False
        if c.min_context_tokens and p.context_tokens < c.min_context_tokens:
            return False
        if c.min_quality is not None and p.quality < c.min_quality:
            return False
        if c.min_reasoning is not None and p.reasoning < c.min_reasoning:
            return False
        if c.max_cost_per_1k_input is not None and p.input_cost_per_1k > c.max_cost_per_1k_input:
            return False
        if c.max_p95_latency_ms is not None:
            lp95 = p.latency.p95_ms if p.latency else None
            if lp95 is None or lp95 > c.max_p95_latency_ms:
                return False
        if c.required_capabilities and not all(p.has(cap) for cap in c.required_capabilities):
            return False
        if c.allow_local_only and p.provider not in {ProviderType.OLLAMA}:
            return False
        return not (c.allow_remote_only and p.provider in {ProviderType.OLLAMA})

    def _score(
        self,
        p: ModelProfile,
        input_tokens: int,
        output_tokens: int,
    ) -> ScoredModel:
        cost = (input_tokens / 1000.0) * p.input_cost_per_1k + (output_tokens / 1000.0) * p.output_cost_per_1k
        # Inverse cost: 1.0 means free, 0.0 means >$1.00 total call.
        cost_component = 1.0 - min(1.0, cost / 1.0)
        p95 = p.latency.p95_ms if p.latency else None
        # 1.0 at <=200ms, 0.0 at >=30s.
        latency_component = 0.5 if p95 is None or p95 <= 0 else 1.0 - min(1.0, max(0.0, (p95 - 200.0)) / (30_000.0 - 200.0))
        components = {
            "quality": p.quality,
            "reasoning": p.reasoning,
            "tool_use": p.tool_use,
            "code": p.code,
            "vision": p.vision,
            "multimodal": p.multimodal,
            "inverse_cost": cost_component,
            "inverse_latency": latency_component,
        }
        w = self._weights
        score = sum(components[k] * w.get(k, 0.0) for k in components)
        return ScoredModel(profile=p, score=score, cost_estimate=cost, components=components)
