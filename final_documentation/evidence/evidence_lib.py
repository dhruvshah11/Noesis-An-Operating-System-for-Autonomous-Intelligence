"""Library-level evidence (no HTTP). Writes evidence_lib.json."""
from __future__ import annotations

import ast
import asyncio
import hashlib
import json
import os
import statistics
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(r"C:\Users\dhruv\Downloads\ASTRAOS")
os.chdir(HERE)
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/evidence_lib.db")
sys.path.insert(0, str(HERE))
OUT: dict = {}


def tstats(xs):
    xs = sorted(xs)
    return {"n": len(xs), "mean_ms": round(statistics.mean(xs), 4), "p50_ms": round(xs[len(xs) // 2], 4),
            "p95_ms": round(xs[min(len(xs) - 1, int(0.95 * len(xs)))], 4), "max_ms": round(xs[-1], 4)}


# ------------------------------------------------------------------ planner timing + determinism
from noesis.agents.core import AgentRoster, AgentRunContext, ExecutorAgent, PlannerAgent  # noqa: E402
from noesis.kernel.capabilities import Capability, CapabilityOp, CapabilityToken, PermissionDenied  # noqa: E402
from noesis.services.kernel_services import ALL_CAPABILITIES, PlannerSvc, _default_tool_registry  # noqa: E402
from noesis.types import AcceptCriterion, AgentType  # noqa: E402

svc = PlannerSvc(tools=_default_tool_registry(HERE / "var" / "ws"))
goals = [ln.strip() for ln in (HERE / "benchmarks" / "noesis_se50" / "goals.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
OUT["se50_goal_count"] = len(goals)
times = []
det_rows = []
agent_mix = Counter()
steps_hist = Counter()
for gi, g in enumerate(goals):
    hashes = []
    for run in range(3):
        t0 = time.perf_counter()
        rep = svc.plan(g, seed=42)
        times.append((time.perf_counter() - t0) * 1000)
        js = rep.plan.model_dump_json()
        hashes.append(hashlib.sha256(js.encode()).hexdigest())
    det_rows.append({"goal_index": gi, "unique_hashes": len(set(hashes)), "steps": len(rep.plan.steps)})
    steps_hist[len(rep.plan.steps)] += 1
    for s in rep.plan.steps:
        agent_mix[s.assigned_agent.value] += 1
OUT["planner_timing"] = tstats(times)
OUT["planner_determinism"] = {
    "goals": len(det_rows),
    "runs_per_goal": 3,
    "goals_with_single_hash": sum(1 for r in det_rows if r["unique_hashes"] == 1),
}
OUT["planner_steps_histogram"] = dict(sorted(steps_hist.items()))
OUT["planner_agent_mix"] = dict(agent_mix.most_common())
# seed sensitivity
g0 = goals[0]
seed_hashes = {s: hashlib.sha256(svc.plan(g0, seed=s).plan.model_dump_json().encode()).hexdigest()[:16] for s in (1, 2, 42, 1337, 9999)}
OUT["planner_seed_sensitivity"] = {"goal": g0, "hashes": seed_hashes, "unique": len(set(seed_hashes.values()))}
sample = svc.plan("Research capability-based security and write a summary document with citations", seed=42)
OUT["planner_sample_plan"] = json.loads(sample.model_dump_json())

# ------------------------------------------------------------------ executor tri-state grid
grid = []
for unmet_high in range(0, 4):
    for failed in range(0, 4):
        crit = [AcceptCriterion(id=f"c{i}", description="criterion", severity="high", met=i >= unmet_high) for i in range(4)]
        from noesis.types import ExecutionPlan, PlanStep, TaskStatus
        steps = [PlanStep(index=i, description="step desc", assigned_agent=AgentType.CODING, status=(TaskStatus.FAILED if i < failed else TaskStatus.SUCCESS), confidence=0.8) for i in range(6)]
        plan = ExecutionPlan(goal="grid goal", steps=steps, reasoning="r")
        d = ExecutorAgent.evaluate_decision(plan=plan, accept_criteria=crit)
        grid.append({"unmet_high_of_4": unmet_high, "failed_steps_of_6": failed, "confidence": d.acceptance_confidence, "decision": str(d.decision)})
OUT["executor_grid"] = grid

# ------------------------------------------------------------------ capability scenarios (kernel level)
from noesis.kernel import Kernel, SysCall  # noqa: E402


async def kernel_scenarios():
    res = []
    k = Kernel.build_default()
    await k.start()

    async def echo(**kw):
        return {"echo": kw}

    k.register_tool("search", echo)
    k.register_tool("shell", echo)
    cases = [
        ("K1 zero capabilities -> TOOL_INVOKE(search)", [], SysCall.TOOL_INVOKE, {"tool": "search"}),
        ("K2 TOOL_INVOKE:search -> TOOL_INVOKE(shell)", [Capability(CapabilityOp.TOOL_INVOKE, "search")], SysCall.TOOL_INVOKE, {"tool": "shell"}),
        ("K3 TOOL_INVOKE:search -> TOOL_INVOKE(search)", [Capability(CapabilityOp.TOOL_INVOKE, "search")], SysCall.TOOL_INVOKE, {"tool": "search", "args": {"q": "x"}}),
        ("K4 TOOL_INVOKE:s* glob -> TOOL_INVOKE(shell)", [Capability(CapabilityOp.TOOL_INVOKE, "s*")], SysCall.TOOL_INVOKE, {"tool": "shell"}),
        ("K5 MEMORY_READ:* -> MEMORY_WRITE(working)", [Capability(CapabilityOp.MEMORY_READ, "*")], SysCall.MEMORY_WRITE, {"zone": "working", "tokens": 10}),
        ("K6 MEMORY_WRITE:working -> MEMORY_WRITE(working)", [Capability(CapabilityOp.MEMORY_WRITE, "working")], SysCall.MEMORY_WRITE, {"zone": "working", "tokens": 10}),
        ("K7 MODEL_INFERENCE:* -> MODEL_ROUTE", [Capability(CapabilityOp.MODEL_INFERENCE, "*")], SysCall.MODEL_ROUTE, {}),
        ("K8 MODEL_INFERENCE:* -> SPAWN_AGENT", [Capability(CapabilityOp.MODEL_INFERENCE, "*")], SysCall.SPAWN_AGENT, {}),
        ("K9 all caps -> RAG_SEARCH (no handler)", [Capability(op) for op in CapabilityOp], SysCall.RAG_SEARCH, {}),
    ]
    for i, (label, caps, call, payload) in enumerate(cases):
        h = k.spawn_agent(agent_id=f"audit-{i}", agent_type="audit", capabilities=caps)
        r = await k.syscall(h, call, payload)
        res.append({"case": label, "success": r.success, "error": (r.error or "")[:160], "latency_ms": r.latency_ms})
    spans = k.dump_recent_spans(limit=50)
    await k.stop()
    return res, spans


ks, spans = asyncio.run(kernel_scenarios())
OUT["kernel_capability_cases"] = ks
OUT["kernel_spans_sample"] = spans[-4:]

# AgentRoster spawn gating
roster = []
for at in AgentRoster.all_types():
    agent = AgentRoster.get(at)
    tok = CapabilityToken(owner_agent_id="audit")
    ctx_none = AgentRunContext(token=tok, capabilities=(), tools=_default_tool_registry(HERE / "var" / "ws"))
    ctx_req = AgentRunContext(token=tok, capabilities=tuple(agent.required_capabilities), tools=ctx_none.tools)
    denied = False
    try:
        AgentRoster.spawn(at, ctx_none)
    except PermissionDenied:
        denied = True
    ok = True
    try:
        AgentRoster.spawn(at, ctx_req)
    except PermissionDenied:
        ok = False
    roster.append({"agent_type": at.value, "class": type(agent).__name__,
                   "required_capabilities": [f"{c.op.value}:{c.target}" for c in agent.required_capabilities],
                   "spawn_with_no_caps_denied": denied, "spawn_with_required_caps_allowed": ok})
OUT["roster_spawn_gating"] = roster

# Tool registry gating
reg = _default_tool_registry(HERE / "var" / "ws")
tok = CapabilityToken(owner_agent_id="audit")
tool_cases = []
for name, caps, args in [
    ("files", (Capability(CapabilityOp.TOOL_INVOKE, "web_fetch"),), {"operation": "list", "path": "."}),
    ("files", (Capability(CapabilityOp.TOOL_INVOKE, "files"),), {"operation": "read", "path": "../../etc/passwd"}),
    ("files", (Capability(CapabilityOp.TOOL_INVOKE, "files"),), {"operation": "write", "path": "notes/a.txt", "content": "hello"}),
    ("shell", (Capability(CapabilityOp.TOOL_INVOKE, "shell"),), {"command": "rm -rf /"}),
    ("python_sandbox", (Capability(CapabilityOp.TOOL_INVOKE, "python_sandbox"),), {"code": "import os\nos.listdir('.')"}),
    ("python_sandbox", (Capability(CapabilityOp.TOOL_INVOKE, "python_sandbox"),), {"code": "import math\nmath.sqrt(144)"}),
    ("python_sandbox", (Capability(CapabilityOp.TOOL_INVOKE, "python_sandbox"),), {"code": "open('x.txt','w')"}),
    ("web_fetch", (Capability(CapabilityOp.TOOL_INVOKE, "web_fetch"),), {"url": "file:///c:/windows/win.ini"}),
]:
    try:
        r = reg.invoke(name, args, token=tok, capabilities=caps)
        tool_cases.append({"tool": name, "args": args, "permission": "granted", "success": r.success, "exit_code": r.exit_code,
                           "stdout": r.stdout[:120], "stderr": r.stderr[:160], "structured": r.structured})
    except PermissionDenied as exc:
        tool_cases.append({"tool": name, "args": args, "permission": "denied", "detail": str(exc)[:200]})
OUT["tool_registry_cases"] = tool_cases

# ------------------------------------------------------------------ memory promotion cascade
from noesis.memory import GyānCorpus, MemoryEntry, PromotionController  # noqa: E402
from noesis.memory.promotion import TIER_NAMES  # noqa: E402

base = datetime(2026, 1, 1, tzinfo=UTC)
pc = PromotionController()
pc.set_clock(base)
texts = [f"fact {i} about csv parsing and unit tests" for i in range(6)] + [f"unrelated note number {i}" for i in range(4)]
ids = []
for i, t in enumerate(texts):
    e = MemoryEntry(content=t, access_count=(3 if i < 8 else 1), created_at=base, last_accessed_at=base)
    ids.append(pc.insert_t1(e))
for t in texts[:6]:
    pc.gyan_corpus.ingest(text=t)
for mid in ids[:4]:
    pc.add_plan_ref(mid, "planA::s1")
    pc.add_plan_ref(mid, "planB::s2")
trace = []
rep = pc.run_all_promotions(passes=1); trace.append({"stage": "pass 1 (t0)", **rep.tier_counts})
rep = pc.run_all_promotions(passes=2); trace.append({"stage": "passes 2-3 (t0)", **rep.tier_counts})
pc.advance_clock(timedelta(days=8))
rep = pc.run_all_promotions(passes=1); trace.append({"stage": "after +8 days", **rep.tier_counts})
for mid in ids[:2]:
    pc.mark_human_reviewed(mid)
rep = pc.run_all_promotions(passes=1); trace.append({"stage": "after human review of 2", **rep.tier_counts})
OUT["promotion_cascade"] = {"trace": trace, "events": len(pc.events), "provenance_tail_sha": pc.provenance_tail_sha,
                            "edges": dict(Counter(f"{e.from_tier}->{e.to_tier}" for e in pc.events))}
# T6 immutability
try:
    pc.tiers["T6"].put(pc.tiers["T6"].get(ids[0]))
    OUT["paalak_overwrite"] = "allowed"
except Exception as exc:
    OUT["paalak_overwrite"] = f"refused: {exc}"[:160]
# determinism of promotion chain
def chain_sha():
    p = PromotionController(); p.set_clock(base)
    from uuid import UUID
    for i, t in enumerate(texts):
        p.insert_t1(MemoryEntry(memory_id=UUID(int=i + 1), content=t, access_count=3, created_at=base, last_accessed_at=base))
    for t in texts[:6]:
        p.gyan_corpus.ingest(text=t)
    p.run_all_promotions(passes=3)
    return p.provenance_tail_sha
OUT["promotion_chain_repeat"] = len({chain_sha() for _ in range(5)})

# planner-integrated promotion counts (what the Planner report actually contains)
OUT["planner_promotion_report"] = sample.promotion_report

# ------------------------------------------------------------------ RAG pipeline (BM25 + RRF)
from noesis.rag.pipeline import Chunker, HybridSearch, IngestPipeline  # noqa: E402

pipe = IngestPipeline(chunker=Chunker(chars_per_chunk=800, overlap_chars=200))
docs = [REPO / "ARCHITECTURE.md", REPO / "backend" / "README.md", REPO / "CHANGELOG.md"]
ing = []
for p in docs:
    raw = p.read_bytes()
    t0 = time.perf_counter()
    d, ch = pipe.ingest(raw, filename=p.name)
    ing.append({"file": p.name, "bytes": len(raw), "chunks": len(ch), "ingest_ms": round((time.perf_counter() - t0) * 1000, 3)})
hs = HybridSearch(pipe.store)
queries = ["capability token HMAC", "memory promotion tiers", "docker compose deployment", "scheduler deadline priority"]
qres = []
for q in queries:
    lat = []
    for _ in range(50):
        t0 = time.perf_counter(); res = hs.search(q, top_k=5); lat.append((time.perf_counter() - t0) * 1000)
    qres.append({"query": q, "top_hits": [{"doc": r.fragment.citation.document_title, "frag": r.fragment.citation.fragment_index, "score": round(r.score, 3), "bm25_rank": r.bm25_rank} for r in res[:3]], **tstats(lat)})
OUT["rag"] = {"ingest": ing, "queries": qres, "fragments": len(pipe.store._frags), "vocab": len(pipe.store._term_index)}

# ------------------------------------------------------------------ model router
from noesis.kernel.model_router import ModelClass, ModelRouter, RoutingConstraint  # noqa: E402
from noesis.types import ProviderType  # noqa: E402

k = Kernel.build_default()
router = k._router
rc_cases = {
    "default (no constraints)": RoutingConstraint(),
    "local only": RoutingConstraint(allow_local_only=True),
    "min_quality>=0.95": RoutingConstraint(min_quality=0.95),
    "max p95 <= 2s": RoutingConstraint(max_p95_latency_ms=2000),
    "requires vision": RoutingConstraint(required_capabilities=("vision",)),
    "impossible (quality>=1.0)": RoutingConstraint(min_quality=1.0),
}
rt = []
for name, rc in rc_cases.items():
    d = router.route(constraint=rc, estimated_input_tokens=2000, estimated_output_tokens=1000)
    rt.append({"constraint": name, "primary": f"{d.primary.profile.provider.value}:{d.primary.profile.model_id}", "score": round(d.primary.score, 4),
               "fallbacks": [f"{f.profile.provider.value}:{f.profile.model_id}" for f in d.fallbacks], "reason": d.reason[:120]})
allscores = sorted(((p.provider.value + ":" + p.model_id, router._score(p, 2000, 1000)) for p in router._profiles), key=lambda x: -x[1].score)
OUT["router"] = {"cases": rt, "scores": [{"model": m, "score": round(s.score, 4), "cost_estimate": round(s.cost_estimate, 5), "components": {k2: round(v, 3) for k2, v in s.components.items()}} for m, s in allscores],
                 "weights": router._weights}

# ------------------------------------------------------------------ code metrics
def py_metrics(root: Path):
    rows = []
    for f in sorted(root.rglob("*.py")):
        if "__pycache__" in f.parts:
            continue
        src = f.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(src)
        n_cls = sum(isinstance(n, ast.ClassDef) for n in ast.walk(tree))
        n_fn = sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in ast.walk(tree))
        loc = sum(1 for ln in src.splitlines() if ln.strip() and not ln.strip().startswith("#"))
        rows.append({"file": str(f.relative_to(root.parent)).replace("\\", "/"), "loc": loc, "lines": src.count("\n") + 1, "classes": n_cls, "functions": n_fn})
    return rows
pm = py_metrics(REPO / "backend" / "noesis")
pkg = defaultdict(lambda: {"files": 0, "loc": 0, "classes": 0, "functions": 0})
for r in pm:
    parts = r["file"].split("/")
    key = parts[1] if len(parts) > 2 else "(root)"
    for k2 in ("loc", "classes", "functions"):
        pkg[key][k2] += r[k2]
    pkg[key]["files"] += 1
OUT["backend_files"] = pm
OUT["backend_packages"] = dict(sorted(pkg.items(), key=lambda kv: -kv[1]["loc"]))
OUT["scripts_loc"] = sum(r["loc"] for r in py_metrics(REPO / "backend" / "scripts"))
OUT["tests_loc"] = sum(r["loc"] for r in py_metrics(REPO / "backend" / "tests"))
fe = []
for f in sorted((REPO / "frontend").rglob("*")):
    if f.suffix in (".ts", ".tsx") and "node_modules" not in f.parts and ".next" not in f.parts and f.name != "next-env.d.ts":
        src = f.read_text(encoding="utf-8", errors="replace")
        fe.append({"file": str(f.relative_to(REPO / "frontend")).replace("\\", "/"), "loc": sum(1 for ln in src.splitlines() if ln.strip())})
OUT["frontend_files"] = fe

# ------------------------------------------------------------------ DB schema from ORM metadata
from noesis.database.models import Base  # noqa: E402

schema = []
for t in Base.metadata.sorted_tables:
    cols = []
    for c in t.columns:
        cols.append({"name": c.name, "type": str(c.type.compile(dialect=__import__("sqlalchemy.dialects.sqlite", fromlist=["dialect"]).dialect())) if True else "",
                     "pg_type": str(c.type), "pk": c.primary_key, "nullable": c.nullable, "unique": bool(c.unique), "index": bool(c.index),
                     "fk": [str(fk.target_fullname) + (f" ON DELETE {fk.ondelete}" if fk.ondelete else "") for fk in c.foreign_keys],
                     "default": (repr(c.default.arg) if c.default is not None and not callable(c.default.arg) else ("callable" if c.default is not None else None))})
    idx = [{"name": i.name, "columns": [c.name for c in i.columns], "unique": i.unique} for i in t.indexes]
    uqs = [{"name": u.name, "columns": [c.name for c in u.columns]} for u in t.constraints if u.__class__.__name__ == "UniqueConstraint"]
    schema.append({"table": t.name, "columns": cols, "indexes": idx, "unique_constraints": uqs})
OUT["db_schema"] = schema

# ------------------------------------------------------------------ junit per file
jx = HERE / "junit.xml"
if jx.exists():
    root = ET.parse(jx).getroot()
    per = defaultdict(lambda: Counter())
    for tc in root.iter("testcase"):
        cls = tc.get("classname", "")
        f = cls.replace(".", "/")
        status = "passed"
        for ch in tc:
            if ch.tag in ("failure", "error"):
                status = "failed"
            elif ch.tag == "skipped":
                status = "xfailed" if "xfail" in (ch.get("type", "") + ch.get("message", "")).lower() else "skipped"
        per[f][status] += 1
        per[f]["time"] += float(tc.get("time", 0))
    OUT["junit_per_file"] = {k2: dict(v) for k2, v in sorted(per.items())}
    OUT["junit_totals"] = {a: root.get(a) for a in ("tests", "failures", "errors", "skipped", "time")} if root.tag == "testsuite" else {a: root[0].get(a) for a in ("tests", "failures", "errors", "skipped", "time")}

(HERE / "evidence_lib.json").write_text(json.dumps(OUT, indent=1, default=str, ensure_ascii=False), encoding="utf-8")
print("ok", list(OUT.keys()))
