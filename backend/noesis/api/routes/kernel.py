"""
Kernel observability endpoints.

Exposes the internal AI Kernel state to sysadmins / observability UIs:

  * ``GET /v1/kernel/state``    — uptime, lifecycle state, counts (agents, plugins)
  * ``GET /v1/kernel/stats``    — scheduler, memory-allocator, model-router aggregates
  * ``GET /v1/kernel/traces``   — recent OTel-shaped syscall span samples (for DAG viz)

All endpoints are read-only.  For security, writes to the kernel go *only*
through syscalls from within an agent context (not HTTP).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request

from noesis.api.deps import RequestID, ok_envelope
from noesis.kernel import Kernel, KernelState
from noesis.types import APIEnvelope

router = APIRouter(prefix="/kernel", tags=["kernel"])


async def _get_kernel(request: Request) -> Kernel:
    """Pull Kernel reference from FastAPI app.state (set in lifespan).

    Tests that don't use the full lifespan fixture can override this dependency
    to inject a test-local Kernel instance.
    """
    kernel: Kernel | None = getattr(request.app.state, "kernel", None)
    if kernel is None:
        # Fallback for tests without full lifespan: try DI container on state too.
        container = getattr(request.app.state, "container", None)
        if container is not None:
            try:
                kernel = await container.get(Kernel)
            except Exception:  # pragma: no cover - defensive
                kernel = None
    if kernel is None:
        raise RuntimeError("Kernel not initialised in app.state.kernel.  Ensure FastAPI.create_app() lifespan() ran before requesting this endpoint.")
    return kernel


@router.get("/state", response_model=APIEnvelope[dict])
async def kernel_state(
    request_id: RequestID,
    kernel: Annotated[Kernel, Depends(_get_kernel)],
) -> APIEnvelope[dict]:
    """Return static + cheap dynamic counters for the running kernel."""
    payload: dict[str, Any] = {
        "kernel_state": kernel.state.value if isinstance(kernel.state, KernelState) else str(kernel.state),
        "uptime_s": round(kernel.uptime_seconds(), 3) if kernel.uptime_seconds() is not None else None,
        "started_at": kernel._started_at.isoformat() if kernel._started_at else None,
        "agents_registered": kernel.agents_registered_count(),
        "services_registered": sorted(kernel._services.keys()),
        "handlers_registered": sorted(s.value for s in kernel._handlers),
        "spans_captured": len(kernel._span_records),
        "spans_capacity": 10_000,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    # Attach plugin count if PluginManager is attached to parent app
    pm = getattr(getattr(kernel, "__app__", None), "state", None)
    if pm and hasattr(pm, "plugins"):
        payload["plugins_loaded"] = len(pm.plugins.list_plugins())
    return ok_envelope(payload, request_id=request_id)


@router.get("/stats", response_model=APIEnvelope[dict])
async def kernel_stats(
    request_id: RequestID,
    kernel: Annotated[Kernel, Depends(_get_kernel)],
) -> APIEnvelope[dict]:
    """Aggregate scheduler, allocator, and model-router counters."""
    payload: dict[str, Any] = {
        "scheduler": kernel.scheduler_stats(),
        "memory_allocator": kernel.allocator_stats(),
        "model_router": kernel.model_router_stats(),
    }
    return ok_envelope(payload, request_id=request_id)


@router.get("/traces", response_model=APIEnvelope[dict])
async def kernel_traces(
    request_id: RequestID,
    kernel: Annotated[Kernel, Depends(_get_kernel)],
    limit: Annotated[int, Query(ge=1, le=5000)] = 50,
) -> APIEnvelope[dict]:
    """Return the most-recent N syscall spans captured in the ring buffer.

    Each entry is OTel-shaped (``trace_id``, ``span_id``, ``latency_ms``,
    ``success``, ``denied``, ``ts``, ``syscall``, ``error``) so a ReactFlow
    or Honeycomb/Grafana frontend can render them without transformation.
    """
    items = kernel.dump_recent_spans(limit=limit)
    return ok_envelope(
        {
            "limit": limit,
            "returned": len(items),
            "spans": items,
        },
        request_id=request_id,
    )
