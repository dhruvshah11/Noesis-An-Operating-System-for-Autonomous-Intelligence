# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
for API-stable releases (1.0.0+).  Pre-1.0.0 releases may break minor-version
compat; see individual migration notes in the release notes.

---

## [Unreleased]

### Added

- **Milestone 0 foundation**: `noesis` Python package, strict mypy, ruff
  profile, Pydantic v2 shared types, 5-provider LLM Strategy layer,
  SQLAlchemy 2.0 Async (6 ORM models), typed Qdrant wrapper, Redis TTL
  cache helpers, FastAPI application factory with lifespan startup,
  /health/{livez,readyz} probes, structlog scrubbed structured logging.
- **CI/CD**: 3-job GitHub Actions matrix (lint/typecheck; pytest ubuntu/windows
  × py3.12/3.13; Docker smoke buildx).
- **Deployment**: Multi-stage backend Dockerfile + 3-service Docker Compose
  stack (backend / Qdrant 1.11 / Redis 7.4) with health-based `depends_on`
  and named persistent volumes.
- **Pagination**: `Page[T]` / `PageParams` cursor-based shared envelope.
- **API v1 prefix**: New `/v1` router mount; legacy `/health` redirects retained.
- **Alembic migrations**: Baseline `0001_milestone0_schema` revision covering
  all 6 ORM tables + indexes.
- **12-agent roster**: `AgentType` now includes JUDGE, CRITIC, EXECUTOR,
  SUPERVISOR (hierarchical Judge/Critic/Executor/Supervisor pattern).
- **Typed inter-agent signals**: `AgentMessageEnvelope` discriminated union
  over Think/Say/ToolCall/ToolResult/MemoryStore/Critic/Handoff.
- **Governance files**: MIT LICENSE, SECURITY.md (90-day disclosure policy),
  CODE_OF_CONDUCT.md (Contributor Covenant 2.1), bug/feature YAML issue
  templates, PR template, CODEOWNERS, FUNDING.yml, CITATION.cff,
  Dependabot config, pre-commit hooks.
- **World-class engineering audit**: 20-dimension `AUDIT.md` covering
  repository architecture, software architecture, code quality, API design,
  agent architecture, LLM engineering, memory, RAG, database, security,
  performance, frontend, DevOps, testing, documentation, OSS readiness,
  deployment, AI benchmarking, DX, and a 15-item future innovation
  roadmap with MoSCoW prioritization.

### Changed

- `AgentType` enumeration expanded from 8 to 12 entries.
- Root `/` endpoint now reports `"current_api_prefix": "/v1"` and points
  health checks at the v1 mount.
- CORS middleware now exposes `Idempotency-Key` header; `Idempotency-Key`
  middleware tracks the request header for M1+ idempotent writes.

### Security

- Structlog secret scrubbing is now recursive into nested dict/list values
  and additionally detects bearer-token / authorization patterns and
  `"secret"` suffixes anywhere in the key.

### Deprecated

- Bare `/health` (without `/v1` prefix) still works but is considered the
  legacy mount. Clients should migrate to `/v1/health/*`.

### Removed

- (None — first release.)

### Fixed

- CORS CSV env-variable parser runs via `Any` typed field to avoid
  pydantic-settings' pre-validator JSON parsing attempt on raw CSV strings.
- `tenacity` retry decorators dropped unsupported `min` / `multiplier` kwargs.
- `ChatMessage` invariants run as a `model_validator(mode="after")` so
  cross-field (role vs tool_call_id vs content) rules work consistently.
- `noesis.database` package uses `__getattr__` lazy loader for `QdrantStore` /
  `get_qdrant` so unit tests without `qdrant-client` installed still import.
- `OllamaProvider`/`ollama_provider.py` no longer uses `__import__` for
  `json` / `asyncio`.
- `_validate_sqlite_path` no longer performs side-effecting `os.makedirs`
  inside a Pydantic validator (side effect moved to `init_database`).
- All 5 providers share one `with_provider_retry` decorator.

### Known Issues

- No providers yet implement native circuit-breaker / fallback routing
  (added as ports + adapters; tracked by Milestone 0.2 SH-2).
- Prompt injection defence for RAG ingestion is not yet wired into the
  document pipeline (Milestone 3 hardening).
