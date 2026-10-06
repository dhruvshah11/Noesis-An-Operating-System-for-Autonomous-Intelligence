"""Evidence collector (documentation audit) — runs against an isolated scratch copy.

Mode is selected with env NOESIS_EVIDENCE_MODE = deterministic | llm.
Writes evidence_<mode>.json next to this file.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODE = os.environ.get("NOESIS_EVIDENCE_MODE", "deterministic")
os.chdir(HERE)
(HERE / "data").mkdir(exist_ok=True)
db = HERE / "data" / f"evidence_{MODE}.db"
if db.exists():
    db.unlink()
os.environ.update(
    {
        "APP_ENV": "development",
        "DATABASE_URL": f"sqlite+aiosqlite:///./data/evidence_{MODE}.db",
        "QDRANT_URL": "http://127.0.0.1:6333",
        "REDIS_URL": "redis://127.0.0.1:6379/0",
        "EVAL_ROOT": str(HERE / "docs" / "eval"),
    }
)
if MODE == "deterministic":
    os.environ["OLLAMA_BASE_URL"] = "http://127.0.0.1:9"  # unreachable -> deterministic fallback
sys.path.insert(0, str(HERE))

from fastapi.testclient import TestClient  # noqa: E402

from noesis.api.main import create_app  # noqa: E402
from noesis.config import get_settings  # noqa: E402

get_settings.cache_clear()
S = get_settings()

OUT: dict = {"mode": MODE, "python": sys.version, "examples": [], "latency": {}, "notes": []}


def trunc(obj, n=2500):
    s = json.dumps(obj, default=str, ensure_ascii=False)
    if len(s) <= n:
        return obj
    return {"__truncated__": True, "preview": s[:n]}


def call(c, method, path, label, **kw):
    t0 = time.perf_counter()
    r = c.request(method, path, **kw)
    dt = (time.perf_counter() - t0) * 1000
    try:
        body = r.json()
    except Exception:
        body = r.text[:1500]
    req = {k: v for k, v in kw.items() if k in ("json", "params", "headers", "data")}
    if "headers" in req:
        req["headers"] = {k: (v[:24] + "…" if len(v) > 28 else v) for k, v in req["headers"].items()}
    OUT["examples"].append(
        {"label": label, "method": method, "path": path, "request": req, "status": r.status_code, "ms": round(dt, 2), "response": trunc(body)}
    )
    return r, body


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def cap_token(caps, *, exp_delta=3600, deny=(), secret=None):
    now = int(time.time())
    payload = {
        "owner": "doc-audit",
        "workspace_id": "audit",
        "expires_at_unix_s": now + exp_delta,
        "capabilities": list(caps),
        "deny_masks": list(deny),
        "issued_at_unix_s": now,
    }
    pj = json.dumps(payload, sort_keys=True)
    key = (secret or S.claim_suites_hmac_secret.get_secret_value()).encode()
    mac = hmac.new(key, pj.encode(), hashlib.sha256).digest()
    return b64u(pj.encode()) + "." + b64u(mac)


def bench(c, method, path, n, **kw):
    xs = []
    for _ in range(n):
        t0 = time.perf_counter()
        r = c.request(method, path, **kw)
        xs.append((time.perf_counter() - t0) * 1000)
        assert r.status_code < 500, (path, r.status_code, r.text[:300])
    xs.sort()
    return {
        "n": n,
        "mean_ms": round(statistics.mean(xs), 3),
        "p50_ms": round(xs[len(xs) // 2], 3),
        "p95_ms": round(xs[min(len(xs) - 1, int(0.95 * len(xs)))], 3),
        "min_ms": round(xs[0], 3),
        "max_ms": round(xs[-1], 3),
        "status": r.status_code,
    }


GOAL = "Write a Python function parse_csv.py that parses CSV files and add unit tests"

with TestClient(create_app()) as c:
    # ---------------- health / meta ----------------
    call(c, "GET", "/", "root")
    call(c, "GET", "/health/livez", "livez")
    call(c, "GET", "/health/readyz", "readyz")
    call(c, "GET", "/v1/health", "v1 health")
    call(c, "GET", "/v1/kernel/state", "kernel state")
    call(c, "GET", "/v1/kernel/stats", "kernel stats")
    call(c, "GET", "/v1/kernel/traces", "kernel traces", params={"limit": 5})
    # ---------------- auth ----------------
    r, tp = call(c, "POST", "/v1/auth/login", "login ok", json={"user_id": "demo", "password": "Demo!12345678"})
    access = tp.get("access_token", "")
    refresh = tp.get("refresh_token", "")
    call(c, "GET", "/v1/auth/me", "me ok", headers={"Authorization": f"Bearer {access}"})
    call(c, "GET", "/v1/auth/me", "me missing token")
    tampered = access[:-2] + ("A" if access[-2] != "A" else "B") + access[-1]
    call(c, "GET", "/v1/auth/me", "me tampered token", headers={"Authorization": f"Bearer {tampered}"})
    call(c, "GET", "/v1/auth/me", "me with refresh token (wrong use)", headers={"Authorization": f"Bearer {refresh}"})
    call(c, "POST", "/v1/auth/refresh", "refresh ok", headers={"Authorization": f"Bearer {refresh}"})
    call(c, "POST", "/v1/auth/login", "login bad password", json={"user_id": "demo", "password": "wrong-password-1"})
    call(c, "POST", "/v1/auth/login", "login unknown user", json={"user_id": "nobody", "password": "whatever-123"})
    call(c, "POST", "/v1/auth/login", "login validation error (short pw)", json={"user_id": "demo", "password": "x"})
    statuses = []
    for _ in range(6):
        rr = c.post("/v1/auth/login", json={"user_id": "ratelimit", "password": "wrong-password-1"})
        statuses.append(rr.status_code)
    OUT["rate_limit_login_statuses"] = statuses
    call(c, "POST", "/v1/auth/login", "login rate limited (7th)", json={"user_id": "ratelimit", "password": "wrong-password-1"})
    call(c, "GET", "/v1/observability/summary", "observability summary", params={"window_s": 600})
    # ---------------- agents ----------------
    call(c, "GET", "/v1/agents", "agents list")
    call(c, "POST", "/v1/agents/invoke", "invoke planner", json={"agent": "planner", "state": {"goal": GOAL, "seed": 42}})
    call(c, "POST", "/v1/agents/invoke", "invoke reflection", json={"agent": "reflection", "state": {"answer": "The API is safe. The API is not safe. See docs."}})
    call(c, "POST", "/v1/agents/invoke", "invoke research (no seeds)", json={"agent": "research", "state": {"query": "capability based security"}})
    call(c, "POST", "/v1/agents/invoke", "invoke unknown agent", json={"agent": "judge", "state": {}})
    # ---------------- runs ----------------
    r, plan_env = call(c, "POST", "/v1/runs/plan", "runs plan", json={"goal": GOAL, "seed": 42})
    plan = plan_env["data"]["plan"]
    t0 = time.perf_counter()
    r, ex_env = call(c, "POST", "/v1/runs/execute", "runs execute", json={"plan": plan})
    OUT["execute_wall_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    OUT["execute_steps"] = [
        {k: s.get(k) for k in ("agent_type", "status", "duration_ms", "tokens_in", "tokens_out", "report_type", "result_preview")}
        for s in ex_env["data"]["steps"]
    ]
    run_id = ex_env["data"]["run_id"]
    call(c, "GET", f"/v1/runs/{run_id}/executions", "executions by run_id")
    call(c, "POST", "/v1/runs/execute", "execute invalid plan", json={"plan": {"goal": "x"}})
    # ---------------- conversations ----------------
    r, conv_env = call(c, "POST", "/v1/conversations", "conversation create", json={"title": GOAL, "agent": "orchestrator", "tags": ["audit"]})
    conv_id = conv_env["data"]["id"]
    t0 = time.perf_counter()
    final = None
    for _ in range(600):
        time.sleep(0.5)
        g = c.get(f"/v1/conversations/{conv_id}").json()["data"]
        if g["status"] in ("completed", "failed"):
            final = g
            break
    OUT["conversation_bg_run_wall_s"] = round(time.perf_counter() - t0, 2)
    OUT["conversation_final"] = trunc(final, 6000)
    call(c, "GET", f"/v1/conversations/{conv_id}", "conversation get", params={"limit_messages": 3})
    call(c, "GET", "/v1/conversations", "conversation list", params={"limit": 5})
    call(c, "PATCH", f"/v1/conversations/{conv_id}", "conversation patch", json={"title": "Renamed audit thread", "tags": ["audit", "doc"]})
    call(c, "POST", f"/v1/conversations/{conv_id}/messages", "message append", json={"role": "user", "content": "Please also document edge cases."})
    call(c, "GET", f"/v1/conversations/{conv_id}/messages", "messages list", params={"limit": 2})
    call(c, "GET", "/v1/conversations/00000000-0000-0000-0000-000000000000", "conversation 404")
    call(c, "POST", "/v1/conversations", "conversation 422", json={})
    call(c, "GET", f"/v1/runs/{conv_id}/executions", "executions by conversation id")
    # ---------------- documents ----------------
    r, d = call(c, "POST", "/v1/documents", "document create", json={"title": "Design notes", "source_uri": "file:///notes.md", "mime_type": "text/markdown"})
    doc_id = d["data"]["id"]
    call(c, "GET", "/v1/documents", "documents list")
    call(c, "GET", f"/v1/documents/{doc_id}", "document get")
    payload = ("NOESIS audit upload. " * 300).encode()
    call(c, "POST", "/v1/documents/upload", "document upload", files={"file": ("audit.txt", payload, "text/plain")}, data={"title": "Audit upload"})
    call(c, "DELETE", f"/v1/documents/{doc_id}", "document delete")
    call(c, "DELETE", f"/v1/documents/{doc_id}", "document delete again (404)")
    # ---------------- memory ----------------
    call(c, "GET", "/v1/memory", "memory list")
    call(c, "POST", "/v1/memory/query", "memory query", json={"content": "csv parsing tests", "top_k": 5})
    call(c, "POST", "/v1/memory/compress", "memory compress", json={"older_than_days": 30})
    # ---------------- uap ----------------
    call(c, "GET", "/v1/uap/transports", "uap transports")
    call(c, "POST", "/v1/uap/transports/inproc", "uap bind inproc", json={"actor_id": "audit-actor", "capabilities": ["send_message"]})
    call(c, "POST", "/v1/uap/envelope/send", "uap envelope send", json={"from": "a", "to": "b", "kind": "message", "payload": {"x": 1}})
    # ---------------- metrics ----------------
    rm = c.get("/metrics")
    OUT["metrics_text_preview"] = rm.text[:3000]
    OUT["metrics_content_type"] = rm.headers.get("content-type")
    call(c, "GET", "/v1/metrics_json", "metrics json")
    # ---------------- capability gate (C1) ----------------
    good = cap_token(["llm.benchmark.read", "bench.results.read"])
    call(c, "GET", "/llm/benchmark", "llm benchmark no token")
    call(c, "GET", "/llm/benchmark", "llm benchmark malformed token", headers={"X-Noesis-Capability-Token": "not-a-token"})
    call(c, "GET", "/llm/benchmark", "llm benchmark wrong secret", headers={"X-Noesis-Capability-Token": cap_token(["llm.benchmark.read"], secret="attacker-secret")})
    call(c, "GET", "/llm/benchmark", "llm benchmark expired", headers={"X-Noesis-Capability-Token": cap_token(["llm.benchmark.read"], exp_delta=-10)})
    call(c, "GET", "/llm/benchmark", "llm benchmark missing cap", headers={"X-Noesis-Capability-Token": cap_token(["bench.results.read"])})
    call(c, "GET", "/llm/benchmark", "llm benchmark deny mask", headers={"X-Noesis-Capability-Token": cap_token(["llm.benchmark.read"], deny=["llm.*"])})
    call(c, "GET", "/llm/benchmark", "llm benchmark ok", headers={"X-Noesis-Capability-Token": good}, params={"prompt_tokens": 64})
    call(c, "GET", "/api/bench/results", "bench results ok", headers={"X-Noesis-Capability-Token": good})
    call(c, "GET", "/api/bench/results", "bench results no token")

    if MODE == "deterministic":
        # ---------------- latency micro-benchmarks (in-process) ----------------
        L = OUT["latency"]
        L["GET /health/livez"] = bench(c, "GET", "/health/livez", 200)
        L["GET /health/readyz"] = bench(c, "GET", "/health/readyz", 50)
        L["GET /v1/kernel/state"] = bench(c, "GET", "/v1/kernel/state", 200)
        L["GET /v1/agents"] = bench(c, "GET", "/v1/agents", 200)
        L["GET /v1/conversations"] = bench(c, "GET", "/v1/conversations", 100, params={"limit": 25})
        L["GET /v1/documents"] = bench(c, "GET", "/v1/documents", 100)
        L["POST /v1/memory/query"] = bench(c, "POST", "/v1/memory/query", 100, json={"content": "csv parsing", "top_k": 5})
        L["POST /v1/auth/login"] = bench(c, "POST", "/v1/auth/login", 4, json={"user_id": "admin", "password": "change-me-please"})
        L["POST /v1/runs/plan"] = bench(c, "POST", "/v1/runs/plan", 50, json={"goal": GOAL, "seed": 42})
        L["POST /v1/runs/execute"] = bench(c, "POST", "/v1/runs/execute", 10, json={"plan": plan})
        L["GET /metrics"] = bench(c, "GET", "/metrics", 100)
        L["GET /api/bench/results"] = bench(c, "GET", "/api/bench/results", 30, headers={"X-Noesis-Capability-Token": good})
    else:
        # ---------------- live local LLM throughput via /llm/benchmark ----------------
        runs = []
        for pt in (64, 256, 1024):
            for _ in range(3):
                rr = c.get(
                    "/llm/benchmark",
                    headers={"X-Noesis-Capability-Token": good},
                    params={"prompt_tokens": pt, "model": "qwen2.5-coder:7b-instruct-q4_K_M"},
                    timeout=600,
                )
                runs.append(rr.json().get("data"))
        OUT["llm_benchmark_runs"] = runs

(HERE / f"evidence_{MODE}.json").write_text(json.dumps(OUT, indent=1, default=str, ensure_ascii=False), encoding="utf-8")
print("wrote", f"evidence_{MODE}.json", len(OUT["examples"]), "examples")
