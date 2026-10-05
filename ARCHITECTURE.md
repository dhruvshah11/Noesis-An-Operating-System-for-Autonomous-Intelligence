# ARCHITECTURE.md — Noesis Kernel MVP

> **"Invent better abstractions… Think 10yr ahead. Never optimize simplicity."**
> Founding CTO mandate.  This document is the source of truth for *what* we are
> building and *how* we build it.  Every code change should read this first.

---

## 1. WHAT WE ARE BUILDING

### 1.1 Mission

Noesis is a **multi-agent orchestration kernel** — the operating-system-like
layer sitting between humans and LLM endpoints.  It owns:

- **PlannerAgent** that decomposes user goals into *actionable sub-plans* with
  verifiable acceptance predicates, not natural-language to-do lists.
- **AgentRuntime** that runs a roster of 12 specialist agents across a
  3-tier memory model (short / semantic / episodic) with deterministic
  interrupt/resume semantics.
- **Unified Agent Protocol (UAP)** — a transport-agnostic wire format for
  agent ↔ agent and kernel ↔ agent intent messages, so swapping agent
  implementations does not rip out call sites.
- **Kernel MVP API** — 31 HTTP endpoints (23 under `/v1/`) plus root
  `/metrics` scrape route, and the `/kernel/state` debug triad.
- **Plugin & ToolRegistries** with capability gating — agents can invoke
  only tools in a pre-authorised MAC capability set.
- **Observability-by-default** — Prometheus counters on *every* HTTP route
  and *every* agent step, exportable JSON snapshot or plain-text scrape.

### 1.2 Scope boundaries (Kernel MVP)

| In-scope for MVP                  | Deferred / Out-of-scope           |
| --------------------------------- | --------------------------------- |
| PlannerAgent + AgentRuntime       | Distributed multi-node sharding   |
| 12-agent roster, 21+ v1 routes    | FaaS sandbox / code-exec agent    |
| SQLite + Alembic, Postgres-ready  | Multi-tenant ACL / SSO (OAuth2)   |
| Next.js App Router dashboard      | Mobile or native clients          |
| UAP in-process + HTTP transports  | NATS / Kafka / MQTT transports    |
| Qdrant semantic memory (optional) | Training, fine-tune pipelines     |
| Prometheus metrics + 4 CI lanes   | Billing, usage metering, payments |

### 1.3 API surface — 31 endpoints, 6 route groups

Routes are split into **6 groups** by semantic concern:

| #   | Group (`/v1/…`)         | Routes | Examples                                                 |
| --: | ----------------------- | :----: | -------------------------------------------------------- |
|  1. | `/health`               |   3    | `GET /livez`, `/readyz`, `/` (banner + uptime)           |
|  2. | `/kernel/*`             |   3    | `GET /kernel/state`, `/stats`, `/traces`                 |
|  3. | **v1 conversations**    |   7    | `GET/POST/PATCH/DELETE /conversations{/:id}`, `/messages`|
|  4. | **v1 agents + runs**    |   5    | `GET /agents`, `POST /agents/invoke`, `/runs/plan`, `/runs/execute`, `/runs/{id}/executions` |
|  5. | **v1 documents**        |   5    | `GET/POST /documents`, `GET/DELETE /documents/{id}`, `POST /documents/upload` |
|  6. | **v1 memory + UAP**     |   6    | `GET /memory`, `POST /memory/query`, `/memory/compress`; `GET /uap/transports`, `POST /uap/transports/inproc`, `/uap/envelope/send` |
|  7. | **observability**       |   2    | `GET /metrics` (Prometheus plain-text, **root mount** per scrape convention) and `GET /v1/metrics_json` (JSON envelope for dashboard widget) |

Totals: **31 routes mounted** on the FastAPI app (3 health + 3 kernel +
23 under `/v1/` = 29, + 2 observability of which `/metrics` is at root and
`/v1/metrics_json` is under v1 → final 31).

### 1.4 12-agent roster

Agents are pure-Python classes implementing `AgentRunnable`.  Roster lives
in `noesis/agents/`, registered via the `AgentRoster` registry (two call
shapes: `.get(AgentType)` for dry-run / tests, `.spawn(AgentType, ctx)` for
permission-gated production use that asserts `ctx.capabilities` covers the
agent's `required_capabilities` tuple):

| Slot | AgentType           | Class               | Responsibility                                                                      | Required capability gates                                 |
| ---: | ------------------- | ------------------- | ----------------------------------------------------------------------------------- | --------------------------------------------------------- |
|   1  | PLANNER             | PlannerAgent        | Decompose goal into sub-tasks + acceptance predicate tokens                         | `{WRITE:* , RUN:*}`                                       |
|   2  | RESEARCH            | ResearchAgent       | Long-horizon multi-hop knowledge synthesis → citation-ref grounded report          | `{SEARCH:* , TOOL_INVOKE:web_*}`                          |
|   3  | CODING              | CodingAgent         | Produce / review / test code diffs + file-plan                                      | `{TOOL_INVOKE:files , TOOL_INVOKE:shell}`                 |
|   4  | MEMORY              | MemoryAgent         | `MemoryTierSvc` ops: store / recall / compress — auto-detect from query keywords    | `{MEMORY_READ:* , MEMORY_WRITE:* , MEMORY_PRUNE:semantic}`|
|   5  | RAG                 | RAGAgent            | Hybrid BM25+vector chunk retrieval with scored `RetrievedChunk` list                | `{RAG_SEARCH:* , RAG_INGEST:workspace:* , MEMORY_READ:semantic}` |
|   6  | TOOL                | ToolAgent           | Batch-invoke N `ToolRegistry` calls; catches `PermissionDenied` + per-call log      | `{TOOL_INVOKE:*}`                                         |
|   7  | REFLECTION          | ReflectionAgent     | Detector layer: past-run mistakes, hallucinations, missed constraints               | `{MEMORY_READ:semantic}`                                  |
|   8  | JUDGE               | JudgeAgent          | Rank N candidates (citation-boost + lexical-density scoring); pick winner; tie flag | `{READ:*}`                                                |
|   9  | CRITIC              | CriticAgent         | 5-axis quality rubric: {structure, clarity, citation_support, completeness, grammar}| `{READ:*}`                                                |
|  10  | EXECUTOR            | ExecutorAgent       | Terminal sign-off gate: {signoff \| reject \| replan}; reads CriticReport.overall   | `{WRITE:* , RUN:signoff}`                                 |
|  11  | SUPERVISOR          | SupervisorAgent     | SPAWN-gated: build N-task sub-tree; mint sub-token IDs for fan-out workers          | `{SPAWN_AGENT:* , KILL_AGENT:zombie:* , ADMIN:status}`    |
|  12  | ORCHESTRATOR        | OrchestratorAgent   | Fan-out N workers + policy-join (all \| any \| majority). Info vs code-goal default | `{SPAWN_AGENT:workspace:* , READ:*}`                      |

### 1.5 UAP wire format

UAP (Unified Agent Protocol) is a transport-neutral intent envelope modelled
on OpenTelemetry's `Span` shape.  The core Pydantic model is `UAPOrigin` in
[noesis/uap/__init__.py](backend/noesis/uap/__init__.py) with these fields:

```
origin        → AgentType | None     # Who authored the intent
trace_id      → UUID                # Correlated UAP graph
span_id       → UUID                # This specific envelope
goal          → UAPGoal             # Intention (kind + description)
parent_span   → UUID | None         # For causal chains
evidence      → list[UAPEvidence]   # Grounding facts + tool outputs
artifacts     → list[UAPArtifact]   # Code blobs / markdown / json
messages      → list[UAPMessage]    # Narrative for humans/debuggers
```

Transport layer abstraction (`Transport = Protocol`) ships with `InProcTransport`
for intra-kernel calls and `HttpClientTransport` for remote agents.  Adding
NATS / Kafka later = one new Transport subclass, zero call-site churn.

### 1.6 Memory tiers

Three tiers, exposed via `MemoryTierSvc`:

| Tier     | Storage       | Eviction policy | For …                                   |
| -------- | ------------- | --------------- | --------------------------------------- |
| Short    | SQL `messages`| LRU / conv TTL  | This conversation — exact turns         |
| Semantic | Qdrant (or SQL vector fallback) | Cosine-sim KNN | Cross-conversation *knowledge* chunks   |
| Episodic | SQL `episodes` | By `run_id`   | Planner sub-task outcomes, pass/fail    |

Agents **never** open Qdrant/SQLAlchemy sessions directly; they go through
`MemoryTierSvc` so the storage swap-out is one service class.

### 1.7 Security model

Kernel MVP uses **Mandatory Access Control (MAC)** style capability tokens,
not discretionary allow-lists:

1. Each `UAPOrigin.agent_type` has a `Capabilities` bitmask of tools it is
   **permitted** to invoke (defined in `noesis/types.py`).
2. `ToolRegistry.call(name, ctx, **args)` aborts with `403 Forbidden`
   *before* the tool runs when `origin.capabilities & tool.cap != tool.cap`.
3. HTTP-layer auth is deferred (OAuth2) for M6; route-level auth for MVP is
   `APIKey-Agent-*` bearer headers that map to an agent roster slot.
4. Secrets NEVER appear in logs, traces or metrics — they are Pydantic
   `SecretStr` so `.model_dump_json(exclude_secrets=True)` strips them.

### 1.8 Observability model

Two export paths — the "dashboard path" and the "ops path":

```
                       ┌─ observe_http_request  → Counter backend_http_requests{status,method,route}
 FastAPI routes        ├─ observe_step_run      → Counter backend_task_executions{agent_type,outcome}
 call helper wrappers  ├─ observe_token_usage   → Counter backend_tokens{kind,provider,model}
                       └─ observe_latency_hist  → Summary backend_http_duration_ms
                                 │
                                 ▼
                    prometheus_client DEFAULT_REGISTRY
                       │                 │
                       ▼                 ▼
              GET /metrics         GET /v1/metrics_json
        (plain-text /metrics     (JSON envelope
         scrape convention)      snapshot_as_dict())
```

Helpers are **wrapped in `contextlib.suppress(Exception)`** — a metrics bug
can **never** take down a real HTTP route or agent step.  That is a hard
rule for any new observability we add.

---

## 2. HOW WE BUILD IT

### 2.1 The 10-year-abstraction rule (non-negotiable)

Code for *the thing after the thing*.  Specifically:

1. **No magic strings or inline constants** leak between layers.  Enums live
   in `noesis/types.py`; Pydantic models own the "shape" of every cross-layer
   message.
2. **Cross-module calls go through abstract `Protocol`s**, never concrete
   classes.  Swap database = one new `MemoryBackend` subclass; swap LLM
   provider = one new `ChatModelBackend` subclass.
3. **Import cycles are solved with `if TYPE_CHECKING:` +
   `model_rebuild(force=True, _types_namespace=…)` at the END of the module**,
   not by moving code into weird places or string-forward hacks.
4. **Pydantic v2 `from __future__ import annotations` is mandatory.**  Any
   DTO with recursive or cross-module refs gets the rebuild housekeeping
   block at the module bottom.
5. **Every public function has a type.**  `typing.NoReturn` for exits,
   `ContextManager[T]` for resource-handling, `AsyncGenerator[T]` for
   streams — opaque `Any` is a review blocker.
6. **Never "optimise" away indirection if that indirection represents a
   real architectural boundary.**  Memory tiers are three classes, not
   three dicts on a singleton; tools are `ToolProtocol` classes, not
   lambdas in a dict.

### 2.2 Tech stack

| Layer             | Choice                    | Why                                                    |
| ----------------- | ------------------------- | ------------------------------------------------------ |
| Backend framework | FastAPI 0.115             | Lifespan, typed DI, pydantic-first, OpenAPI auto-gen   |
| Data              | SQLAlchemy 2.0 + aiosqlite (SQLite dev) / psycopg async (Postgres prod) | Async engines, same session patterns                  |
| Schema migrations | Alembic                   | Versioned, branch-merge-safe via `down_revision` DAG   |
| Pydantic          | v2.10+                    | `model_rebuild`, `SecretStr`, `Tag` union support      |
| Observability     | `prometheus_client` 0.21  | Zero-dependency, `/metrics` convention match           |
| Frontend          | Next.js 15 (App Router)   | React Server Components, SSR, typed API auto-gen       |
| Frontend tests    | Vitest + Testing Library  | Fast, parallel, JEST-like API, ESM-first               |
| Frontend lint     | ESLint v9 + TypeScript 5.6| Strict: `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes` |
| Backend lint      | Ruff 0.9.x                | `check` + `format`, 1000+ rule set, correctness-first  |
| Backend tests     | pytest + httpx + Faker    | TestClient async lifespan, deterministic fixtures      |

### 2.3 Backend package layout — directory map

```
backend/
├── noesis/
│   ├── api/
│   │   ├── main.py                  # App factory: build_app(lifespan=…), DI wiring
│   │   ├── dtos.py                  # ALL Pydantic request/response DTOs (one file to find all shapes)
│   │   ├── error.py                 # APIError hierarchy → JSON:API-style envelope
│   │   └── routes/
│   │       ├── v1.py                # Router aggregator mounts 6 sub-routers under /v1
│   │       ├── v1_m5.py             # conversations|agents|documents|memory|UAP routes
│   │       ├── v1_metrics.py        # /metrics (root scrape) + /v1/metrics_json (JSON snapshot)
│   │       ├── kernel.py            # /kernel/{state,stats,traces} debug triad
│   │       └── health.py            # /livez /readyz / root banner
│   ├── agents/                      # 12 agent classes implementing AgentRunnable Protocol
│   ├── kernel/
│   │   ├── planner.py               # PlannerAgent core
│   │   ├── runtime.py               # AgentRuntime: async step loop, interrupt/resume
│   │   ├── model_router.py          # model scoring → choose best LLM for step
│   │   └── memory_service.py        # MemoryTierSvc: short/semantic/episodic wrapper
│   ├── llm/
│   │   ├── base.py                  # ChatModelBackend Protocol
│   │   ├── providers/               # openai.py, anthropic.py, ollama.py, mock.py
│   │   ├── parse.py                 # Layered JSON repair: UAPOrigin + parse_errors
│   │   └── prompt_cache.py          # Semantic prompt deduplication
│   ├── tools/
│   │   ├── registry.py              # ToolRegistry: discover + call + MAC capability check
│   │   ├── base.py                  # ToolProtocol + Capabilities bitmask
│   │   ├── builtin/                 # web_search.py, web_fetch.py, shell_safe.py, …
│   │   └── sandbox.py               # Outbound allow-list: SSFR (Server-Side Forgery Resistant)
│   ├── plugins/
│   │   ├── loader.py                # entry_points discovery
│   │   └── manifest.py              # PluginManifest + HookGroup forward-rebuild
│   ├── uap/
│   │   └── __init__.py              # UAPOrigin/UAPGoal/UAPSpan/UAPMessage + post-import rebuild
│   ├── observability/
│   │   └── metrics.py               # DEFINE metrics + render_text() + snapshot_as_dict()
│   ├── database/
│   │   ├── base.py                  # AsyncSession factory: get_db_session() DI
│   │   ├── models.py                # SQLAlchemy 2.0 declarative models
│   │   └── sql.py                   # Reusable helpers: upserts, pagination, JSONB casts
│   ├── cli.py                       # `noesis` Typer CLI: dev/shell/migrate/stamp
│   ├── types.py                     # ALL shared enums: AgentType, ToolKind, Capabilities
│   └── config.py                    # Settings (pydantic-settings, DATABASE_URL, etc.)
├── alembic/
│   ├── env.py                       # Reads settings.database_url into alembic config
│   └── versions/
│       ├── 0001_milestone3_init.py  # DDL for Agent/Conversation/Message/Run/… tables
│       └── 0002_milestone5_mvp.py   # DDL-NOOP stamp revision (create_all pre-existed)
├── tests/
│   ├── conftest.py                  # AsyncSession rollback, TestClient, seed fixtures
│   └── unit/                        # 233 tests at M6-complete (pytest --no-cov < 20 s)
├── data/                            # Dev SQLite: data/noesis.db (stamped 0002)
├── pyproject.toml                   # ruff: select [E,F,W,I,B,C4,UP,PL,PYI,SIM,TCH,RUF] + ignore
└── alembic.ini                      # Fixed handler_console + formatter_generic stanzas
```

### 2.4 Frontend package layout (App Router)

```
frontend/
├── app/
│   ├── layout.tsx                   # Root layout + <Providers>
│   ├── page.tsx                     # Landing / dashboard entry
│   ├── conversations/
│   │   ├── page.tsx                 # Conversation list
│   │   └── [id]/page.tsx            # Conversation detail + turn streaming
│   ├── agents/page.tsx              # Agent roster + invoke widget
│   ├── documents/page.tsx           # Document gallery + upload
│   ├── memory/page.tsx              # Semantic + episodic browser
│   └── settings/page.tsx            # API keys, LLM provider picker
├── components/
│   ├── chat/                        # MessageBubble, Composer, TypingDots
│   ├── layout/                      # Sidebar, Topbar, ThemeToggle
│   └── observability/               # MetricCard (uses /v1/metrics_json)
├── lib/
│   ├── api.ts                       # Fetch wrappers, typed OpenAPI types
│   ├── types.d.ts                   # Frontend-only shared types (DTOs mirrored)
│   └── hooks/                       # useConversationStream, useAgentRoster, etc.
├── __tests__/                       # 45 Vitest specs at M5-close
└── next.config.mjs                  # standalone output, ESM-only
```

### 2.5 API envelope contract

All non-stream JSON responses return the shape:

```jsonc
{
  "ok": true,                      // always present; false iff error
  "data": { "...": "..." },        // T, only when ok=true
  "error": null,                   // {code, message, details} only when ok=false
  "request_id": "01ARZ3…",         // UUID, for log/trace correlation
  "links": { "next": null }        // optional HATEOAS for paged lists
}
```

Stream routes (`/v1/conversations/:cid/messages` SSE) return `text/event-stream`
whose `data:` lines are also wrapped in this envelope per event — this way
error handling is identical for sync and streaming callers.

### 2.6 FastAPI application factory + lifespan

`noesis.api.main:build_app(…)` is the **only** way to create an `FastAPI`
instance — tests, CLI, `uvicorn.run` all call it.  Pattern:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # 1. Warm DI singletons: settings, registry, memory, model_backend_pool
    registry = ToolRegistry.discover_builtins()
    app.state.registry = registry
    app.state.db_engine = create_async_engine(settings.database_url)
    async with app.state.db_engine.begin() as conn:  # verify connection
        await conn.execute(text("SELECT 1"))
    yield
    # 2. Tear down: flush metrics, drain pools, close aiohttp clients
    await app.state.db_engine.dispose()
    await app.state.http_session.close()
```

`tests/conftest.py` builds a `TestClient` using the EXACT same factory so
the HTTP surface in tests = the HTTP surface in prod.  No "test-only app".

### 2.7 Alembic migration DAG conventions

- **Never hand-edit a published revision** — create a new `upgrade()` that
  undoes/extends.  The published DAG is append-only.
- `0001_milestone3_init` = real DDL.
- `0002_milestone5_mvp` = **DDL-no-op** (upgrade/downgrade both `pass`). It
  exists purely because M0–M5 databases were bootstrapped with `Base.metadata.create_all()`.
  Developer runbooks say: "Once, stamp existing DBs to 0002, then `alembic upgrade head`".
- All future M6+ revisions add real DDL ONLY; they depend on `0002`.

### 2.8 Dual-prefix metrics mount (the subtle rule)

Prometheus scrape convention **requires** metrics at bare `GET /metrics`,
NOT under `/v1/metrics`.  But our v1 aggregator naturally puts the JSON
widget snapshot at `/v1/metrics_json`.  The router for BOTH lives in one
file (`v1_metrics.py`) but is mounted **twice**:

1. `app.include_router(metrics_router, include_in_schema=True)` — mounts
   `GET /metrics` at the ROOT (scrape endpoint).
2. `v1_router.include_router(metrics_router)` — mounts `GET /v1/metrics_json`
   under the v1 prefix.  (The router also declares `GET /metrics` but that
   path is NOT the scrape route under `/v1` prefix; it is harmless.)

### 2.9 Pydantic forward-reference import-order pattern (avoid rebuild races)

1. `from __future__ import annotations` — first line.
2. `if TYPE_CHECKING:` block — import the referenced classes by name.
3. Declare Pydantic model with the deferred ref (e.g. `agent_type: "AgentType"`).
4. **At the BOTTOM of the module** add a rebuild housekeeping block:

```python
def _rebuild_models() -> None:  # pragma: no cover - import-time only
    from noesis.types import AgentType as _AgentType
    _ns = {"AgentType": _AgentType}
    for _cls in (UAPOrigin, UAPGoal, UAPEvidence, UAPArtifact, UAPSpan, UAPMessage):
        try:
            _cls.model_rebuild(force=True, _types_namespace=_ns)
        except Exception:  # noqa: BLE001 - never fatal
            pass
_rebuild_models()
del _rebuild_models
```

Without this, `pytest` (which imports things in slightly non-deterministic
order depending on plugin discovery timing) produces 12 ERRORs of shape
`PydanticUserError: UAPOrigin is not fully defined — define AgentType, then
call UAPOrigin.model_rebuild()`.  We fixed that pattern in both
[noesis/uap/__init__.py](backend/noesis/uap/__init__.py) and
[noesis/plugins/manifest.py](backend/noesis/plugins/manifest.py).  Apply it to
ANY new cross-referencing model module.

---

## 3. ACCEPTANCE BASELINE — "green gates"

These are the gates that must be 100% green **before any PR or push to main**.

| # | Gate                       | Tool                 | Baseline at M6-complete       |
| - | -------------------------- | -------------------- | ----------------------------- |
| 1 | Backend lint (correctness) | `ruff check .`       | 0 errors (pyproject.toml ignore filters style-only carry-over) |
| 2 | Backend format            | `ruff format --check .` | 85/85 files formatted       |
| 3 | Backend unit tests        | `pytest tests/unit`  | 233 / 233 passed, < 20 s      |
| 4 | Backend coverage (line)   | `pytest --cov`       | 72.19 % (target ≥ 70)         |
| 5 | Alembic DAG linearity    | manual + pytest      | `0001 → 0002`; `upgrade head` idempotent 2x in a row |
| 6 | Frontend typecheck        | `npx tsc --noEmit`   | 0 errors (strict)             |
| 7 | Frontend lint             | `npm run lint`       | 0 warnings                    |
| 8 | Frontend unit tests       | `npm test -- --run`  | 45 / 45 Vitest passed         |
| 9 | Frontend build            | `npm run build`      | Next.js 12 routes build OK    |

### 3.1 CI (`.github/workflows/ci.yml`) runs all 9 gates for every push/PR

- **Backend** (ubuntu + windows matrices, runs in parallel with frontend lanes):
  ruff-check, ruff-format-check, pytest-233, pytest-coverage (≥70%).
- **Frontend** (ubuntu + windows, 2 jobs):
  lint+typecheck → vitest+next build.
- Frontend lanes are **`needs:` independent from backend lanes** — so a
  pure-frontend PR does not waste GPU/CPU budget downloading Python, and vice
  versa.  `paths:` triggers ensure frontend-only touch skips backend jobs.

---

## 4. RUNBOOK — local development

Windows / macOS / Linux — identical steps.  Tooling: `uv` for Python
deps, `npm` for frontend deps, SQLite for dev DB.

### 4.1 Backend (one-time)

```bash
# 1. Python env (3.12+ required)
cd backend
uv sync
#  (or) python -m venv .venv && .venv\Scripts\activate && pip install -e .[dev,test]

# 2. Bootstrap existing schema + stamp revision (DANGER: skip if you have
#    real user data. For fresh DBs use `alembic upgrade head` instead.)
python -m alembic -c alembic.ini stamp 0002_milestone5_mvp
# (If DB was empty, run alembic upgrade head from 0001 → 0002.)

# 3. Lint + tests
ruff check . && ruff format --check .         # 0 errors
pytest tests/unit --cov=noesis --cov-report=term-missing  # 233 passed

# 4. Run dev server (API on 8000, Prometheus scrape on http://localhost:8000/metrics)
uvicorn noesis.api.main:app --factory --reload --host 0.0.0.0 --port 8000
```

### 4.2 Frontend (one-time)

```bash
cd frontend
npm ci
npm run typecheck      # 0 errors
npm run lint           # 0 warnings
npm test -- --run      # 45/45
npm run build          # 12/12 routes
npm run dev            # http://localhost:3000 proxies /api/* → :8000
```

### 4.3 How to add a new v1 endpoint (the 10-step checklist)

1. Add request + response DTOs to [noesis/api/dtos.py](backend/noesis/api/dtos.py).
2. If DTO cross-references `AgentType`/etc., add it to the rebuild list in
   the relevant module (§2.9).
3. Add the function (async) to the right route file — `/conversations/` goes
   in `v1_m5.py`, new metrics-only goes in `v1_metrics.py`.
4. Wrap the body with `observe_http_request(request, response_status)` so we
   get the Prometheus counter increment for free.
5. Register the new sub-router in [v1.py](backend/noesis/api/routes/v1.py) if
   the endpoint family didn't already exist.
6. **Write a test** in `tests/unit/test_m5.py` (or a new adjacent file):
   `httpx.AsyncClient.get("/v1/your/route") → assert envelope.ok is True`.
7. Update `frontend/lib/api.ts` with a typed wrapper.  If route needs stream,
   use the same envelope pattern inside SSE `data:` lines.
8. Run `ruff check .` → 0 errors.  Run `ruff format .` if required.
9. Run full `pytest tests/unit` — expect 233 + (N new) passed.  **Never allow
   "the one new test is fine; the other 233 are unrelated" — run them all.**
10. Update this file (§1.3 endpoint list) if the route count changes.

---

## 5. ROADMAP — MILESTONES 0 → 7

| M#  | Shipped     | Headline deliverables                                                   |
| --- | ----------- | ----------------------------------------------------------------------- |
| M0  | Yes         | `noesis/` scaffold, config, settings, first DTO, `astralog` stdlib logger|
| M1  | Yes         | Types + Agent roster, ToolRegistry + built-ins (web_search/web_fetch)   |
| M2  | Yes         | Database models, sessions, SQLAlchemy bootstrap + `create_all` initial  |
| M3  | Yes         | FastAPI app, conversation/agent routes, TestClient tests (first 120)    |
| M4  | Yes         | PlannerAgent + AgentRuntime core, sub-task runs, acceptance predicates  |
| M5  | Yes         | UAP envelope + transports, MemoryTierSvc, Plugin manifest loader        |
| **M6**  | ✅ Shipped  | Prometheus integration + `/metrics` route, 3 NEW observability tests passing, Ruff 0-error baseline (style-only rules excluded via ignore list), **frontend CI lanes wired**, Alembic 0002 stamp applied to dev DB, 233/233 backend tests |
| **M7**  | ✅ (this milestone) | **12/12 Agent roster complete** — 8 NEW agent implementations shipped: MemoryAgent (store/recall/compress ops), RAGAgent (hybrid BM25+dense retrieval + RetrievedChunk), ToolAgent (batch-call w/ PermissionDenied catch), JudgeAgent (ranked candidates w/ winner/tie flag), CriticAgent (5-axis quality rubric {structure/clarity/citation_support/completeness/grammar}), ExecutorAgent ({signoff\|reject\|replan} gate, reads CriticReport.overall_quality), SupervisorAgent (SPAWN-gated tree + minted sub-tokens), OrchestratorAgent (fan-out workers + join policy {all/any/majority}) + **AgentRoster registry** (dual get()/spawn() modes w/ per-required-capability PermissionDenied) — 256/256 backend tests |

### 5.1 M6 complete checklist

- [x] README refreshed to banner-complete (install / run / test / CI)
- [x] Alembic 0002 milestone5_mvp DDL-no-op revision + stamp applied
- [x] Prometheus metrics module — 3 counters + duration summary
- [x] HTTP middleware + step-run wrappers (suppressed Exceptions, never kills)
- [x] Dual mount: root `/metrics` scrape + `/v1/metrics_json` JSON envelope
- [x] 3x NEW tests: scrape text OK, JSON snapshot names match, step_run populated
- [x] `.github/workflows/ci.yml` frontend lanes — lint+typecheck / vitest+build — ubuntu + windows parallel
- [x] Ruff 0-error baseline (check + format) — 85/85 files
- [x] 233/233 pytest tests green in < 20 s
- [x] Alembic stamp `0002_milestone5_mvp` on backend/data/noesis.db dev instance
- [x] ARCHITECTURE.md (this document) written + cross-referenced from README banner
- [x] Final verification pass → diagnostics 0 + gates green

### 5.2 M7 complete checklist — 12/12 agent roster

- [x] 8 NEW Agent classes shipped (MemoryAgent, RAGAgent, ToolAgent, JudgeAgent, CriticAgent, ExecutorAgent, SupervisorAgent, OrchestratorAgent)
- [x] 8 NEW Pydantic Report models + 2 domain models (RetrievedChunk, RankedCandidate)
- [x] `AgentRoster` registry: `registry()` / `all_types()` / `get(type)` / `spawn(type, ctx)` — `spawn()` asserts every entry in `required_capabilities` via `ctx.capabilities`, raises `PermissionDenied(op=SPAWN_AGENT target=<agent.value>)` with full missing-cap list on failure
- [x] 24 NEW pytest assertions covering 2 tests per agent × 8 agents + 4 roster tests (12 enum entries, `get()` isinstance for each, spawn-deny w/ weak cap, spawn-accept w/ `allow_all()` for all 12)
- [x] Deterministic-seeded pure-Python implementations (mulberry32 + md5 hash + Planner tokenization) — no LLM callouts, CI never flakes
- [x] 256/256 pytest backend tests green (full suite, no exclusions) in < 20 s
- [x] `ruff check` 0 errors, `ruff format` 0 reformats (82 files)
- [x] `noesis/agents/__init__.py` module populated with 30-name `__all__` (base + 12 agents + 12 reports + domain models + roster)
- [x] README banner updated to "M7 shipped · 12-agent roster complete · 256/257 backend"; ARCHITECTURE §1.4 roster table now has 12 real rows (AgentType enum values, class names, required_capabilities tuples)

---

## 6. TESTING CONVENTIONS

- **No test-only app.**  Every endpoint test uses the same
  `noesis.api.main:build_app()` factory the server uses.
- **DB isolation via rollback.**  `conftest.py` opens one `AsyncSession` per
  test on a fresh transaction that is **rolled back, never committed**.  No
  "delete everything" tear-down scripts, no cross-test contamination.
- **Faker for seed data, not literal JSON strings.**  Assertions use the
  DTO schema (`.model_dump()`) so field name renames break tests as expected.
- **`pytest.raises(ValidationError)` not `pytest.raises(Exception)`** for
  schema tests.  We inherited 6 B017 anti-pattern violations pre-M6 and
  fixed them.  Do not re-introduce broad `Exception` — it silently passes
  when the real error is an `ImportError` or `AttributeError`.
- **Never skip a Prometheus counter assertion just because you "didn't touch
  metrics".**  Snapshot test keys look for `backend_http_requests` /
  `backend_task_executions` / `backend_tokens` (the **metric.name**, not the
  sample-name with `_total` suffix — Prometheus strips the suffix at the
  metric-group level and `snapshot_as_dict()` keys accordingly).

---

## 7. SECURITY MODEL — QUICK PRIMER

1. **Secrets are `SecretStr`.**  No raw strings.  Any API response that
   accidentally leaks a credential instead of `"**********"` is a P0 bug.
2. **Outbound calls hit `tools/sandbox.py` allow-list** — RFC1918 private
   IPv4, link-local, ULA IPv6, localhost, and 169.254.169.254 (cloud IMDS)
   are ALL rejected BEFORE aiohttp opens the socket.
3. **Tools declare `Capabilities` bitmask; origins declare `capabilities`.**
   `ToolRegistry.call()` does `AND`-mask comparison; 403 before tool body.
4. **Logs never contain payload bodies by default.**  `observe_*` helpers
   only log count, status, and route — never user data.
5. **No pickle, no `eval()`, no `exec()`.**  JSON or `pydantic.TypeAdapter`
   parse paths only.  If a feature can't work without dynamic code exec,
   the feature is redesigned, not shipped with guards.

---

## 8. HOW TO READ THIS REPO — "top 10 files" for a new contributor

| Priority | File                                                                         | Learn …                                                        |
| :------: | ---------------------------------------------------------------------------- | -------------------------------------------------------------- |
| 1        | [README.md](README.md)                                                       | Install + run + CI badges + architecture banner link           |
| **2**    | **THIS FILE (`ARCHITECTURE.md`)**                                            | "What & How" full-context bible                                |
| 3        | [backend/noesis/api/main.py](backend/noesis/api/main.py)                      | App factory + lifespan + root mounts                           |
| 4        | [backend/noesis/api/routes/v1.py](backend/noesis/api/routes/v1.py)             | How 6 sub-routers aggregate to `/v1`                           |
| 5        | [backend/noesis/kernel/runtime.py](backend/noesis/kernel/runtime.py)           | AgentRuntime step loop: how agents run                         |
| 6        | [backend/noesis/uap/__init__.py](backend/noesis/uap/__init__.py)               | UAP envelope model + rebuild housekeeping                      |
| 7        | [backend/noesis/observability/metrics.py](backend/noesis/observability/metrics.py) | Counters, helpers, snapshot format                        |
| 8        | [backend/noesis/tools/registry.py](backend/noesis/tools/registry.py)           | Tool discovery + MAC capability enforcement                    |
| 9        | [backend/pyproject.toml](backend/pyproject.toml)                             | Ruff rule set + ignore list (style-only carry-over explained)  |
| 10       | [.github/workflows/ci.yml](.github/workflows/ci.yml)                         | 3 backend lanes + 2 frontend lanes (ubuntu + windows)          |

---

*Version: M6-complete (2026-03-18).  This document is append-only with
versioned sections.  The "gates" and "roster" tables update as we ship new
milestones; the architectural rules (§2.1) are edited only by consensus of
the full core team.*
