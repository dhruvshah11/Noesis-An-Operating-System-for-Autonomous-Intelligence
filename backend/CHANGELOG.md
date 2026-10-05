# Changelog

All notable changes to the **Noesis — Autonomous Multi-Agent AI Operating System** project will be documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html)
(with pre-release tags for release-candidate builds distributed via TestPyPI / GitHub Releases).

---

## [Unreleased]

### Planned
- `v1.0.0` production freeze + CODS-COMAD / IHI upload camera-ready paper revisions.
- Public plugin marketplace (manifest signing + attestation).
- Distributed worker pool (RabbitMQ / Celery back-end for horizontal scaling).
- Fine-grained RLS on multi-tenant Postgres backend.
- Plugin sandbox WASM runtime (deny-by-default capability model).

---

## [0.2.0-rc2] — 2026-08-24

MS9 (Self-Host 10-PR Benchmark) + MS10 (RC2 packaging, SBOM, Release Checklist) corner deliverables.
First release candidate intended for **Docker Desktop self-host** + **GitHub Releases** distribution.

> Release-candidate builds are published to **TestPyPI** (`twine upload --repository testpypi`)
> and to **ghcr.io/dhruvshah11/noesis** container registry.  The final `0.2.0` tag will
> promote the same artefacts to main PyPI without recompilation, after the 30-minute soak
> test (step 14 of the release checklist) passes without regression.

### Added — Security / SBOM
- `backend/Dockerfile.laptop` — 3-stage (builder → installer → runtime slim) laptop/self-host image.
  Non-root `noesisapp` user (`uid=10001`), `HEALTHCHECK /health`, `EXPOSE 8000`,
  `CMD uvicorn noesis.api.main:app --host 0.0.0.0 --port 8000`.
- `backend/.dockerignore` — excludes `dist/`, `.venv`, `__pycache__`, `*.pyc`, `benchmarks/`,
  `.env`, secrets, coverage + IDE junk from the Docker build context.
- `backend/sbom/trivyignore` — **empty** policy file enforcing **0 HIGH / 0 CRITICAL**
  vulnerability exemptions for every RC cut.
- `backend/scripts/audit_sbom.sh` (+ `.ps1` PowerShell twin) — install hints for
  scoop/choco/apt/brew, then `syft packages … -o spdx-json=dist/noesis-sbom.spdx.json`
  followed by `trivy image --severity HIGH,CRITICAL --exit-code 1 local/noesis:0.2.0-rc2`.
- `pyproject.toml` → `[project.optional-dependencies]` → `security = ["syft", "trivy"]`
  installable group.

### Added — Self-Host Benchmark (MS9)
- `backend/benchmarks/selfhost/selfhost_10prs.json` — 10 synthetic PR descriptions
  covering auth, memory promotion, LLM failover, tristate, Next.js frontend,
  MAC audit, determinism C3, paper/thesis drafts, scheduler backpressure, and
  Docker+SBOM packaging.  Each entry carries `id`, `title`, `body`,
  `expected_files_changed`, `repo_path = repos/pr{id}_scratch`.
- `backend/scripts/bench_selfhost_10prs.py` — invokes the 12-agent Sanskrit-named
  seeded skeleton pipeline with `mode="selfhost"` against each PR, emits
  `docs/eval/results_selfhost/selfhost_report.csv` with columns
  `pr_id, tristate, plan_sha, duration_ms, files_created, lint_ok, test_ok`.
  `lint_ok` runs `ruff format --check` on the created workspace; `test_ok` runs
  `pytest` on any `test_*.py` files.  Supports `--smoke 2 --outdir …` sandbox
  exit-0 smoke test (creates 2 temp dirs, writes a fake `.py`, ruff checks it,
  cleans CWD on exit).

### Added — RC2 Packaging & Release Artifacts
- `backend/CHANGELOG.md` (this file) — Keep-a-Changelog 1.1 format.
- `RELEASE_CHECKLIST_v0.2.0_rc2.md` (repo root) — 15-step ordered checklist for
  Dhruv covering `git init`, `gh auth`, TestPyPI `hatch build clean` + `twine upload`,
  signed `v0.2.0-rc2` git tag, draft GitHub Release with wheel + SBOM attachments,
  Docker `ghcr.io/dhruvshah11/noesis:0.2.0-rc2` build+push, Trivy 0 HIGH/CRITICAL
  verification, 4-audit `run_all_audits.ps1` run, Vercel/Hetzner backend smoke,
  Frontend `npm run build` standalone export, 30-min soak test with `?demo=true`
  + 5 SE50 tasks, and Tweet/X + LinkedIn + Discord university announcement.

### Changed — Kernel / Memory / LLM (Summary §0 Code Changes Applied)
- **MAC audit / Viva Deny** — `noesis/kernel/capabilities.py` + `allocators.py`
  implement 4 deny scenarios (critic filesystem, tool-agent sudo, planner network
  socket, cross-workspace memory access).  `scripts/audit_mac_spawn.py` exit-0
  evidence captured in `docs/eval/mac_spawn_evidence.{md,json}`.
- **Promotion controller** — `noesis/memory/promotion.py` rewritten to a 4-phase
  controller (TTL scan → cosine deduplication → LLM criticality summary →
  provenanced promotion).  Integrated into scheduler loop with backpressure
  when the T2→T3 queue exceeds 200 entries; unit tests in
  `tests/unit/test_memory_promotion.py` and
  `tests/unit/test_memory_promotion_wiring.py`.
- **LLM provider failover** — `noesis/llm/factory.py` adds `FailoverLLMProvider`
  with 4-provider chain (OpenAI → Anthropic → Gemini → OpenRouter).  Circuit
  breaker trips after 3 consecutive 5xx / timeouts, resets after 60 s.
  Prometheus counter `noesis_llm_failover_total{from,to}` emitted per switch.
  Evidence in `docs/eval/llm_provider_audit.json`.
- **Executor tristate** — Kriyakārī/ExecutorAgent emits `TriStateDecision`
  (`signoff | reject | replan`).  Severity-driven gating: ≥1 high unmet →
  `REPLAN`, any critical unmet → `REJECT`, else `SIGNOFF`.  Seeded pipeline
  `run_full_seeded_pipeline.py` exit code reflects the all-SIGNOFF invariant.
  Tests in `tests/unit/test_executor_tristate.py`.
- **Front-end rewrites** — Next.js `app/conversations`, `app/memory/explorer`,
  `app/agents`, `app/timeline`, `app/metrics`, `app/settings` pages rewritten
  with Tailwind v3 + shadcn/ui.  SSE streaming from `/v1/kernel/stream/:run_id`
  renders the 12-agent pipeline timeline on the conversations page.
- **Paper / thesis drafts** — `docs/paper/` (6 sections: abstract, intro,
  related work, architecture/methodology, implementation/evaluation,
  discussion/conclusion, references) + `docs/thesis/chapters/01…08.md`
  (Introduction, Literature Survey, System Architecture, Methodology,
  Implementation, Evaluation, Future Work, Conclusion).
- **Determinism C3** — `scripts/determinism_manifest.py` produces SHA-256
  canonical JSON per run, reproducibility identity matrix, CSV manifest.
  `reproducibility_score = 1.0` target on 100 runs × 5 goals × seed=42.
- **SE50 corpus + 3-run evidence** — `benchmarks/noesis_se50/corpus.{csv,json}`
  with goals.txt; `docs/eval/se50_determinism_3runs.csv` + summary JSON.

### Fixed
- `noesis/api/main.py` — stray `Pydantic` `ValidationError` raised inside endpoints
  is now caught by a dedicated `_pydantic_validation_handler` that returns a
  structured 500 envelope instead of leaking raw traces to the client.
- `noesis/database/sql.py` — `async_session()` context manager leak on Windows
  IOCP event loop fixed in integration teardown; `test_kernel_e2e.py` no longer
  hangs on the close path.

### Security
- `Dockerfile.laptop` drops root → fixed-UID `noesisapp:noesisapp (10001:10001)`
  before running `uvicorn`, compatible with Kubernetes `runAsNonRoot: true`
  Pod Security Standards on self-hosted clusters.
- `trivyignore` empty-policy enforces 0 HIGH/CRITICAL CVE exemptions; every
  release build is gated by `audit_sbom.{sh,ps1}` → `trivy --exit-code 1`.
- `/health` endpoints are unauthenticated but read-only; every other route
  continues to require `Authorization: Bearer <JWT>` via `noesis/api/deps.py`.
- Determinism pipeline strips opaque UUIDs / wall-clock keys from the manifest
  hash input so the audit only compares *semantic* outputs.

---

## [0.1.0] — 2026-07-15

Milestone 5 (MVP) release — initial wheel build shipped to internal testers.

### Added
- Full 12-agent Sanskrit-named pipeline (Manan → Darshak → Vidya → Parikshak →
  Karmakarta → Anveshak → Vivechak → Paalak → Rakshak → Samanyaka → Kriyakārī →
  Nirikshak) with deterministic seeded skeleton.
- 6-tier memory model (T1 Indriya … T6 Tattva) with initial tiered-list heuristic.
- FastAPI `noesis.api.main:app` with `/v1`, `/health`, `/metrics`, `/llm_benchmark`
  route groups, CORS, GZip, X-Request-ID middleware, structured JSON envelope.
- SQLite + Alembic schema `0001_milestone0_schema.py` → `0002_milestone5_mvp.py`.
- Initial LLM provider adapters (OpenAI, Anthropic, Gemini, Ollama, OpenRouter).
- Plugin system (`noesis/plugins/`) with hookspec + manifest + capability tokens.
- RAG pipeline (`noesis/rag/pipeline.py`) with Qdrant vector store + Redis KV tier.
- Prometheus metrics (`noesis/observability/metrics.py`) + `/metrics` endpoint.
- `pyproject.toml` (hatchling build backend) + first `dist/noesis-0.1.0-py3-none-any.whl`.
- `docs/eval/run_all_audits.ps1` — 4-audit bundle (MAC spawn, determinism manifest,
  LLM provider audit, memory promotion placeholder).
- Frontend Next.js scaffold with `.next` standalone export.

---

[Unreleased]: https://github.com/dhruvshah11/noesis/compare/v0.2.0-rc2...HEAD
[0.2.0-rc2]: https://github.com/dhruvshah11/noesis/compare/v0.1.0...v0.2.0-rc2
[0.1.0]: https://github.com/dhruvshah11/noesis/releases/tag/v0.1.0
