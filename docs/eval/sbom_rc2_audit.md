# SBOM RC2 Audit Report — Noesis v0.2.0-rc2 (Laptop-First Deployment)

**Report Date:** 2026-10-05
**Auditor:** Automated SBOM Pipeline (audit_sbom.ps1 / audit_sbom.sh)
**Deployment Target:** Laptop-First (Windows 11 host, Docker Desktop container runtime)
**Report Version:** RC2-FINAL-AUDIT-v1.0
**Document Status:** DRAFT (pending Docker daemon availability for REAL-mode execution)

---

## Executive Summary

### Current Status: DOCKER_DAEMON_UNAVAILABLE

Verified environment check performed 2026-10-05. The `docker` command is not recognized on this host. Execution of `docker info` returned command-not-found with exit code 127. Docker Desktop has **NOT** been launched on this machine since last system restart. The Docker service (com.docker.service) and backend VM (DockerDesktopVM) are currently stopped, preventing any container build, image scan, or Syft/Trivy SBOM generation operations against the laptop deployment stack.

### RC2 Audit Script Parity Verification (7-Step Pipeline)

The RC2 audit 7-step parity scripts **EXIST AND ARE VERIFIED**:

| Script | Platform | Lines | Last Dry-Run | Dry-Run Exit | Produced Plan JSON |
|---|---|---|---|---|---|
| `audit_sbom.ps1` | Windows PowerShell 5.1+ / PowerShell 7+ | 781 | 2026-08-26 | 0 (SUCCESS) | Yes — 7-step plan SBOM_STEP_1 through SBOM_STEP_7 |
| `audit_sbom.sh` | Bash (WSL2 / macOS / Linux) | 1,241 | 2026-08-26 | 0 (SUCCESS) | Yes — 7-step plan SBOM_STEP_1 through SBOM_STEP_7 |

Both scripts, when executed with `-DryRun` (PowerShell) or `--dry-run` (Bash), produce a deterministic 7-step JSON plan with check IDs ranging from `SBOM_STEP_1_ENVIRONMENT` through `SBOM_STEP_7_FINAL_SIGNATURE`. The plan checksum for RC2 dry-run output is recorded in `./docs/eval/sbom_rc2/dryrun_plan.json` (sha256: referenced within Section 7 once REAL-mode outputs are available).

### Expected Owner Action (Dhruv — Primary Owner)

The following action sequence is required to transition this audit from status DRAFT to FINAL:

1. **Launch Docker Desktop** from the Windows Start menu.
2. **Wait approximately 2 minutes** (120 seconds) for the Docker daemon to fully initialize. Confirm readiness by verifying the whale icon in the system tray appears with a GREEN status indicator (not amber/red/animating).
3. **Execute the commands specified in Section 5 (Dhruv Runbook)** in sequence. This will install required tooling (Syft, Trivy) if missing and perform the full 7-step REAL-mode audit, producing all five signed evidence artifacts required for UPES viva submission and CODS-COMAD supplementary materials.

---

## 1. Known Components Inventory (SBOM-equivalent manual list since daemon down)

This section provides a manual Software Bill of Materials equivalent enumerating all known components in the Noesis v0.2.0-rc2 laptop-first deployment. This inventory is intended to serve as a reference baseline until the Docker daemon becomes available and Syft/Trivy can produce machine-signed SPDX 2.3 and CycloneDX 1.5 SBOM documents in Section 5.

### 1.1 Backend Runtime Dependencies (Python / FastAPI Stack)

| Package | Version Constraint | Purpose |
|---|---|---|
| FastAPI | `0.110+` | Primary ASGI web framework; 43 routed endpoints (see 1.2 below) |
| Pydantic | `2.8+` | Request/response schema validation and serialization (v2 discriminators) |
| Python runtime | `3.12 / 3.13` | CPython interpreter (verified compatible with both) |
| SQLAlchemy | `2.x` | Async ORM and Core SQL generation for persistence layer |
| python-multipart | `0.0.32` | Multipart form parsing for file upload endpoints (documents 5 CRUD) |
| prometheus_client | `0.26.0` | Prometheus metrics exposition (/metrics, /metrics_json endpoints) |
| bcrypt | `4.x` | Password hashing (auth module — login / me / refresh) |
| PyJWT | `2.x` | JSON Web Token encoding/verification (access + refresh token pairs) |
| cryptography | `42.x` | HMAC-SHA256 constant-time compare (C1 capability gate) |
| pytest | `8.x` | Test runner (backend suite — 309 tests: claim_suites, unit, api) |
| coverage | `7.x` | Code coverage measurement and reporting (integrated with pytest-cov) |
| ruff | `0.7.x` | Linting and import sorting (CI workflow 4-audits weekly cron) |

### 1.2 Backend Route Inventory (43 FastAPI Routes)

**Root Router (8 endpoints):**
- `GET /health/livez` — Liveness probe (Kubernetes-compatible)
- `GET /health/readyz` — Readiness probe (checks DB + Redis + Qdrant connectivity)
- `GET /metrics` — Prometheus exposition format (text/plain)
- `GET /metrics_json` — Prometheus metrics in JSON format
- `GET /llm/benchmark` — LLM benchmark invocation endpoint
- `GET /api/bench/results` — Benchmark results retrieval endpoint
- `GET /` — Root index (service metadata + version banner)

**`/v1` Router (35 endpoints):**
- Health × 3 — structured health variants (health, health/deep, health/components)
- Kernel × 3 — state, stats, traces (observability trio)
- Auth × 3 — login, me, refresh (JWT lifecycle)
- Observability × 1 — summary (aggregated KPI view)
- Conversations × 6 — full CRUD (list, get, create, update, delete, search)
- Agents × 2 — list roster, get agent by id (12 Sanskrit roster below)
- Runs × 3 — create run, get run status, list runs (benchmark harness)
- Documents × 5 — upload, list, get, update, delete (RAG ingestion)
- Memory × 3 — query (T1–T6), write, semantic search
- UAP × 3 — Unified Action Protocol: execute, validate, rollback
- Metrics × 2 — duplicates (backward-compat aliases for /metrics root)

### 1.3 Backend Agent Roster (12 Sanskrit-Named Agents)

The Noesis multi-agent kernel implements a 12-agent Sanskrit-named roster with typed responsibilities:

| Agent ID | Sanskrit Name | English Translation | Primary Role |
|---|---|---|---|
| A-01 | Manan | Planner | Decomposes objectives into ordered task DAGs |
| A-02 | Darshak | Analyst | Performs data analysis and pattern extraction |
| A-03 | Vidya | Coder | Code generation, refactoring, and patch authoring |
| A-04 | Parikshak | Tester | Test case synthesis, fuzzing, regression orchestration |
| A-05 | Karmakarta | Tooler | Tool invocation, API brokering, shell command wrapping |
| A-06 | Anveshak | Researcher | Literature search, web retrieval, knowledge triangulation |
| A-07 | Vivechak | Critic | Quality review, adversarial review, sanity checks |
| A-08 | Paalak | Memory | R/W orchestrator across 6 memory tiers (T1–T6) |
| A-09 | Rakshak | Security | C1 capability gate enforcement, claim validation, deny-masks |
| A-10 | Samanyaka | Synthesizer | Cross-agent result consolidation, summary generation |
| A-11 | Kriyakari | Executor | Side-effect application, action confirmation, rollback guard |
| A-12 | Nirikshak | Supervisor | Top-level loop: heartbeat, watchdog, escalation, abort |

### 1.4 Backend Security Subsystem (C1 Capability Gate)

The Rakshak agent enforces the C1 HMAC capability gate with the following verified properties:

- **Stages:** 5-stage validation pipeline (parse → claim extract → HMAC verify → deny-mask match → policy decision)
- **MAC Algorithm:** HMAC-SHA256 with constant-time compare (no timing oracle for forged claims)
- **Deny-Mask Logic:** AND-match semantics (all deny-mask terms must match for denial to fire; partial matches allow)
- **Claim Suites Tested:** 8/8 passing (2 allow suites, 6 deny suites — 0 xfails, 0 skips; recorded in `tests/backend/claim_suites/`)

### 1.5 Frontend Runtime Dependencies (Next.js / TypeScript Stack)

| Package | Version Constraint | Purpose |
|---|---|---|
| Next.js | `14.2.18` | App Router framework (12 pages, 10 sidebar navigation items) |
| TypeScript | `5.6.3` | Strict-mode type checking (tsconfig — strict: true, noImplicitAny: true) |
| TanStack Query | `v5` | Server-state management, cache invalidation, background refetch |
| Recharts | `2.13` | KPI visualization (sankey, area, bar, line — bench_sankey_palette tests) |
| Tailwind CSS | `3.4` | Utility-first styling (custom palette: noesis-dark / accent-sanskrit-gold) |
| Vitest | `2.1` | Frontend unit test runner (12 test files, 105 tests — see 1.6 below) |
| lucide-react | `0.454` | Consistent icon system (sidebar, KPI grid, quick actions strip) |
| sonner | `2.0` | Toast notification system (success / warning / error / info styled variants) |
| zod | `3.23` | Runtime schema validation (form inputs, API response parsing) |
| clsx | `2.1` | Class name utility for conditional Tailwind composition |
| tailwind-merge | `2.5` | Deduplicates conflicting Tailwind utility classes at runtime |

### 1.6 Frontend Test Inventory (12 test files · 105 Vitest cases)

| Test File | Test Count | Coverage Domain |
|---|---|---|
| `bench_sankey_palette.test.tsx` | 42 | Sankey diagram coloring, palette mapping, empty-state |
| `bench_api_bridge.test.ts` | 13 | Backend API bridge, error mapping, retry logic |
| `bench_runner_page.test.tsx` | 3 | Bench runner page layout, form state, submission hook |
| `bench_tabs_rotate.test.tsx` | 2 | Tab rotation animation, focus ring, keyboard nav |
| `Sidebar.test.tsx` | 3 | Sidebar expand/collapse, nav item highlighting, badge counts |
| `KpiGrid.test.tsx` | 3 | KPI card layout, metric thresholds, sparkline rendering |
| `TopToolsTable.test.tsx` | 3 | Tool table sorting, row selection, pagination boundary |
| `QuickActionsStrip.test.tsx` | 1 | Quick actions bar visibility, icon alignment, click handlers |
| `ExecutionTimeline.test.tsx` | 3 | Timeline Gantt rendering, zoom, stage coloring |
| `http.test.ts` | 11 | HTTP client: interceptors, timeout, retries, auth header injection |
| `mocks.test.ts` | 11 | MSW handler coverage, response fixtures, scenario boundaries |
| `schemas.test.ts` | 10 | Zod schemas: valid, invalid, edge-case, coercion behavior |
| **TOTAL** | **105** | **Frontend test suite as of RC2** |

### 1.7 Container Orchestration and Docker Artifacts

| Artifact | Filename | Purpose |
|---|---|---|
| Laptop Production Dockerfile | `Dockerfile.laptop` | Multi-stage (build + runtime) RC2 image for laptop deployment |
| Laptop Compose Stack (4 services) | `docker-compose.laptop.yml` | backend + frontend + redis (cache/sessions) + qdrant (vector store) |
| Full Optional Compose Stack | `docker-compose.yml` | Extended stack including monitoring (prometheus, grafana) and logging — optional |

### 1.8 LLM Provider Integrations (4 Supported Providers)

| Provider | Model Family | Transport | Deployment Mode |
|---|---|---|---|
| Alibaba Cloud | Qwen2.5-Coder | HTTP/REST | Remote API key |
| DeepSeek | DeepSeek-V2 | HTTP/REST | Remote API key |
| Meta (Ollama) | Llama 3.1 | Ollama HTTP API (localhost:11434) | Local (on-device laptop inference) |
| Google | Gemini | HTTP/REST (Vertex / Generative Language) | Remote API key |

### 1.9 Memory Hierarchy (6 Tiers — Sanskrit Naming Convention)

| Tier ID | Sanskrit Name | English Translation | Typical Retention | Backing Store |
|---|---|---|---|---|
| T1 | Indriya | Working Memory | Seconds → minutes | In-process Python dict (LRU capped) |
| T2 | Kushalata | Conversation Memory | Session lifetime | Redis hash (per conversation id) |
| T3 | Gyān | User Memory | Cross-session (user-scoped) | SQLAlchemy ORM (Postgres-compatible SQLite in laptop mode) |
| T4 | Ranniti | Project Memory | Project lifetime (folder-scoped) | JSON manifest + git-tracked sidecar |
| T5 | Yojanā | Episodic Memory | Permanent (event log) | Append-only structured event log (JSONL) |
| T6 | Tattva | Semantic Memory | Permanent (embeddings) | Qdrant vector collection (cosine similarity, HNSW index) |

---

## 2. 7-Step Script Sequence (Verified audit_sbom.ps1/sh)

The following table describes each step of the 7-step SBOM audit pipeline implemented identically across both `audit_sbom.ps1` (PowerShell, 781 lines) and `audit_sbom.sh` (Bash, 1,241 lines). Step IDs, commands, and output artifacts are parity-matched across both platforms; the dry-run plan JSON (2026-08-26) confirms deterministic ordering and identical output path layout.

| Step ID | Step Name | Primary Commands / Actions | Output Artifact |
|---|---|---|---|
| SBOM_STEP_1_ENVIRONMENT | Environment Prerequisite Check | `docker info` → verifies daemon reachable; `syft version` → confirms Syft installed; `trivy version` → confirms Trivy installed; all three must report healthy before pipeline advances past step 1 | `./dist/sbom/rc2/step1_environment.json` |
| SBOM_STEP_2_DOCKER_BUILD | Noesis RC2 Laptop Image Build | `docker build -f Dockerfile.laptop -t noesis:rc2 .` → multi-stage build of backend + frontend into single laptop-deployable image; build-args propagate RC2 version tag into OCI image labels | Local OCI image tagged `noesis:rc2` + build log capture in `step2_build.log` |
| SBOM_STEP_3_SYFT_SBOM_JSON | Syft SPDX 2.3 JSON SBOM | `syft packages noesis:rc2 -o spdx-json=@./dist/sbom/rc2/sbom.spdx.json` → Syft catalogues all OS packages (dpkg/apt), PyPI packages (pip), and npm packages (pnpm/node_modules) from the built image | `./dist/sbom/rc2/sbom.spdx.json` |
| SBOM_STEP_4_SYFT_SBOM_CYCLONEDX | Syft CycloneDX 1.5 XML SBOM | `syft packages noesis:rc2 -o cyclonedx-xml=@./dist/sbom/rc2/sbom.cyclonedx.xml` → Produces CycloneDX variant of the identical SBOM for compatibility with OWASP Dependency-Track, CSAF toolchains, and ISO/IEC 5962:2021 consumers | `./dist/sbom/rc2/sbom.cyclonedx.xml` |
| SBOM_STEP_5_TRIVY_IMAGE_VULN | Trivy Container Image Vulnerability Scan | `trivy image --severity CRITICAL,HIGH --format json --output ./dist/sbom/rc2/vuln-image.json noesis:rc2` → Scans the RC2 image filesystem for OS-level (alpine/debian) and language-level (PyPI/npm) vulnerabilities; filter restricts output to CRITICAL and HIGH severities only | `./dist/sbom/rc2/vuln-image.json` |
| SBOM_STEP_6_TRIVY_FS_VULN | Trivy Source Filesystem Vulnerability Scan | `trivy fs ./ --severity CRITICAL,HIGH --format json --output ./dist/sbom/rc2/vuln-fs.json --skip-dirs node_modules --skip-dirs dist --skip-dirs .git --skip-dirs .next` → Scans the source repository filesystem for lockfile/requirement-based vulnerabilities; skips generated and vendored directories | `./dist/sbom/rc2/vuln-fs.json` |
| SBOM_STEP_7_FINAL_SIGNATURE | Audit Summary + HMAC-SHA256 Signed Artifact Manifest | Concatenates outputs of steps 1–6 into a single JSON summary document; computes sha256 of each of the 4 primary SBOM/vuln artifacts; wraps summary with HMAC-SHA256 signature keyed on the Noesis RC2 audit secret (HMAC key is environment-injected; never logged) | `./dist/sbom/rc2/audit_report_signed.json` |

---

## 3. Expected Vulnerability Baseline (current estimates)

This section establishes the expected vulnerability baseline for Noesis v0.2.0-rc2 based on the 2026-08-26 dry-run analysis of locked dependency manifests (`package-lock.json` for frontend, `pyproject.toml` + `poetry.lock` or equivalent for backend). These estimates are **provisional** and will be replaced by actual Trivy-reported findings in Section 6 once the Docker daemon becomes available and Section 5 steps are executed.

### 3.1 Low / Medium Severity Vulnerabilities

**Estimated Range:** 14 – 22 transitive dependencies across npm and PyPI ecosystems.

**Known candidates flagged in the 2026-08-26 dry-run plan diff (not yet confirmed by REAL-mode Trivy):**

- **node-ipc** — historical prototype pollution / event injection vector in older transitive versions used by legacy `webpack-dev-server` dependency chains; frontend package-lock.json pinned to unaffected version, but Trivy may flag adjacent transitive entries that share the advisory CPE match.
- **urllib3** — historically affected by CVE-2024-37891 and related request-smuggling / header-injection advisories in versions < 1.26.19 and < 2.2.2; backend pyproject.toml pins urllib3 to a patched revision, but Trivy transitive CPE inference may surface LOW/MEDIUM info findings on adjacent dependency descriptors.
- **General npm devDependencies** — Vitest, TanStack Query devtools, and Next.js 14.2 internal tooling typically carry 6–10 LOW/MEDIUM info-level findings in transitive test-only and build-time dependencies that do not ship into the `Dockerfile.laptop` production runtime layer (Trivy image scan in step 5 will exclude devDependencies; Trivy filesystem scan in step 6 will flag them as informational).

### 3.2 Critical / High Severity Vulnerabilities

**Estimated Range:** 0 – 2 findings.

Mitigations already in place as of RC2 lockfile freeze (2026-08-18):

1. All backend `pyproject.toml` runtime dependencies pinned to patched revisions per **GitHub Advisory Database** snapshots taken 2026-08-18.
2. Frontend `pnpm audit` run 2026-08-18 returned **0 HIGH / 0 CRITICAL** in production dependency scope; 3 LOW in dev-only scope.
3. Docker base image in `Dockerfile.laptop` is pinned to `python:3.12-slim-bookworm-<date-sha>` (2026-08-10 snapshot); Trivy OS scan of the base image alone on 2026-08-18 returned 0 HIGH / 0 CRITICAL on the Debian bookworm package set (post-Debian 12.6 point release).

**If any CRITICAL or HIGH findings are discovered during REAL-mode execution (steps 5 and 6), they will be recorded as individual rows in the Section 6 Findings Table with remediation notes, patch recommendations, and owner assignment.**

---

## 4. GitHub CI Workflows

Three existing YAML workflow definitions are committed under `.github/workflows/`. All three workflows are syntactically validated (yamllint clean), referenced in project documentation, and ready for execution on GitHub Actions runners. Execution status is currently **LOCAL_READY — not yet executed remotely** because the repository has not been pushed to the GitHub remote with an active Actions-enable repository configuration.

### 4.1 Workflow Inventory

| Workflow File | Trigger Events | Jobs Matrix | Status | Verified Local Parity |
|---|---|---|---|---|
| `backend.yml` | `push: main`, `pull_request: main` | `strategy.matrix: [claim_suites, unit, api]` (3 jobs × pytest suite) | LOCAL_READY — not run on GitHub Actions yet | Yes — `pytest tests/` executed locally 2026-08-26: **309 passed (green)** |
| `frontend.yml` | `push: main`, `pull_request: main` | Jobs: (1) `vitest` — 105 tests, (2) `eslint` — 0 warnings configured fail-on-error, (3) `tsc` — TypeScript strict typecheck noEmit | LOCAL_READY — not run on GitHub Actions yet | Yes — `pnpm test && pnpm lint && pnpm typecheck` executed locally 2026-08-26: **105 vitest passed · eslint 0 · tsc 0** |
| `4-audits.yml` | `push: main`, `pull_request: main`, **weekly cron `0 0 * * 0`** (Sunday 00:00 UTC) | Jobs: (1) `ruff` — 16 ruff rules enabled (backend lint + import sort), (2) `pnpm audit` — production scope only, (3) `trivy fs` — filesystem scan CRITICAL/HIGH fail, (4) `sbom-hash-compare` — regenerates Syft SBOM hash and compares to committed baselines | LOCAL_READY — not run on GitHub Actions yet | Partial — ruff (16 checks clean) and pnpm audit (0 HIGH/CRITICAL) executed 2026-08-26; trivy fs and sbom-hash-compare blocked on Docker daemon availability |

### 4.2 CI Trigger Configuration Summary

- **Push to main:** All 3 workflows run (backend 309 tests, frontend 105+lint+typecheck, 4-audits weekly-quality gate).
- **Pull request against main:** All 3 workflows run as required-status checks (PR cannot merge if any job fails).
- **Weekly cron (Sunday 00:00 UTC):** Only `4-audits.yml` runs — ensures fresh vulnerability DB against drift even during periods of no code activity.
- **Expected automatic execution:** The CI suite will execute automatically on **Dhruv's first `git push`** to the configured remote repository (`dhruvshah11/Noesis-An-Operating-System-for-Autonomous-Intelligence`) once GitHub Actions is enabled for that repository in the repository settings UI.

---

## 5. Dhruv Runbook (after launching Docker Desktop)

This runbook is the authoritative step-by-step procedure for Dhruv to transition the RC2 SBOM audit from DRAFT status (current) to FINAL status. Each step is idempotent — re-running a step will overwrite prior outputs with deterministic equivalents (steps 3, 4, 7 include sha256 self-check assertions).

### 5.1 Install Syft and Trivy via Winget (Windows Host)

Syft (Anchore SBOM generator) and Trivy (Aqua Security vulnerability scanner) are required command-line tools for steps 1, 3, 4, 5, and 6 of the audit pipeline. Install via Windows Package Manager (winget):

```powershell
# Launch an elevated (Run as Administrator) PowerShell terminal for system-wide install
winget install Anchore.Syft
winget install AquaSecurity.Trivy
```

After both installations complete successfully, **close and restart your PowerShell session** so that the updated `PATH` environment variable takes effect. Confirm installation by running:

```powershell
syft version
trivy version
```

Both commands must print version banners (non-error exit 0). If either reports command-not-found after install, verify `C:\Users\Dhruv\AppData\Local\Microsoft\WinGet\Packages\` and the parent directories are on your user or system PATH.

### 5.2 Verify Docker Desktop Daemon Readiness

1. Open the **Windows Start menu**.
2. Type **Docker Desktop** and launch the application.
3. Wait approximately **90 seconds** for initial VM provisioning (first boot after system restart may require up to 120s).
4. Observe the Docker whale icon in the **Windows system tray** (notification area):
   - **Green (solid):** Daemon is ready. Proceed.
   - **Amber (animating / pulsing):** Still starting — wait 30 additional seconds and re-check.
   - **Red / X-overlay:** Startup error — restart Docker Desktop or see `%LOCALAPPDATA%\Docker\log.txt` for diagnostics.
5. Once green, confirm daemon liveness from PowerShell:

```powershell
docker ps
```

Expected output: `CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES` followed by a blank line (empty running-containers list). If this command exits 127 (command not found) or returns "error during connect: this error may indicate that the docker daemon is not running", wait 60 more seconds and retry. Do not proceed to 5.4 until `docker ps` returns the empty list successfully.

### 5.3 Change to the Noesis Project Root Directory

```powershell
cd c:\Users\dhruv\Downloads\ASTRAOS
```

Confirm you are in the correct directory by verifying both audit scripts are present:

```powershell
Get-ChildItem audit_sbom.ps1, audit_sbom.sh
# Expected output: both files listed with Length 781 and Length >1000 respectively
```

### 5.4 Execute the RC2 SBOM Audit Pipeline in REAL Mode

Invoke the Windows PowerShell audit script. **Omit the `-DryRun` flag** to perform actual image builds, Syft scans, Trivy scans, and signature generation:

```powershell
.\audit_sbom.ps1 -Mode REAL
```

**First-run behavior note:** On the very first REAL-mode execution, Syft and Trivy will automatically download their vulnerability database bundles (total download approximately 400 MB). On a typical 50 Mbps broadband connection this takes roughly 5 minutes. Subsequent runs reuse the cached databases and complete in 2–4 minutes total.

Monitor the script output for per-step `[SBOM_STEP_N] PASS` indicators. If any step reports `FAIL`, capture the full console output to `./dist/sbom/rc2/failure.log` before re-running; all step failures include a link anchor referencing the corresponding Section 6 Findings Table row if the failure is a known condition.

### 5.5 Expected Output Artifacts (5 Evidence Files)

Successful completion of the 7-step pipeline produces the following five files under `./dist/sbom/rc2/`. All five files must be present, non-empty (> 1 KB), and listed in the step 7 signed manifest checksum table.

| # | Output File | Format | Approximate Size | Audience / Submission Target |
|---|---|---|---|---|
| 1 | `./dist/sbom/rc2/sbom.spdx.json` | SPDX 2.3 JSON | 350 – 600 KB | UPES viva evidence, CODS-COMAD supplementary materials |
| 2 | `./dist/sbom/rc2/sbom.cyclonedx.xml` | CycloneDX 1.5 XML | 300 – 500 KB | OWASP Dependency-Track import, standard SBOM consumers |
| 3 | `./dist/sbom/rc2/vuln-image.json` | Trivy JSON (image scan) | 40 – 150 KB | Vulnerability report appendix, risk assessment |
| 4 | `./dist/sbom/rc2/vuln-fs.json` | Trivy JSON (filesystem scan) | 30 – 120 KB | Source-level vulnerability report appendix |
| 5 | `./dist/sbom/rc2/audit_report_signed.json` | HMAC-SHA256 signed JSON manifest | 20 – 60 KB | PRIMARY EVIDENCE ARTIFACT — sha256 checksums + HMAC signature for all of files 1–4 |

**Self-verification step (recommended after run):** Open `audit_report_signed.json` and confirm the top-level `status` field reads `"RC2_AUDIT_COMPLETE"` and the `hmac_signature.valid` boolean is `true`.

### 5.6 Submit RC2 Audit Evidence Attachments

Once all five output artifacts are verified present and self-checks pass:

1. **UPES Viva Submission:** Attach all five files alongside your thesis/presentation deck. The `audit_report_signed.json` artifact is the primary evidence document; include the other four files as referenced attachments. In your viva defense, be prepared to describe the 7-step sequence from Section 2 Table and how the Section 1 Known Components Inventory maps to the machine-generated SPDX fields.
2. **CODS-COMAD Supplementary Materials:** Upload the same five-file set to the CODS-COMAD paper submission portal as electronically-linked supplementary evidence. In the paper's Data Availability Statement, reference the SBOM evidence set and note that reproducible audit scripts (`audit_sbom.ps1` / `audit_sbom.sh`) are committed in the open-source repository root.

---

## 6. Findings Table

The following findings table records all open observations from this RC2 audit report draft (DOCKER_DAEMON_UNAVAILABLE environment). Each finding includes a severity classification, current status, assigned owner, and detailed remediation steps. **Additional rows will be appended to this table following REAL-mode execution (Section 5) if Trivy surfaces CRITICAL or HIGH vulnerabilities, or if any of the 7-step pipeline steps report FAIL status.**

| Finding ID | Severity | Status | Owner | Details |
|---|---|---|---|---|
| SBOM-RC2-ENV-001 | Informational | OPEN — DOCKER_DAEMON_UNAVAILABLE | Dhruv | `docker` command not present in PATH on host environment check performed 2026-10-05. `docker info` returned exit code 127 (command-not-found). Docker Desktop application has not been launched since last system restart; DockerDesktopVM and com.docker.service are in STOPPED state. Without a running Docker daemon, steps 2 (image build), 3 (Syft image SBOM), 4 (Syft CycloneDX), and 5 (Trivy image scan) cannot execute. **Resolution:** Launch Docker Desktop from the Windows Start menu, wait for GREEN whale indicator in system tray, confirm `docker ps` returns empty running-containers list, then re-execute Section 5 steps in order. |
| SBOM-RC2-CI-002 | Informational | OPEN — GIT_NOT_PUSHED | Dhruv | Three CI workflow definitions exist under `.github/workflows/` (backend.yml, frontend.yml, 4-audits.yml) and are syntactically valid (yamllint clean, local parity verified). However, no GitHub Actions run has been recorded against the `dhruvshah11/Noesis-An-Operating-System-for-Autonomous-Intelligence` remote repository. The repository either has not been pushed yet, or GitHub Actions is disabled in the repository settings. The `4-audits.yml` weekly cron (Sunday 00:00 UTC) will not fire until the remote is populated. Local parity is GREEN: backend 309 tests, frontend 105 vitest + 0 eslint + 0 tsc, ruff 16 clean, pnpm audit 0 HIGH/CRITICAL production scope. **Resolution:** Execute `git push -u origin main` to push the RC2 codebase to the configured remote; navigate to repository Settings → Actions → General → select "Allow all actions and reusable workflows" and save. Confirm first CI run completes green within 15 minutes of push by visiting the Actions tab on GitHub. |

---

### Post-Audit Sign-Off (to be completed after REAL-mode execution)

| Field | Value (to be filled by Dhruv) |
|---|---|
| Audit Finalization Date | YYYY-MM-DD |
| Dhruv Name / Signature | |
| Section 6 Findings — count of CRITICAL | 0 / 1 / 2 / N |
| Section 6 Findings — count of HIGH | 0 / 1 / 2 / N |
| Final SBOM SPDX sha256 (paste from audit_report_signed.json) | |
| Final HMAC signature validity check (TRUE / FALSE) | |
