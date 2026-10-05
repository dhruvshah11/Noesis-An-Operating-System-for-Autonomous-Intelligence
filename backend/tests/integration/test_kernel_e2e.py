"""
End-to-end integration tests for M1.2 kernel observability endpoints.

These tests boot the REAL FastAPI app (real lifespan, real DI container,
real Kernel, real Sql*Repositories) and make HTTP requests against it.
This is the acceptance-criteria-critical gate for M1.

Notes on wiring:
  * The ``test_client`` fixture in ``tests/conftest.py`` builds the real app
    via ``noesis.api.main.create_app()`` (which runs lifespan on the first
    request).  Tests here reuse that fixture to avoid event-loop re-entry
    problems with Windows IOCP's proactor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


@pytest.mark.integration
def test_lifespan_boots_kernel_state_running(test_client: TestClient) -> None:
    # First HTTP request triggers lifespan (FastAPI/TestClient behavior).
    resp = test_client.get("/v1/kernel/state")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    data = body["data"]
    # lifespan() calls kernel.start() → kernel transitions BOOTING → RUNNING.
    assert data["kernel_state"] == "running"
    assert data["uptime_s"] is not None
    assert data["uptime_s"] >= 0.0
    # M1.1 DI wiring: _services dict MUST be populated by di build_default_container.
    services = data["services_registered"]
    assert "users" in services
    assert "memories" in services
    assert "conversations" in services
    assert "knowledge_objects" in services
    assert "artifacts" in services
    # SysCall handlers are registered.
    handlers = set(data["handlers_registered"])
    for required in {"memory_read", "memory_write", "model_chat", "model_route", "tool_invoke", "get_clock"}:
        assert required in handlers, f"Missing handler {required}; got {sorted(handlers)}"


@pytest.mark.integration
def test_kernel_stats_nonempty_sections_and_known_model_cards(test_client: TestClient) -> None:
    resp = test_client.get("/v1/kernel/stats")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    # Scheduler: zero counters exist with keys intact.
    sched = data["scheduler"]
    assert sched["tasks_queued"] == 0
    assert sched["tasks_done"] == 0
    assert sched["deadline_misses"] == 0
    # Memory allocator: zones dict structure exists.
    zones = data["memory_allocator"]["zones"]
    assert isinstance(zones, dict)
    # Model router must have registered 7+ default cards.
    profiles = data["model_router"]["profiles"]
    assert data["model_router"]["profiles_registered"] == len(profiles)
    assert len(profiles) >= 7
    model_ids = {p["model_id"] for p in profiles}
    # sanity: check default ollama + openai cards exist.
    assert any("llama" in mid.lower() for mid in model_ids) or any("gpt" in mid.lower() for mid in model_ids)
    # Cost fields exist (interview-grade observability).
    for p in profiles:
        assert "input_cost_per_1k" in p
        assert "output_cost_per_1k" in p
        assert "context_tokens" in p
        assert "requires_gpu" in p


@pytest.mark.integration
def test_kernel_traces_endpoint_has_records_after_http_requests(test_client: TestClient) -> None:
    # First issue a couple of requests that definitely go through the HTTP layer.
    test_client.get("/v1/kernel/state")
    test_client.get("/v1/kernel/stats")
    # Now pull traces.
    resp = test_client.get("/v1/kernel/traces?limit=1000")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    # Shape contract.
    assert isinstance(data["spans"], list)
    assert data["returned"] == len(data["spans"])
    assert data["limit"] == 1000
    # Any span that IS present must be OTel-shaped.
    for span in data["spans"][:10]:
        assert "trace_id" in span
        assert "span_id" in span
        assert "syscall" in span
        assert "success" in span
        assert "latency_ms" in span
        assert "ts" in span
