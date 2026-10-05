"""Tests for GET /api/bench/results — Benchmark Results Hub endpoint.

Uses TestClient against the real FastAPI app.  The endpoint either returns
real data (if ``tables_for_paper.json`` exists under ``eval_root``) or falls
back to demo-mode placeholders.  Both code paths must return a well-formed
BenchmarkResults envelope (200).
"""

from __future__ import annotations

import base64
import hmac
import json
import time
from hashlib import sha256
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from noesis.config import get_settings


def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _sign(payload_json: str, key: bytes) -> bytes:
    return hmac.new(key, payload_json.encode("utf-8"), sha256).digest()


def _valid_headers(*, cap: str = "bench.results.read") -> dict[str, str]:
    """Fabricate a valid, signed X-Noesis-Capability-Token header for smoke tests.

    Non-claim-suite tests don't exercise deny paths — they just need a token
    that passes the gate so the endpoint business logic can be tested.
    """
    settings = get_settings()
    key = settings.claim_suites_hmac_secret.get_secret_value().encode("utf-8")
    now = int(time.time())
    payload = {
        "owner": "smoke-test-agent",
        "workspace_id": "smoke-test-ws",
        "expires_at_unix_s": now + 3600,
        "capabilities": [cap, "llm.benchmark.read"],
        "deny_masks": [],
        "issued_at_unix_s": now,
    }
    payload_json = json.dumps(payload, sort_keys=True)
    payload_b64 = _b64url_encode(payload_json.encode("utf-8"))
    mac = _sign(payload_json, key)
    mac_b64 = _b64url_encode(mac)
    return {"X-Noesis-Capability-Token": f"{payload_b64}.{mac_b64}"}


def test_bench_results_get_200_shape(test_client: TestClient) -> None:
    """GET /api/bench/results → 200 with BenchmarkResults-shaped payload.

    Works whether real data lives on disk or we fall back to demo mode —
    both branches return the same schema envelope.
    """
    resp = test_client.get("/api/bench/results", headers=_valid_headers(cap="bench.results.read"))
    assert resp.status_code == 200, f"Unexpected status {resp.status_code}: {resp.text}"
    body = resp.json()

    assert body["ok"] is True, "Envelope ok flag must be True"
    assert body.get("data") is not None, "Envelope data must be present"

    data = body["data"]
    required_top = {"se50", "se50_rows", "humaneval_pass_at_1", "humaneval_buckets",
                    "mbpp_pass_at_1", "mbpp_buckets", "ablation_table", "signoff_avg_conf"}
    assert required_top.issubset(data.keys()), f"Missing top-level keys: {required_top - set(data.keys())}"

    se50 = data["se50"]
    required_se50 = {"overall_pass_at_1", "overall_ci_low", "overall_ci_high",
                     "n_total", "n_correct", "per_category", "per_difficulty"}
    assert required_se50.issubset(se50.keys()), f"Missing se50 keys: {required_se50 - set(se50.keys())}"
    assert isinstance(se50["overall_pass_at_1"], float)
    assert 0.0 <= se50["overall_pass_at_1"] <= 1.0
    assert isinstance(se50["n_total"], int)
    assert isinstance(se50["n_correct"], int)
    assert isinstance(se50["per_category"], list)
    assert isinstance(se50["per_difficulty"], list)

    assert isinstance(data["se50_rows"], list)

    he_p1 = data["humaneval_pass_at_1"]
    assert isinstance(he_p1, float)
    assert 0.0 <= he_p1 <= 1.0
    assert isinstance(data["humaneval_buckets"], list)

    mbpp_p1 = data["mbpp_pass_at_1"]
    assert isinstance(mbpp_p1, float)
    assert 0.0 <= mbpp_p1 <= 1.0
    assert isinstance(data["mbpp_buckets"], list)

    ablation = data["ablation_table"]
    assert "variant_keys" in ablation
    assert isinstance(ablation["variant_keys"], list)
    assert len(ablation["variant_keys"]) == 3, "ablation_table.variant_keys must be 3-tuple"
    assert isinstance(ablation["rows"], list)
    assert isinstance(ablation["notes"], dict)

    avg_conf = data["signoff_avg_conf"]
    assert isinstance(avg_conf, float)
    assert 0.0 <= avg_conf <= 1.0

    meta = body.get("meta") or {}
    assert "source" in meta


def test_bench_results_refresh_also_200(test_client: TestClient) -> None:
    """GET /api/bench/results?refresh=true → 200 regardless of whether CSVs exist.

    ``refresh=true`` attempts to regenerate tables_for_paper.json from any
    auto-discovered CSVs under eval_root; if none exist the call is a no-op
    and the endpoint still returns a valid 200 (demo or real).
    """
    resp = test_client.get(
        "/api/bench/results",
        params={"refresh": "true"},
        headers=_valid_headers(cap="bench.results.read"),
    )
    assert resp.status_code == 200, f"Unexpected status {resp.status_code}: {resp.text}"
    body = resp.json()

    assert body["ok"] is True
    data = body["data"]
    se50_p1 = data["se50"]["overall_pass_at_1"]
    assert isinstance(se50_p1, float)
    assert 0.0 <= se50_p1 <= 1.0


def test_bench_results_schema_types_and_ranges(test_client: TestClient) -> None:
    """Validate every nested BenchmarkResults field carries correct types/ranges.

    (Same assertion set works for both demo data and real on-disk data.)
    """
    resp = test_client.get("/api/bench/results", headers=_valid_headers(cap="bench.results.read"))
    assert resp.status_code == 200
    data = resp.json()["data"]

    for cat in data["se50"]["per_category"]:
        for k in ("category", "n_total", "n_correct", "pass_at_1", "ci_low", "ci_high"):
            assert k in cat, f"per_category item missing key '{k}'"
        assert cat["n_total"] >= 0
        assert cat["n_correct"] >= 0
        assert 0.0 <= cat["pass_at_1"] <= 1.0
        assert 0.0 <= cat["ci_low"] <= 1.0
        assert 0.0 <= cat["ci_high"] <= 1.0

    for diff in data["se50"]["per_difficulty"]:
        for k in ("difficulty", "n_total", "n_correct", "pass_at_1"):
            assert k in diff, f"per_difficulty item missing key '{k}'"
        assert diff["n_total"] >= 0
        assert diff["n_correct"] >= 0
        assert 0.0 <= diff["pass_at_1"] <= 1.0

    for row in data["se50_rows"]:
        for k in ("task_id", "category", "difficulty", "tristate",
                  "duration_ms", "plan_sha", "kriyakari_conf"):
            assert k in row, f"se50_row missing key '{k}'"
        assert isinstance(row["duration_ms"], int) and row["duration_ms"] >= 0
        assert 0.0 <= float(row["kriyakari_conf"]) <= 1.0
        assert row["tristate"] in {"signoff", "reject", "replan"}

    for he in data["humaneval_buckets"]:
        for k in ("task_id", "codename", "pass_rate", "n_samples"):
            assert k in he, f"humaneval_bucket missing key '{k}'"
        assert 0.0 <= float(he["pass_rate"]) <= 1.0
        assert isinstance(he["n_samples"], int) and he["n_samples"] >= 0

    for mb in data["mbpp_buckets"]:
        for k in ("bucket", "difficulty", "pass_at_1", "n_tasks"):
            assert k in mb, f"mbpp_bucket missing key '{k}'"
        assert 1 <= int(mb["difficulty"]) <= 5
        assert 0.0 <= float(mb["pass_at_1"]) <= 1.0
        assert isinstance(mb["n_tasks"], int) and mb["n_tasks"] >= 0


def test_bench_results_demo_mode_explicit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Force demo mode by overriding eval_root with an empty temp dir.

    This is the only test that pins demo-mode sentinel values (0.40, 0.0, etc.)
    so it reliably asserts the fallback branch regardless of the developer's
    local docs/eval contents.
    """
    empty_eval = tmp_path / "empty_eval"
    empty_eval.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("EVAL_ROOT", str(empty_eval))

    from noesis.config import get_settings
    get_settings.cache_clear()
    assert get_settings().eval_root == str(empty_eval)

    from fastapi.testclient import TestClient

    from noesis.api.main import create_app
    from noesis.database import sql as _sql

    _sql._engine = None
    _sql._session_factory = None

    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/bench/results", headers=_valid_headers(cap="bench.results.read"))
        assert resp.status_code == 200, f"Unexpected {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["ok"] is True
        meta = body.get("meta") or {}
        assert meta.get("demo") is True, f"Expected demo=True with empty eval_root; meta={meta!r}"
        data = body["data"]
        assert data["se50"]["overall_pass_at_1"] == 0.40
        assert data["humaneval_pass_at_1"] == 0.0
        assert data["mbpp_pass_at_1"] == 0.0

    get_settings.cache_clear()


def test_llm_benchmark_endpoint_still_works(test_client: TestClient) -> None:
    """Regression check: older sibling GET /llm/benchmark must still return 200.

    (Adding the bench_results router shouldn't disturb existing llm_benchmark.)
    """
    resp = test_client.get("/llm/benchmark", headers=_valid_headers(cap="llm.benchmark.read"))
    assert resp.status_code == 200, f"Sibling /llm/benchmark broken: {resp.status_code} {resp.text[:200]}"
    body = resp.json()
    assert body["ok"] is True, "/llm/benchmark envelope must be ok=true"
    assert "data" in body
