"""
Tests for /v1/kernel/{state,stats,traces} observability endpoints.

Strategy:
  * unit tests use a lightweight fake Kernel injected into app.state so
    tests don't need the full lifespan/DB setup (fast, deterministic).
  * integration tests (tests/integration/) use the real lifespan + real
    kernel to validate persistence and E2E.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from noesis.api.routes.kernel import _get_kernel
from noesis.api.routes.kernel import router as kernel_router
from noesis.kernel import Kernel, KernelState

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_fake_kernel(**overrides: Any) -> Kernel:
    """Build a Kernel with fresh scheduler/allocator for tests."""
    k = Kernel.build_default()
    # Override individual attributes for deterministic assertions.
    for key, value in overrides.items():
        setattr(k, key, value)
    return k


@pytest.fixture
def app_with_kernel() -> tuple[FastAPI, Kernel]:
    app = FastAPI()
    k = _make_fake_kernel()
    app.state.kernel = k
    app.include_router(kernel_router, prefix="/v1")

    # Middleware: populate request.state.request_id (the same one the real
    # app's main:create_app uses).  Deps.RequestID reads request.state.request_id.
    @app.middleware("http")
    async def _add_rid(request, call_next):  # type: ignore[no-untyped-def]
        rid = request.headers.get("X-Request-ID") or "test-rid-00000000"
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    # Override dep to return test-local kernel — zero-arg lambda works because
    # FastAPI dependency_overrides engine accepts any callable.
    app.dependency_overrides[_get_kernel] = lambda: k
    return app, k


@pytest.fixture
def client(app_with_kernel) -> TestClient:  # type: ignore[no-untyped-def]
    app, _ = app_with_kernel
    return TestClient(app)


# ---------------------------------------------------------------------------
# /v1/kernel/state
# ---------------------------------------------------------------------------


def test_kernel_state_returns_booting_before_start(client: TestClient, app_with_kernel) -> None:  # type: ignore[no-untyped-def]
    _, _k = app_with_kernel
    resp = client.get("/v1/kernel/state")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["kernel_state"] == KernelState.BOOTING.value
    assert data["agents_registered"] == 0
    assert data["spans_captured"] == 0
    assert data["spans_capacity"] == 10_000
    assert "services_registered" in data
    assert "handlers_registered" in data
    assert data["generated_at"].endswith("Z")


def test_kernel_state_shows_uptime_after_start(client, app_with_kernel) -> None:  # type: ignore[no-untyped-def]
    import asyncio

    _app, k = app_with_kernel
    asyncio.get_event_loop().run_until_complete(k.start())
    resp = client.get("/v1/kernel/state")
    body = resp.json()
    assert resp.status_code == 200
    assert body["data"]["uptime_s"] is not None
    assert body["data"]["uptime_s"] >= 0.0
    assert body["data"]["kernel_state"] == KernelState.RUNNING.value


def test_kernel_state_services_listed(client, app_with_kernel) -> None:  # type: ignore[no-untyped-def]
    _app, k = app_with_kernel
    # Mimic M1.1 wiring: populate _services with repo keys.
    k._services["users"] = object()
    k._services["memories"] = object()
    resp = client.get("/v1/kernel/state")
    data = resp.json()["data"]
    assert "users" in data["services_registered"]
    assert "memories" in data["services_registered"]
    # SysCall handlers (number varies based on SysCall enum size).
    # Just confirm the expected entry points from kernel._handlers exist.
    handler_set = set(data["handlers_registered"])
    assert {"memory_read", "memory_write", "model_route", "tool_invoke", "get_clock"} <= handler_set


# ---------------------------------------------------------------------------
# /v1/kernel/stats
# ---------------------------------------------------------------------------


def test_kernel_stats_returns_sections(client) -> None:
    resp = client.get("/v1/kernel/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    data = body["data"]
    assert {"scheduler", "memory_allocator", "model_router"} <= set(data.keys())
    # Scheduler counters start at zero; at least the counter fields exist
    for counter in (
        "tasks_queued",
        "tasks_running",
        "tasks_done",
        "tasks_failed",
        "tasks_cancelled",
        "deadline_misses",
    ):
        assert counter in data["scheduler"]
    # memory_allocator zones dict + active leases exist.
    assert "zones" in data["memory_allocator"]
    assert "active_leases" in data["memory_allocator"]
    # Model router: 7 default profiles are registered in Kernel.build_default
    assert data["model_router"]["profiles_registered"] >= 7
    assert len(data["model_router"]["profiles"]) >= 7
    assert "outcomes_recorded" in data["model_router"]
    assert "weights" in data["model_router"]


def test_kernel_model_profiles_include_gpu_flag(client) -> None:
    resp = client.get("/v1/kernel/stats")
    profiles = resp.json()["data"]["model_router"]["profiles"]
    providers = {p["provider"] for p in profiles}
    # Default kernel registers at least ollama (local) and OpenAI.
    assert "ollama" in providers or "openai" in providers
    # Every profile carries an explicit GPU flag and cost fields.
    for p in profiles:
        assert "requires_gpu" in p
        assert "model_class" in p
        assert "input_cost_per_1k" in p


def test_kernel_allocator_zones_populated_after_malloc(client, app_with_kernel) -> None:  # type: ignore[no-untyped-def]
    import asyncio

    _app, k = app_with_kernel
    asyncio.get_event_loop().run_until_complete(k.start())
    # Force a memory allocation (syscall MEMORY_WRITE goes through allocator).
    from noesis.kernel.allocators import MemoryZone

    asyncio.get_event_loop().run_until_complete(k._allocator.malloc("test-agent", MemoryZone.WORKING, 128))
    resp = client.get("/v1/kernel/stats")
    zones = resp.json()["data"]["memory_allocator"]["zones"]
    assert zones.get("working", 0) >= 128


# ---------------------------------------------------------------------------
# /v1/kernel/traces
# ---------------------------------------------------------------------------


def test_kernel_traces_empty_shape(client) -> None:
    resp = client.get("/v1/kernel/traces")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["data"]["limit"] == 50  # default
    assert body["data"]["returned"] == 0
    assert body["data"]["spans"] == []


def test_kernel_traces_limit_parameter_validated(client) -> None:
    bad = client.get("/v1/kernel/traces?limit=0")
    assert bad.status_code == 422  # FastAPI validation error (ge=1)
    bad2 = client.get("/v1/kernel/traces?limit=99999")
    assert bad2.status_code == 422  # le=5000


def test_kernel_traces_returns_otel_shape_for_captured_spans(client, app_with_kernel) -> None:  # type: ignore[no-untyped-def]
    _app, k = app_with_kernel
    # Inject handcrafted span samples (matches _record_span output structure).
    now_iso = datetime.now(UTC).isoformat()
    k._span_records.extend(
        [
            {
                "trace_id": "T1",
                "span_id": "S1",
                "syscall": "model_route",
                "success": True,
                "denied": False,
                "latency_ms": 2.3,
                "error": None,
                "ts": now_iso,
            },
            {
                "trace_id": "T2",
                "span_id": "S2",
                "syscall": "tool_invoke",
                "success": False,
                "denied": True,
                "latency_ms": 5.1,
                "error": "Capability denied",
                "ts": now_iso,
            },
        ]
    )
    resp = client.get("/v1/kernel/traces?limit=100")
    data = resp.json()["data"]
    assert data["returned"] == 2
    span1, span2 = data["spans"]
    assert span1["trace_id"] == "T1"
    assert span1["success"] is True
    assert span1["syscall"] == "model_route"
    assert span1["error"] is None
    assert span2["denied"] is True
    assert span2["error"] == "Capability denied"


def test_kernel_traces_respects_limit(client, app_with_kernel) -> None:  # type: ignore[no-untyped-def]
    _app, k = app_with_kernel
    for i in range(10):
        k._span_records.append(
            {
                "trace_id": str(i),
                "span_id": str(i),
                "syscall": "clock",
                "success": True,
                "denied": False,
                "latency_ms": 0.1,
                "error": None,
                "ts": "2025-01-01T00:00:00Z",
            }
        )
    resp = client.get("/v1/kernel/traces?limit=3")
    body = resp.json()
    assert body["data"]["returned"] == 3
    # Most recent 3 returned (dump_recent_spans slices from the end).
    returned_trace_ids = [s["trace_id"] for s in body["data"]["spans"]]
    assert returned_trace_ids == ["7", "8", "9"]
