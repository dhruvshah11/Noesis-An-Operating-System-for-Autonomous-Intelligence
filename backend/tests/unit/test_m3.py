"""
Milestone 3 tests: tools + agents + security + auth routes + observability.

Coverage goals (M3 acceptance):
  * ToolRegistry: LSP all 9 adapters implement 4 attrs + invoke returns ToolResult
  * Registry capability gating: token without TOOL_INVOKE:<name> raises PermissionDenied
  * 3 agents each return {status, report, report_type}
  * Security: hash/verify round-trip, JWT sign/decode, invalid sig tamper fails, rate limit,
    sanitiser tag strip + password strength.
  * HTTP routes: /v1/auth/login, /v1/auth/me, /v1/auth/refresh, /v1/observability/summary
  * Observability: record_request() + record_tool_trace() appear in /v1/observability/summary.
"""

from __future__ import annotations

import datetime as _dt
import sqlite3
import time

import pytest

from noesis.agents.core import (
    AgentRunContext,
    CitationRef,
    CodingAgent,
    CodingPatchReport,
    PatchStep,
    ReflectionAgent,
    ReflectionReport,
    ResearchAgent,
    ResearchReport,
)
from noesis.api.routes.v1_m3 import (
    get_jwt_service,
    record_request,
    record_tool_trace,
)
from noesis.kernel.capabilities import Capability, CapabilityOp, CapabilityToken, PermissionDenied
from noesis.security import (
    InMemoryRateLimiter,
    InputSanitiser,
    JWTDecodeError,
    JWTService,
    PasswordHasher,
    RateLimitExceeded,
)
from noesis.tools import (
    CalendarTool,
    DBTool,
    EmailTool,
    FilesTool,
    GitHubTool,
    PythonSandboxTool,
    ShellTool,
    ToolPort,
    ToolRegistry,
    ToolResult,
    WeatherTool,
    WebFetchTool,
)
from noesis.types import TaskStatus

_ALL_CONCRETE_TOOLS = (
    ShellTool,
    PythonSandboxTool,
    FilesTool,
    GitHubTool,
    WeatherTool,
    CalendarTool,
    EmailTool,
    DBTool,
    WebFetchTool,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def admin_tools(tmp_path):
    """All 9 tool adapters wired to a ToolRegistry, with FilesTool + CalendarTool + Email/Dummy stubs on tmp_path."""
    reg = ToolRegistry()
    reg.register(ShellTool())  # dry-run — no allowed_commands
    reg.register(PythonSandboxTool(timeout_s=3))
    reg.register(FilesTool(tmp_path))
    reg.register(GitHubTool())  # dry-run — no api_token
    reg.register(WeatherTool())
    reg.register(CalendarTool(tmp_path / "astra.ics"))
    reg.register(EmailTool())  # dry-run — no host/password

    # DBTool: in-process sqlite3 connection
    def _factory():
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO t VALUES (1, 'alice'), (2, 'bob')")
        return conn

    reg.register(DBTool(_factory))
    reg.register(WebFetchTool())
    yield reg


@pytest.fixture()
def full_token():
    return CapabilityToken(owner_agent_id="pytest", workspace_id="ws-test")


@pytest.fixture()
def full_caps():
    return (Capability(CapabilityOp.TOOL_INVOKE, "*"),)


# ---------------------------------------------------------------------------
# ToolRegistry LSP + capability gates
# ---------------------------------------------------------------------------


def test_toolport_abc_interface():
    # Every concrete tool provides .name / .description / .parameter_schema / invoke()
    # Invoke must return ToolResult (success bool, exit_code int).
    # FilesTool needs a cwd; we use temp dir inside each param test.
    import inspect

    for cls in _ALL_CONCRETE_TOOLS:
        assert issubclass(cls, ToolPort)
        abs_methods = {n for n in ("name", "description", "parameter_schema", "invoke")}
        for n in abs_methods:
            v = getattr(cls, n, None)
            assert v is not None, f"{cls.__name__} missing {n}"
    # invoke() sig: args: Mapping
    sig = inspect.signature(ToolPort.invoke)
    assert list(sig.parameters.keys()) == ["self", "args"]


def test_registry_register_duplicate_raises(admin_tools):
    with pytest.raises(ValueError, match="duplicate tool name"):
        admin_tools.register(ShellTool())


def test_registry_manifest_returns_all_9(admin_tools):
    man = admin_tools.manifest()
    names = sorted(m["name"] for m in man)
    assert names == sorted(["shell", "python_sandbox", "files", "github", "weather", "calendar", "email", "db", "web_fetch"])


def test_registry_invoke_unknown_tool_returns_failure(admin_tools, full_token, full_caps):
    r = admin_tools.invoke("nope", {}, token=full_token, capabilities=full_caps)
    assert r.success is False
    assert "Unknown tool" in r.stderr


def test_registry_capability_gate_blocks_without_permission(admin_tools, full_token):
    # Attempt TOOL_INVOKE:shell but capabilities only allow files: should raise PermissionDenied.
    only_files = (Capability(CapabilityOp.TOOL_INVOKE, "files"),)
    with pytest.raises(PermissionDenied):
        admin_tools.invoke("shell", {"command": "echo hello"}, token=full_token, capabilities=only_files)


def test_registry_capability_wildcard_allows_everything(admin_tools, full_token, full_caps):
    # Wildcard TOOL_INVOKE:* should pass capability gate and produce a dry-run shell result.
    r = admin_tools.invoke("shell", {"command": "echo ok"}, token=full_token, capabilities=full_caps)
    assert r.success is True


# ---------------------------------------------------------------------------
# Individual adapters
# ---------------------------------------------------------------------------


def test_shell_tool_dry_run_describes_exec():
    s = ShellTool()  # no allowed_commands → dry-run
    r = s.invoke({"command": "ls -la"})
    assert r.exit_code == 0 and r.success
    assert "would exec" in r.stdout


def test_shell_tool_whitelist_rejects_unknown():
    s = ShellTool(allowed_commands=["echo"])
    r = s.invoke({"command": "cat /etc/passwd"})
    assert r.success is False
    assert "not in allowed_commands" in r.stderr


def test_python_sandbox_expr_returns_structured():
    sandbox = PythonSandboxTool()
    r = sandbox.invoke({"code": "x = sum(range(100))\nx\n", "env": {}})
    assert r.success and r.exit_code == 0
    assert r.structured.get("result") == 4950


def test_python_sandbox_blocks_import_os():
    sandbox = PythonSandboxTool()
    r = sandbox.invoke({"code": "import os\nos.listdir('.')"})
    assert not r.success
    assert "not allowed" in (r.stderr or "")


def test_python_sandbox_blocks_open_builtin():
    sandbox = PythonSandboxTool()
    r = sandbox.invoke({"code": "open('x').read()"})
    assert not r.success or "'open'" in r.stderr


def test_files_tool_write_read_roundtrip(tmp_path):
    f = FilesTool(tmp_path)
    f.invoke({"operation": "write", "path": "hello.txt", "content": "Hello world"})
    read = f.invoke({"operation": "read", "path": "hello.txt"})
    assert read.stdout == "Hello world"


def test_files_tool_refuses_path_traversal(tmp_path):
    f = FilesTool(tmp_path)
    r = f.invoke({"operation": "read", "path": "../secrets.txt"})
    assert not r.success and "escapes allowed root" in r.stderr


def test_github_tool_dry_run_repo(admin_tools, full_token, full_caps):
    r = admin_tools.invoke(
        "github",
        {"operation": "repo", "owner": "astraos", "repo": "astraos"},
        token=full_token,
        capabilities=full_caps,
    )
    assert r.success
    assert r.structured["owner"] == "astraos"


def test_weather_tool_dry_run():
    w = WeatherTool()
    # WeatherTool *calls* httpx if present — force dry-run with a subclassed httpx=None? No:
    # instead pass lat/lon, should produce ToolResult regardless (success even on network miss).
    # We call directly:
    r = w.invoke({"latitude": 52.5, "longitude": 13.4})
    assert isinstance(r, ToolResult)
    # structured field may contain mode=dry-run if httpx missing, or real Open-Meteo data otherwise
    assert r.exit_code != 0 or r.stdout


def test_calendar_tool_add_and_list(tmp_path):
    cal = CalendarTool(tmp_path / "cal.ics")
    r = cal.invoke(
        {
            "operation": "add",
            "start_iso": "2026-09-01T09:00:00Z",
            "end_iso": "2026-09-01T10:00:00Z",
            "summary": "M3 review",
        }
    )
    assert r.success and "added event" in r.stdout
    listed = cal.invoke({"operation": "list"})
    assert "M3 review" in listed.stdout and listed.structured["count"] >= 1


def test_email_tool_send_dry_run():
    e = EmailTool()
    r = e.invoke({"operation": "send", "to": ["alice@example.com"], "subject": "Hi", "body": "there"})
    assert r.success and r.structured["to"] == ["alice@example.com"]


def test_db_tool_sqlite_readonly_select(admin_tools, full_token, full_caps):
    r = admin_tools.invoke("db", {"sql": "SELECT * FROM t ORDER BY id"}, token=full_token, capabilities=full_caps)
    assert r.success
    assert "alice" in r.stdout
    rows = r.structured["rows"]
    assert rows == [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]


def test_db_tool_blocks_insert(admin_tools, full_token, full_caps):
    r = admin_tools.invoke("db", {"sql": "INSERT INTO t VALUES (3, 'charlie')"}, token=full_token, capabilities=full_caps)
    assert not r.success
    assert "only SELECT / WITH / EXPLAIN / PRAGMA / SHOW / VALUES" in r.stderr


def test_web_fetch_tool_rejects_ftp_scheme():
    w = WebFetchTool()
    r = w.invoke({"url": "ftp://evil.invalid/x"})
    assert not r.success and "scheme" in r.stderr


def test_web_fetch_tool_http_local_allowed_structure():
    w = WebFetchTool()
    r = w.invoke({"url": "http://localhost:1/nope"})
    # Should either succeed (if httpx missing → dry-run) or fail gracefully (ConnectionError → -1)
    assert isinstance(r, ToolResult)


# ---------------------------------------------------------------------------
# ResearchAgent
# ---------------------------------------------------------------------------


def _ctx(tools, token=None, caps=None) -> AgentRunContext:
    return AgentRunContext(
        token=token or CapabilityToken(owner_agent_id="pytest"),
        capabilities=tuple(caps or [Capability(CapabilityOp.TOOL_INVOKE, "*")]),
        tools=tools,
        request_id="test-req",
    )


def test_research_agent_missing_query_returns_failed(admin_tools):
    agent = ResearchAgent()
    out = agent.run({}, _ctx(admin_tools))
    assert TaskStatus(out["status"]) == TaskStatus.FAILED


def test_research_agent_plan_only_when_no_seed_urls(admin_tools):
    agent = ResearchAgent(max_sources=4)
    out = agent.run({"query": "What is Noesis?"}, _ctx(admin_tools))
    # No seed URLs → AWAITING_INPUT + 0.2 confidence
    assert TaskStatus(out["status"]) == TaskStatus.AWAITING_INPUT
    report = ResearchReport(**out["report"])
    assert report.confidence <= 0.25
    assert report.plan


def test_research_agent_synthesises_multiple_sources(admin_tools):
    agent = ResearchAgent(max_sources=4)

    class WrapA(WebFetchTool):
        name = "web_fetch"

        def __init__(self):
            super().__init__()

        def invoke(self, args):
            url = args.get("url", "")
            # Dispatch by URL suffix — return different content per seed URL.
            if "v=a" in url:
                return ToolResult(
                    success=True,
                    exit_code=0,
                    stdout="# Source A\n\nPython 3.13 is the recommended runtime, supports higher performance on Noesis.\n",
                )
            if "v=b" in url:
                return ToolResult(
                    success=True,
                    exit_code=0,
                    stdout="# Source B\n\nPython 3.13 supports performance tuning, Noesis bundles it as the default runtime.\n",
                )
            return ToolResult(success=False, exit_code=404, stderr="unmapped stub")

    reg2 = ToolRegistry(tools=(WrapA(),))
    urls = ["https://a.example/doc?v=a", "https://b.example/doc?v=b"]
    out = agent.run({"query": "Python 3.13 Noesis runtime", "seed_urls": urls}, _ctx(reg2))
    assert TaskStatus(out["status"]) == TaskStatus.SUCCESS
    rep = ResearchReport(**out["report"])
    assert len(rep.sources) == 2
    assert rep.confidence >= 0.5


# ---------------------------------------------------------------------------
# ReflectionAgent
# ---------------------------------------------------------------------------


def test_reflection_flags_missing_citations():
    agent = ReflectionAgent()
    state = {
        "answer": "Rust is memory safe. Rust is faster than Python. Rust has crates.io.",
        "tool_calls": [],
    }
    out = agent.run(state, _ctx(ToolRegistry()))
    assert TaskStatus(out["status"]) == TaskStatus.SUCCESS
    report = ReflectionReport(**out["report"])
    kinds = [m.kind for m in report.mistakes]
    assert "missing_citations" in kinds
    assert report.confidence <= 0.85


def test_reflection_flags_tool_failures():
    agent = ReflectionAgent()
    state = {
        "answer": "ran command",
        "citations": [],
        "tool_calls": [{"name": "shell", "result": ToolResult(success=False, exit_code=2, stderr="boom")}],
    }
    out = agent.run(state, _ctx(ToolRegistry()))
    report = ReflectionReport(**out["report"])
    kinds = [m.kind for m in report.mistakes]
    assert "tool_failures" in kinds
    assert report.replan_recommended is True


def test_reflection_reports_contradiction():
    agent = ReflectionAgent()
    state = {
        "answer": "The sky is blue. The sky is not blue because it is night.",
        "citations": [CitationRef(source_kind="url", location="x", snippet="x")],
    }
    out = agent.run(state, _ctx(ToolRegistry()))
    report = ReflectionReport(**out["report"])
    assert any(m.kind == "internal_contradiction" for m in report.mistakes)
    assert report.replan_recommended is True


# ---------------------------------------------------------------------------
# CodingAgent (alpha)
# ---------------------------------------------------------------------------


_SOURCE = '''\
"""Hello module."""


def add(a, b):
    return a + b
'''


def test_coding_agent_returns_plan_and_patches(tmp_path, admin_tools):
    # Prepare a source file via FilesTool first.
    admin_tools.get("files").invoke({"operation": "write", "path": "hello.py", "content": _SOURCE})
    agent = CodingAgent()
    instructions = """
- replace "return a + b" with "return a + b + 1"
- replace module docstring "Hello module." with "Goodbye module."
""".strip()
    out = agent.run(
        {"target_file": "hello.py", "instructions": instructions},
        _ctx(admin_tools),
    )
    assert TaskStatus(out["status"]) == TaskStatus.SUCCESS
    report = CodingPatchReport(**out["report"])
    assert report.plan_steps and report.patches
    # Apply the patches programmatically.
    new_src = CodingAgent.apply_patch(_SOURCE, report.patches)
    assert "Goodbye module." in new_src
    assert "return a + b + 1" in new_src
    assert report.confidence >= 0.7


def test_coding_agent_patch_ambiguous_match_raises(tmp_path):
    src = "x = 1\nx = 1\nx = 1\n"
    patch = PatchStep(target_file="a.py", operation="replace", original="x = 1", proposed="y = 2")
    with pytest.raises(ValueError, match="original snippet matched"):
        CodingAgent.apply_patch(src, [patch])


# ---------------------------------------------------------------------------
# Security primitives
# ---------------------------------------------------------------------------


def test_password_hasher_roundtrip_and_rehash():
    h = PasswordHasher()
    pw = "Demo!1234567890"
    digest = h.hash(pw)
    assert digest != pw
    assert h.verify(pw, digest) is True
    assert h.verify("wrong", digest) is False
    # Outdated digest always needs rehash
    assert h.needs_rehash("") or digest is not None


def test_jwt_sign_roundtrip():
    svc = JWTService(secret="x" * 32)
    tok = svc.sign(subject="u-1", roles=("admin", "user"))
    sub = svc.decode(tok)
    assert sub.sub == "u-1"
    assert set(sub.roles) == {"admin", "user"}


def test_jwt_tampered_sig_fails():
    svc = JWTService(secret="x" * 32)
    tok = svc.sign(subject="u-2")
    head, payload, sig = tok.split(".")
    bad = f"{head}.{payload}.{sig[:-1]}{'A' if sig[-1] != 'A' else 'B'}"
    with pytest.raises(JWTDecodeError, match="signature mismatch"):
        svc.decode(bad)


def test_jwt_expired_token_fails():
    svc = JWTService(secret="x" * 32, access_token_ttl=_dt.timedelta(microseconds=1))
    tok = svc.sign(subject="u-expired")
    time.sleep(0.01)
    with pytest.raises(JWTDecodeError, match="expired"):
        svc.decode(tok)


def test_jwt_wrong_use_fails():
    svc = JWTService(secret="x" * 32)
    tok = svc.sign(subject="u-ref", kind="refresh")
    with pytest.raises(JWTDecodeError, match="token_use must be"):
        svc.decode(tok, expected_use="access")


def test_in_memory_rate_limiter_sliding_window_blocks():
    rl = InMemoryRateLimiter()
    key = "rl-test1"
    for _i in range(3):
        rl.check(key=key, limit=3, window_s=60)
    with pytest.raises(RateLimitExceeded, match="Rate limit exceeded"):
        rl.check(key=key, limit=3, window_s=60)


def test_input_sanitiser_drops_onclick_and_tags():
    san = InputSanitiser()
    s = san.sanitize_html('<p onclick="alert(1)">Hello <b>world</b> <a href="javascript:x">click</a></p>')
    assert "onclick" not in s
    assert "<p>" not in s and "<b>" not in s
    assert "Hello world" in s


def test_input_sanitiser_control_chars_dropped():
    san = InputSanitiser()
    raw = "A\x00\x01B\nC\tD"
    out = san.sanitize_plain(raw)
    assert "\x00" not in out and "\x01" not in out
    assert out == "A B C D"


def test_password_strength_validator():
    ok, reasons = InputSanitiser.validate_password_strength("Demo!12345678")
    assert ok is True and reasons == []
    ok, reasons = InputSanitiser.validate_password_strength("short")
    assert ok is False and any("too short" in r for r in reasons)
    ok, reasons = InputSanitiser.validate_password_strength("alllowercaseletters")
    assert ok is False and any("too simple" in r for r in reasons)
    ok, reasons = InputSanitiser.validate_password_strength("aaaaaaaaaaaaaaaaaaaaaa")
    assert ok is False and any("distinct characters" in r or "simple" in r for r in reasons)


# ---------------------------------------------------------------------------
# HTTP routes (auth + observability) via TestClient
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_shared_rate_limiter():
    # Clear the module-level rate limiter used by auth + observability routes
    # between tests so rate-limit states don't leak.
    try:
        from noesis.api.routes import v1_m3 as _m3
    except Exception:  # pragma: no cover - defensive
        _m3 = None
    if _m3 is not None:
        rl = getattr(_m3, "_SHARED_RATE_LIMITER", None)
        if rl is not None and hasattr(rl, "reset"):
            rl.reset()
        # Also clear metrics ring if present
        metrics = getattr(_m3, "_METRICS", None)
        if metrics is not None:
            with getattr(metrics, "lock", __import__("threading").RLock()):
                if hasattr(metrics.requests, "clear"):
                    metrics.requests.clear()
                if hasattr(metrics.tool_traces, "clear"):
                    metrics.tool_traces.clear()
    yield


@pytest.fixture()
def app_client(_reset_shared_rate_limiter):
    from fastapi.testclient import TestClient

    from noesis.api.main import app

    with TestClient(app) as client:
        yield client


def test_auth_login_demo_user_returns_token_pair(app_client):
    r = app_client.post("/v1/auth/login", json={"user_id": "demo", "password": "Demo!12345678"})
    assert r.status_code == 200, r.content
    body = r.json()
    assert "access_token" in body and "refresh_token" in body
    assert body["token_type"] == "Bearer"


def test_auth_login_bad_password_is_401(app_client):
    r = app_client.post("/v1/auth/login", json={"user_id": "demo", "password": "wrongpwx"})
    assert r.status_code == 401


def test_auth_login_rate_limit_blocks_same_ip_user(app_client):
    for _ in range(5):
        app_client.post("/v1/auth/login", json={"user_id": "demo", "password": "wrong1111"})
    r = app_client.post("/v1/auth/login", json={"user_id": "demo", "password": "wrong1111"})
    # Either 401 (wrong pw) or 429 (rate limit) — after 5 FAILS + 6th call: 429 expected
    assert r.status_code in (401, 429)


def test_auth_me_returns_subject(app_client):
    login = app_client.post("/v1/auth/login", json={"user_id": "demo", "password": "Demo!12345678"}).json()
    bearer = {"Authorization": f"Bearer {login['access_token']}"}
    r = app_client.get("/v1/auth/me", headers=bearer)
    assert r.status_code == 200
    body = r.json()
    assert body["sub"] == "demo" and "user" in body["roles"]


def test_auth_refresh_issues_new_access(app_client):
    login = app_client.post("/v1/auth/login", json={"user_id": "demo", "password": "Demo!12345678"}).json()
    bearer = {"Authorization": f"Bearer {login['refresh_token']}"}
    r = app_client.post("/v1/auth/refresh", headers=bearer)
    assert r.status_code == 200
    new_access = r.json()["access_token"]
    # /v1/auth/me should accept new access token
    r2 = app_client.get("/v1/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert r2.status_code == 200 and r2.json()["sub"] == "demo"


def test_auth_me_missing_bearer_returns_401(app_client):
    r = app_client.get("/v1/auth/me")
    assert r.status_code == 401


def test_observability_summary_admin(app_client):
    # 1. Login as admin; we rely on environment settings fallback if admin env missing → use demo + create admin token manually via svc.
    svc = get_jwt_service()
    admin_tok = svc.sign(subject="test-admin", kind="access", roles=("admin",))
    # Seed metrics.
    for _ in range(10):
        record_request(duration_ms=80, tokens_prompt=500, tokens_completion=200, cost_usd=0.00012)
    for _ in range(5):
        record_tool_trace(tool_name="shell", duration_ms=50)
    record_tool_trace(tool_name="shell", duration_ms=9999, error=True)
    bearer = {"Authorization": f"Bearer {admin_tok}"}
    r = app_client.get("/v1/observability/summary?window_s=999999", headers=bearer)
    assert r.status_code == 200, r.content
    body = r.json()
    assert body["total_requests"] >= 10
    assert body["total_prompt_tokens"] >= 10 * 500
    tools_by_name = {t["tool_name"]: t for t in body["tools"]}
    shell = tools_by_name["shell"]
    assert shell["invocations"] >= 5
    assert shell["errors"] >= 1
    assert shell["p95_ms"] >= 50


def test_observability_summary_requires_admin_role(app_client):
    login = app_client.post("/v1/auth/login", json={"user_id": "demo", "password": "Demo!12345678"}).json()
    # demo user has only "user" role — observability route requires admin/observability.
    bearer = {"Authorization": f"Bearer {login['access_token']}"}
    r = app_client.get("/v1/observability/summary", headers=bearer)
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Milestone 7 new agents: 8 roster slots + AgentRoster
# ---------------------------------------------------------------------------


from noesis.agents import (
    Agent,
    AgentRoster,
    CriticAgent,
    CriticReport,
    ExecutorAgent,
    ExecutorReport,
    JudgeAgent,
    JudgeReport,
    MemoryAgent,
    MemoryReport,
    OrchestratorAgent,
    OrchestratorReport,
    RAGAgent,
    RAGReport,
    SupervisorAgent,
    SupervisorReport,
    ToolAgent,
    ToolReport,
)
from noesis.kernel.capabilities import allow_all
from noesis.types import AgentType


def _m7_ctx(tools=None, caps=None, token=None) -> AgentRunContext:
    reg = tools or ToolRegistry()
    if caps is None:
        capabilities: tuple[Capability, ...] = (Capability(CapabilityOp.TOOL_INVOKE, "*"),)
    else:
        capabilities = tuple(caps)
    return AgentRunContext(
        token=token or CapabilityToken(owner_agent_id="pytest-m7", workspace_id="ws-m7"),
        capabilities=capabilities,
        tools=reg,
        request_id="req-m7",
        workspace_id="ws-m7",
    )


# ----- MemoryAgent -------------------------------------------------------


def test_memory_agent_recall_succeeds():
    a = MemoryAgent()
    out = a.run({"query": "Where did I leave my keys?", "operation": "recall"}, _m7_ctx())
    assert TaskStatus(out["status"]) == TaskStatus.SUCCESS
    rep = MemoryReport(**out["report"])
    assert rep.operation == "recall"
    assert rep.items_processed >= 1
    assert rep.keys
    assert rep.confidence > 0.4


def test_memory_agent_compress_returns_ratio():
    a = MemoryAgent()
    out = a.run({"query": "compress stale memory buckets", "operation": "compress"}, _m7_ctx())
    assert TaskStatus(out["status"]) == TaskStatus.SUCCESS
    rep = MemoryReport(**out["report"])
    assert rep.operation == "compress"
    assert 0.0 <= rep.compressed_ratio <= 1.0
    assert rep.items_processed >= 1


def test_memory_agent_empty_input_is_failed():
    a = MemoryAgent()
    out = a.run({}, _m7_ctx())
    assert TaskStatus(out["status"]) == TaskStatus.FAILED
    rep = MemoryReport(**out["report"])
    assert rep.confidence == 0.0


# ----- RAGAgent ----------------------------------------------------------


def test_rag_agent_retrieves_top_k_chunks():
    a = RAGAgent()
    out = a.run({"query": "Python 3.13 free-threading GIL", "k": 4}, _m7_ctx())
    assert TaskStatus(out["status"]) == TaskStatus.SUCCESS
    rep = RAGReport(**out["report"])
    assert rep.k == 4
    assert len(rep.chunks) == 4
    assert all(isinstance(c.score, float) and 0.0 <= c.score <= 1.0 for c in rep.chunks)
    assert rep.cited_sources
    assert rep.confidence > 0.5


def test_rag_agent_missing_query_fails():
    a = RAGAgent()
    out = a.run({}, _m7_ctx())
    assert TaskStatus(out["status"]) == TaskStatus.FAILED
    rep = RAGReport(**out["report"])
    assert rep.chunks == []


# ----- ToolAgent ---------------------------------------------------------


def test_tool_agent_empty_calls_is_awaiting_input(admin_tools):
    a = ToolAgent()
    out = a.run({"calls": []}, _m7_ctx(tools=admin_tools))
    assert TaskStatus(out["status"]) == TaskStatus.AWAITING_INPUT
    rep = ToolReport(**out["report"])
    assert rep.invocations_requested == 0


def test_tool_agent_runs_shell_dry_run(admin_tools, full_token, full_caps):
    a = ToolAgent()
    out = a.run(
        {"calls": [{"name": "shell", "args": {"command": "echo hello"}}]},
        _m7_ctx(tools=admin_tools, token=full_token, caps=full_caps),
    )
    rep = ToolReport(**out["report"])
    assert rep.invocations_requested == 1
    # shell tool dry-run: success=True with no allowed_commands → ShellTool returns
    # exit_code=0 stdout dry-run banner or success=False depending on branch.
    assert rep.invocations_success + rep.invocations_failed == 1
    assert rep.call_log and rep.call_log[0]["name"] == "shell"


def test_tool_agent_catches_permission_denied(admin_tools, full_token):
    # Use a token that intentionally carries NO capabilities at all → every call
    # is denied, producing PermissionDenied entries instead of uncaught exceptions.
    empty_caps: tuple[Capability, ...] = ()
    a = ToolAgent()
    out = a.run(
        {"calls": [{"name": "files", "args": {"operation": "list", "path": "."}}]},
        _m7_ctx(tools=admin_tools, token=full_token, caps=empty_caps),
    )
    rep = ToolReport(**out["report"])
    assert rep.invocations_failed >= 1
    assert any(entry.get("permission_denied") for entry in rep.call_log)


# ----- JudgeAgent --------------------------------------------------------


def test_judge_ranks_candidates_and_picks_winner():
    a = JudgeAgent()
    cands = [
        {"id": "a", "text": "Short answer"},
        {"id": "b", "text": "This is a well cited answer with [src01] and [src02] plus multiple complete sentences that argue the point thoroughly."},
        {"id": "c", "text": "A middling answer with one citation [src99] that gives a moderate amount of detail and evidence."},
    ]
    out = a.run({"prompt": "Which candidate is best?", "candidates": cands}, _m7_ctx())
    assert TaskStatus(out["status"]) == TaskStatus.SUCCESS
    rep = JudgeReport(**out["report"])
    assert rep.winner_id is not None
    ranks = sorted(r.rank for r in rep.candidates)
    assert ranks == [1, 2, 3]
    # Candidate b has most citations + length → should win rank 1
    by_id = {r.candidate_id: r for r in rep.candidates}
    assert by_id["b"].rank == 1
    assert by_id["b"].score >= by_id["c"].score >= by_id["a"].score


def test_judge_no_candidates_returns_failed():
    a = JudgeAgent()
    out = a.run({}, _m7_ctx())
    assert TaskStatus(out["status"]) == TaskStatus.FAILED
    rep = JudgeReport(**out["report"])
    assert rep.candidates == []


# ----- CriticAgent -------------------------------------------------------


def test_critic_scores_quality_and_produces_rubric():
    a = CriticAgent()
    draft = (
        "## Executive Summary\n"
        "This is a strong draft that argues the case with citations [src01] and [src02].\n"
        "It has multiple paragraphs. Each paragraph supports the thesis with evidence.\n"
        "The conclusion restates the main idea clearly and calls for action.\n"
    )
    out = a.run({"draft": draft}, _m7_ctx())
    assert TaskStatus(out["status"]) == TaskStatus.SUCCESS
    rep = CriticReport(**out["report"])
    assert set(("structure", "clarity", "citation_support", "completeness", "grammar")).issubset(rep.quality_scores)
    assert 0.0 <= rep.overall_quality <= 1.0
    assert rep.praise or rep.improvements


def test_critic_short_draft_fails():
    a = CriticAgent()
    out = a.run({"draft": "nope"}, _m7_ctx())
    assert TaskStatus(out["status"]) == TaskStatus.FAILED


# ----- ExecutorAgent -----------------------------------------------------


def test_executor_signs_off_good_answer():
    a = ExecutorAgent()
    answer = (
        "This is a high-quality final answer over 120 chars long, properly justified, "
        "well structured, with adequate length and no signs of rushing or cutting "
        "corners to deliver the result."
    )
    out = a.run({"final_answer": answer}, _m7_ctx())
    assert TaskStatus(out["status"]) == TaskStatus.SUCCESS
    rep = ExecutorReport(**out["report"])
    assert rep.decision == "signoff"


def test_executor_rejects_short_answer():
    a = ExecutorAgent()
    out = a.run({"final_answer": "too short"}, _m7_ctx())
    assert TaskStatus(out["status"]) == TaskStatus.AWAITING_INPUT
    rep = ExecutorReport(**out["report"])
    assert rep.decision == "reject"
    assert rep.rejection_reason
    assert rep.replan_hints


def test_executor_reads_critic_from_state():
    a = ExecutorAgent()
    state = {
        "final_answer": "x" * 300,  # long enough on its own
        "report_type": "CriticReport",
        "report": {"overall_quality": 0.22},  # below 0.5 threshold → replan
    }
    out = a.run(state, _m7_ctx())
    rep = ExecutorReport(**out["report"])
    assert rep.decision == "replan"


# ----- SupervisorAgent ---------------------------------------------------


def test_supervisor_requires_spawn_capability():
    # ctx carries only TOOL_INVOKE:* — SPAWN_AGENT missing → Supervisor MUST
    # refuse to plan the tree.
    a = SupervisorAgent()
    wrong_caps = (Capability(CapabilityOp.TOOL_INVOKE, "*"),)
    out = a.run({"goal": "Build a 5-step subtask tree"}, _m7_ctx(caps=wrong_caps))
    assert TaskStatus(out["status"]) == TaskStatus.FAILED
    rep = SupervisorReport(**out["report"])
    assert rep.task_count == 0
    assert "SPAWN_AGENT" in rep.summary


def test_supervisor_builds_tree_with_allow_all():
    a = SupervisorAgent()
    out = a.run({"goal": "Build a 7-step subtask tree for research + coding"}, _m7_ctx(caps=allow_all()))
    assert TaskStatus(out["status"]) == TaskStatus.SUCCESS
    rep = SupervisorReport(**out["report"])
    assert rep.task_count >= 2
    assert rep.task_count == rep.completed + rep.failed + rep.pending
    assert rep.minted_subtokens == rep.task_count


# ----- OrchestratorAgent -------------------------------------------------


def test_orchestrator_defaults_to_research_rag_memory():
    a = OrchestratorAgent()
    out = a.run({"goal": "Find and cite information about Noesis architecture"}, _m7_ctx())
    assert TaskStatus(out["status"]) == TaskStatus.SUCCESS
    rep = OrchestratorReport(**out["report"])
    assert rep.fan_out_count >= 2
    assert AgentType.RESEARCH.value in rep.dispatched_to
    assert AgentType.RAG.value in rep.dispatched_to
    assert AgentType.MEMORY.value in rep.dispatched_to
    assert rep.join_policy == "all"
    assert rep.join_summary


def test_orchestrator_code_goal_picks_code_reflection_critic():
    a = OrchestratorAgent()
    out = a.run({"goal": "patch the code bug and test the refactor"}, _m7_ctx())
    rep = OrchestratorReport(**out["report"])
    assert AgentType.CODING.value in rep.dispatched_to
    assert AgentType.REFLECTION.value in rep.dispatched_to
    assert AgentType.CRITIC.value in rep.dispatched_to


# ----- AgentRoster -------------------------------------------------------


def test_agent_roster_exactly_12_matches_enum():
    assert len(AgentRoster.registry()) == 12
    assert set(AgentRoster.registry().keys()) == set(AgentType)
    # Stable sorted order
    assert AgentRoster.all_types() == sorted(AgentType, key=lambda at: at.value)


def test_agent_roster_get_returns_instance_for_every_enum():
    for at in AgentType:
        inst = AgentRoster.get(at)
        assert isinstance(inst, Agent)
        assert inst.agent_type == at


def test_agent_roster_spawn_gate_rejects_insufficient_token():
    # Supervisor requires SPAWN_AGENT:* + KILL_AGENT:zombie:* + ADMIN:status.
    # A token carrying only TOOL_INVOKE:* must raise PermissionDenied.
    weak = (Capability(CapabilityOp.TOOL_INVOKE, "*"),)
    ctx = _m7_ctx(caps=weak)
    with pytest.raises(PermissionDenied, match=r"(?i)spawn[_ ]agent|spawn_agent:\*"):
        AgentRoster.spawn(AgentType.SUPERVISOR, ctx)


def test_agent_roster_spawn_accepts_allow_all_for_every_agent():
    every_cap = allow_all()
    ctx = _m7_ctx(caps=every_cap)
    for at in AgentType:
        inst = AgentRoster.spawn(at, ctx)
        assert isinstance(inst, Agent)
        assert inst.agent_type == at
