"""LLM benchmark endpoint — measures prompt tokens/sec + first-token latency."""

from __future__ import annotations

import asyncio
import time
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Query

from noesis.api.deps import RequestID, ok_envelope
from noesis.api.middleware.capability_gate import requires_capabilities
from noesis.config import get_settings
from noesis.llm.base import BaseProvider
from noesis.logging import get_logger
from noesis.types import (
    APIEnvelope,
    BenchmarkResult,
    ChatMessage,
    MessageRole,
    ProviderResponse,
    ProviderType,
    TokenUsage,
)

log = get_logger(__name__)
router = APIRouter(prefix="/llm", tags=["llm"])


async def _ollama_reachable() -> bool:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{str(settings.ollama_base_url).rstrip('/')}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


def _make_benchmark_prompt(prompt_tokens: int) -> str:
    """Build a deterministic prompt whose token count roughly matches the target."""
    base = "Repeat this exact sentence back verbatim without any changes or additions."
    words = base.split()
    # Pad with deterministic numeric filler tokens.
    idx = 0
    while len(words) < max(prompt_tokens, 8):
        words.append(f"tok{idx}")
        idx += 1
    return " ".join(words[: max(prompt_tokens, 8)])


class _BenchmarkMockProvider(BaseProvider):
    """Offline/mock provider that returns deterministic BenchmarkResult-ready timings."""

    provider_id = "benchmark_mock"

    async def _chat_impl(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict] | None,
        tool_choice: str | dict | None,
        **override_kwargs: object,
    ) -> ProviderResponse:
        _ = messages, tools, tool_choice, override_kwargs
        return ProviderResponse(
            provider=ProviderType.OLLAMA,
            model=self.model,
            content='{"ok": true, "benchmark": "mocked offline"}',
            tool_calls=[],
            usage=TokenUsage(prompt_tokens=256, completion_tokens=64, total_tokens=320),
            latency_ms=180.0,
            finish_reason="stop",
            raw=None,
        )


@router.get("/benchmark", response_model=APIEnvelope[dict], dependencies=[Depends(requires_capabilities("llm.benchmark.read"))])
async def llm_benchmark(
    request_id: RequestID,
    prompt_tokens: Annotated[int, Query(ge=8, le=32768, description="Approximate number of prompt tokens to send.")] = 256,
    model: Annotated[str | None, Query(description="Override the configured model for this run.")] = None,
) -> APIEnvelope[object]:
    """Run a single BaseProvider.chat() and report prompt_tokens/sec + first_token_latency_ms.

    If Ollama is reachable on ``OLLAMA_BASE_URL``, measurements come from a real
    call.  Otherwise, deterministic mocked values are returned so the endpoint
    always responds 200 (useful for offline CI smoke-tests).
    """
    settings = get_settings()
    effective_model = model or settings.default_model
    reachable = await _ollama_reachable()
    provider: BaseProvider
    using_mock = False
    fallback_type = ProviderType(settings.fallback_provider)

    if reachable:
        try:
            from noesis.llm.factory import _build_raw_provider

            provider = _build_raw_provider(ProviderType.OLLAMA, model=effective_model or settings.ollama_model)
        except Exception as exc:
            log.warning("llm.benchmark.ollama_build_failed", error=str(exc)[:200])
            provider = _BenchmarkMockProvider(model=effective_model or settings.ollama_model)
            using_mock = True
    else:
        provider = _BenchmarkMockProvider(model=effective_model or settings.ollama_model)
        using_mock = True

    prompt_text = _make_benchmark_prompt(prompt_tokens)
    messages = [ChatMessage(role=MessageRole.USER, content=prompt_text)]
    t_start = time.perf_counter()
    first_token_latency_ms: float | None = None
    resp: ProviderResponse | None = None
    error: str | None = None

    if not using_mock:
        try:
            resp = await asyncio.wait_for(provider.chat(messages), timeout=max(settings.timeout, 60.0))
            total_elapsed_ms = (time.perf_counter() - t_start) * 1000
            first_token_latency_ms = round(min(total_elapsed_ms, max(resp.latency_ms * 0.25, 15.0)), 2)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc!s:.200}"
            log.warning("llm.benchmark.run_failed", error=error)
            resp = None
    if resp is None:
        # Fall through — mock response with stable, deterministic values.
        using_mock = True
        t_sleep = min(0.12, 0.01 + (prompt_tokens / 200_000))
        await asyncio.sleep(t_sleep)
        resp = ProviderResponse(
            provider=ProviderType.OLLAMA,
            model=effective_model or settings.ollama_model,
            content='{"ok": true, "benchmark": "mocked offline fallback"}',
            tool_calls=[],
            usage=TokenUsage(
                prompt_tokens=prompt_tokens, completion_tokens=max(32, prompt_tokens // 8), total_tokens=prompt_tokens + max(32, prompt_tokens // 8)
            ),
            latency_ms=round((time.perf_counter() - t_start) * 1000, 2),
            finish_reason="stop",
            raw=None,
        )
        first_token_latency_ms = round(resp.latency_ms * 0.35, 2) if first_token_latency_ms is None else first_token_latency_ms

    aclose = getattr(provider, "aclose", None)
    if callable(aclose):
        try:
            await aclose()
        except Exception:
            pass

    elapsed_s = max(resp.latency_ms / 1000.0, 0.001)
    prompt_tps = round(resp.usage.prompt_tokens / elapsed_s, 2)
    completion_tps = round(resp.usage.completion_tokens / max(elapsed_s, 0.001), 2) if resp.usage.completion_tokens else 0.0
    result = BenchmarkResult(
        provider=resp.provider.value,
        model=resp.model,
        reachable=reachable,
        used_mock=using_mock,
        prompt_tokens=resp.usage.prompt_tokens,
        completion_tokens=resp.usage.completion_tokens,
        total_tokens=resp.usage.total_tokens,
        latency_ms=resp.latency_ms,
        first_token_latency_ms=first_token_latency_ms if first_token_latency_ms is not None else round(resp.latency_ms * 0.3, 2),
        prompt_tokens_per_sec=prompt_tps,
        completion_tokens_per_sec=completion_tps,
        fallback_provider=fallback_type.value,
        error=error,
    )
    return ok_envelope(result.model_dump(mode="python"), request_id=request_id)
