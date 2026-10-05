"""
Prometheus (OpenMetrics) instrumentation for the Noesis Kernel MVP.

Registers a module-level singleton registry with:

  * Counters:
      backend_http_requests_total{method, route, status}
      backend_task_executions_total{agent_type, status}

  * Summaries (count + sum aggregations):
      backend_http_duration_seconds
      backend_step_duration_ms
      backend_tokens_total{kind}   # kind = "in" | "out"

Exposes at two URL paths via FastAPI routes:
  GET /metrics       — Prometheus scrape convention (text/plain; version=0.0.4)
  GET /v1/metrics    — JSON envelope for the dashboard widget

Helpers `observe_http()` and `observe_step()` are pure — they silently no-op
when called before the registry is created (or in tests), so they can be
sprinkled liberally through request handlers / AgentSvc without guards.

Design rationale (10yr-abstraction rule): keep this module *independent* of
FastAPI/DI so it is equally usable from CLI workers, cron scripts, or async
worker processes.  The route-wiring is kept in astra.api.routes.v1_metrics so
the metrics module stays single responsibility.
"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from time import perf_counter_ns
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

# ---------------------------------------------------------------------------
# Lazy import so the module is importable even if prometheus_client is not
# installed (we gate with try/except ImportError + _Stub no-op shim).  This
# matches the "offline-safe" pattern used across the kernel so deploys that
# don't need metrics are not forced to carry the dependency.
# ---------------------------------------------------------------------------
try:  # pragma: no cover - branch is trivially verified at import time
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Summary,
        generate_latest,
    )
    from prometheus_client import (
        REGISTRY as _DEFAULT_REGISTRY,
    )

    _PROM_INSTALLED = True
except Exception:  # pragma: no cover - defences against any import weirdness
    _PROM_INSTALLED = False
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    _DEFAULT_REGISTRY = object()  # type: ignore[assignment]


_NS_PER_SEC = 1_000_000_000


# ---------------------------------------------------------------------------
# Counter / Summary shims.  We intentionally *don't* expose the prometheus
# classes directly to application code so we can swap implementations or
# disable globally without touching call sites.
# ---------------------------------------------------------------------------
@dataclass
class _StubMetric:
    name: str
    documentation: str = ""

    def labels(self, **_kv):  # type: ignore[no-untyped-def]
        return self

    def inc(self, *a, **kw):  # type: ignore[no-untyped-def]
        return None

    def observe(self, *a, **kw):  # type: ignore[no-untyped-def]
        return None


if _PROM_INSTALLED:
    HTTP_REQ: Counter = Counter(
        "backend_http_requests_total",
        "Total HTTP requests handled by the backend v1 API.",
        labelnames=("method", "route", "status"),
    )
    TASK_EXEC: Counter = Counter(
        "backend_task_executions_total",
        "Total planner step executions handled by AgentSvc.",
        labelnames=("agent_type", "status"),
    )
    TOKENS: Counter = Counter(
        "backend_tokens_total",
        "LLM tokens consumed, partitioned by kind (in/out).",
        labelnames=("kind",),
    )
    HTTP_DUR: Summary = Summary(
        "backend_http_duration_seconds",
        "Elapsed wall time per HTTP request, in seconds.",
        labelnames=("method", "route"),
    )
    STEP_DUR: Summary = Summary(
        "backend_step_duration_ms",
        "Elapsed wall time per AgentSvc run_step() call, in milliseconds.",
        labelnames=("agent_type",),
    )
else:  # pragma: no cover - defensive stub path
    HTTP_REQ = _StubMetric("backend_http_requests_total")  # type: ignore[assignment]
    TASK_EXEC = _StubMetric("backend_task_executions_total")  # type: ignore[assignment]
    TOKENS = _StubMetric("backend_tokens_total")  # type: ignore[assignment]
    HTTP_DUR = _StubMetric("backend_http_duration_seconds")  # type: ignore[assignment]
    STEP_DUR = _StubMetric("backend_step_duration_ms")  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Public helper API.  All functions are fire-and-forget: they never raise.
# ---------------------------------------------------------------------------
def observe_http_request(
    method: str,
    route: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    """Record an HTTP request against the counters + duration summary."""
    with suppress(Exception):
        meth = (method or "GET").upper()
        status = str(int(status_code))
        HTTP_REQ.labels(method=meth, route=route or "/", status=status).inc()
        HTTP_DUR.labels(method=meth, route=route or "/").observe(duration_seconds)


def observe_step_run(
    agent_type: str,
    status: str,
    duration_ms: float,
    tokens_in: int = 0,
    tokens_out: int = 0,
) -> None:
    """Record a single step execution from AgentSvc.run_step()."""
    with suppress(Exception):
        atype = agent_type or "unknown"
        st = status or "UNKNOWN"
        TASK_EXEC.labels(agent_type=atype, status=st).inc()
        STEP_DUR.labels(agent_type=atype).observe(max(0.0, float(duration_ms)))
        if tokens_in:
            TOKENS.labels(kind="in").inc(max(0, int(tokens_in)))
        if tokens_out:
            TOKENS.labels(kind="out").inc(max(0, int(tokens_out)))


def render_text() -> tuple[str, str]:
    """Return (body_text, content_type) for the latest prometheus scrape."""
    if not _PROM_INSTALLED:  # pragma: no cover - trivially exercised
        return (
            "# prometheus_client not installed — metrics disabled.\n",
            CONTENT_TYPE_LATEST,
        )
    data = generate_latest(_DEFAULT_REGISTRY)
    body = data.decode("utf-8", errors="replace") if isinstance(data, (bytes, bytearray)) else str(data)
    return body, CONTENT_TYPE_LATEST


def snapshot_as_dict() -> dict[str, object]:
    """JSON-serializable snapshot of current counter/summary totals.

    Used by GET /v1/metrics (JSON envelope) so the dashboard metrics page
    renders without scraping raw prometheus text.
    """
    snap: dict[str, object] = {
        "counters": {},
        "summaries": {},
        "prometheus_installed": _PROM_INSTALLED,
    }
    if not _PROM_INSTALLED:  # pragma: no cover - defensive path
        return snap
    counters: dict[str, object] = {}
    summaries: dict[str, object] = {}
    with suppress(Exception):
        # Walk the default registry; samples are pre-aggregated
        for metric in _DEFAULT_REGISTRY.collect():
            name = metric.name
            mtype = getattr(metric, "type", "unknown")
            for sample in metric.samples or []:
                sname = sample.name
                labels = dict(sample.labels or {})
                value = sample.value
                is_counter_total = sname.endswith("_total")
                is_created = sname.endswith("_created")
                is_summary_tail = sname.endswith("_sum") or sname.endswith("_count")
                key_parts = [f"{k}={v}" for k, v in sorted(labels.items())]
                key = ",".join(key_parts) or "*"
                if is_counter_total:
                    counters.setdefault(name, {})
                    counters[name][key] = value  # type: ignore[index]
                elif is_created:
                    # skip _created timestamps: counters bucket already has
                    # the useful total; dropping keeps snapshots small.
                    pass
                elif is_summary_tail:
                    summaries.setdefault(name, {})
                    summaries[name].setdefault(key, {})
                    suffix = sname.rsplit("_", 1)[-1]
                    summaries[name][key][suffix] = value  # type: ignore[index]
                elif mtype == "summary" and sname == name:
                    # Summary metric that has no explicit _sum/_count suffix
                    # (e.g., prometheus_client Summary samples without
                    # quantiles — fall back to bucketing it with a single
                    # "value" key under summaries[name][key]).
                    summaries.setdefault(name, {})
                    summaries[name].setdefault(key, {})
                    summaries[name][key]["value"] = value  # type: ignore[index]
    snap["counters"] = counters
    snap["summaries"] = summaries
    return snap


def http_timer(method: str, route: str) -> Callable[[int], float]:
    """Context-ish helper: returns a function `stop(status_code)` that
    records duration + counter.  Uses perf_counter_ns for sub-ms precision.

    Usage:
        stop = http_timer("GET", "/v1/conversations")
        ... do work ...
        elapsed_s = stop(200)
    """
    start = perf_counter_ns()

    def _stop(status_code: int) -> float:
        elapsed_ns = perf_counter_ns() - start
        elapsed_s = elapsed_ns / _NS_PER_SEC
        observe_http_request(method, route, status_code, elapsed_s)
        return elapsed_s

    return _stop
