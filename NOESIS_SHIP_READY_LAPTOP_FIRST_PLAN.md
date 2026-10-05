================================================================================
NOESIS — SHIP-READY MAJOR PROJECT + RESEARCH PAPER PLAN
               (LAPTOP-FIRST, Jetson deferred to Week 16 hardware demo)
================================================================================
Owner:  Dhruv Shah · @dhruvshah11   ·   Final-Year B.Tech / B.E. Capstone
Status: Active · 18-week execution · Laptop-first (Windows / macOS / Linux)

CHANGE LOG (v1.1):
  • Jetson Orin Nano section (previously Weeks 1-2, W14 deploy) REPOSITIONED to
    W16 "Viva Hardware Demo" (optional, non-blocking for thesis + paper).
  • ALL benchmarks (W7-W9) and baseline work now run LOCALLY on Dhruv's laptop
    via Ollama + llama.cpp server with GPU acceleration (NVIDIA RTX or Apple M
    family). 0 token fees.
  • OllamaProvider (already shipped) is the default inference target through
    Week 10. Jetson bootcamp is W16 one-week sprint.
================================================================================

0.  MISSION & THREE FINAL DELIVERABLES
================================================================================

| # | Deliverable | Target Output | Rubric Weight |
|:-:|:---|:---|:---:|
| 1 | Ship-Ready Code Release **Noesis v1.0** | `pip install noesis` package · GitHub release tag v1.0.0 · 8-page Next.js studio wired to live kernel · laptop `docker compose up` single command · 100-consecutive-run determinism audit manifest published · OpenAPI 3.1 spec snapshot frozen | 30% |
| 2 | Major Project (University capstone) | Synopsis approved · 60-page IEEE-style thesis (Chapters 1-8) · 19-slide Viva deck · 4 scripted live viva demos (MAC non-bypass, bit-exact reproducibility, end-to-end PR, laptop offline mode) | 40% |
| 3 | 6-page Research Paper — Conference Ready | Venue primary: CODS-COMAD 2027 (Jan 2027, IIT Bombay, Scopus, student deadline ~Nov 2026). Fallback: ICAC3 2027 · arXiv:cs.AI preprint. ACM 2-col SigConf, 8–10 cited references, 3 novelty claims, 4 benchmark result tables + p-value bars. | 30% |

================================================================================
1.  LAPTOP ENVIRONMENT (do once — 20 minutes) — ZERO COST, 0 TOKENS FOREVER
================================================================================

Laptop used: Dhruv Shah's personal laptop (Windows 11 / RTX 40xx with 8GB+ VRAM /
32GB+ RAM / 1TB NVMe — or any MacBook M1+ 16GB).

Step-by-step (repeatable on ANY laptop):

  1. Backend install — from repo root `backend/`:
     ```bash
     py -3.12 -m venv .venv
     .\.venv\Scripts\activate        (Windows)
     source .venv/bin/activate       (mac / Linux)
     pip install --upgrade pip
     pip install -e ".[dev]"
     # Verify: 256 / 256 green:
     pytest tests/unit -q
     ```
  2. Local LLM install — download Ollama (https://ollama.com/, 100MB install).
     Pull code models (one-time download, ~4-6 GB each depending on quant):
     ```bash
     ollama pull qwen2.5-coder:7b-instruct-q4_K_M     # 4.7GB · 20-40 t/s RTX
     ollama pull qwen2.5-coder:3b-instruct-q4_K_M      # 2.2GB · fast mode, 40-60 t/s
     ollama pull deepseek-coder-v2:16b-lite-instruct-q4_K_M  # 9.4GB · top-tier
     ollama serve                                      # runs on http://localhost:11434
     ```
  3. Backend `.env.local` laptop template:
     ```dotenv
     # backend/.env.local
     APP_NAME=Noesis
     LLM_PROVIDER=ollama
     OLLAMA_BASE_URL=http://localhost:11434/v1
     OLLAMA_MODEL=qwen2.5-coder:7b-instruct-q4_K_M
     DATABASE_URL=sqlite+aiosqlite:///./data/noesis.db
     QDRANT_URL=http://localhost:6333
     QDRANT_COLLECTION_PREFIX=noesis
     REDIS_URL=redis://localhost:6379/0
     SECRET_KEY=noesis-dev-change-me-before-production-please
     ```
  4. Frontend install:
     ```bash
     cd frontend
     # Use bundled .node/npm if global Node isn't available:
     set PATH=%CD%\.node;%PATH%   (Win cmd)
     export PATH="$PWD/.node:$PATH"  (mac / bash)
     npm install
     cp .env.example .env.local
     # Edit .env.local: NEXT_PUBLIC_API_BASE_URL="http://localhost:8000"
     npm run dev       # => Next.js :3000
     ```
  5. Laptop single-command stack (Qdrant+Redis) — start Docker Desktop, then:
     ```bash
     docker compose -f docker-compose.laptop.yml up -d
     # => qdrant on 6333, redis on 6379, noesis backend on 8000 all together
     ```

Expected laptop performance (RTX 4070 8GB, typical dev laptop):

  Qwen2.5-Coder-7B-Q4  32-38 t/s  (prefill 90 tok/s)
  Qwen2.5-Coder-3B-Q4  60-72 t/s
  DeepSeek 16B-lite    18-22 t/s  (needs 10GB+ VRAM)

MacBook M3 Pro 18GB:
  Qwen2.5-Coder-7B-Q4  24-28 t/s  (Apple Metal engine native)

================================================================================
2.  18-WEEK LAPTOP-FIRST EXECUTION ROADMAP
================================================================================
Legend: 🔴 KERNEL + SYSTEMS   🟣 FRONTEND STUDIO   🟢 PAPER + THESIS + BENCH

WEEK  | DATES    | 🔴 KERNEL + SYSTEMS                            | 🟣 FRONTEND STUDIO                                       | 🟢 PAPER + THESIS + BENCHMARKS                              | GATED MILESTONE
------|----------|------------------------------------------------|----------------------------------------------------------|-------------------------------------------------------------|-------------------
W1    | Sep 7–13 | 1.1 Relax pyproject Python >=3.10 (Hatch config). 1.2 Add OllamaProvider smoke test; create `.env.local.example` + `docker-compose.laptop.yml`. 1.3 Add `noesis run --seed 42 --deterministic` CLI flags. 1.4 Run 256/256 pytest + ruff + format — all green. | 2.1 `npm i @tanstack/react-query @tanstack/react-query-devtools sonner`. 2.2 Create `providers/app-router.tsx` QueryProvider wrapper in Next app/layout. 2.3 Rewire `app/page.tsx` Dashboard from buildMock* → live `fetchObservability()` via React Query. 2.4 Add `sonner` toasts on HttpError 401/403 (typed messages). 2.5 Run `npm test` Vitest + lint + typecheck. | 3.1 Submit university synopsis portal. 3.2 Title: "Noesis: An Operating System Kernel for Autonomous Multi-Agent Intelligence". 3.3 Register paper title + authorship (guide as co-author) in CODS-COMAD draft system. 3.4 Create `docs/thesis/` + `docs/paper/` git directories. | MS1: SYNOPSIS + LAPTOP STACK GREEN
W2    | Sep 14–20 | 1.5 CapabilityKernel audit — script `scripts/audit_mac_spawn.py` runs 4 viva deny scenarios in one shot (0 caps, JWT tamper, empty token tool, tampered token). 1.6 Determinism audit: `scripts/audit_determinism.py` (`--runs 100 --seed 42`) runs 100 consecutive `POST /v1/runs/execute`, collects report JSON SHA-256 → `docs/artifacts/determinism_manifest_100runs.json`. 1.7 Publish manifest. | 2.6 Rewire Conversations page (`app/conversations/page.tsx`) → live GET list + post Message form. 2.7 Rewire Memory page + Explorer (T1–T6 chips) → live `listMemory()` + GET tier summary. 2.8 Rewire Documents RAG Library → `POST /v1/documents/upload` + table. 2.9 Rewire Agent workbench → `POST /v1/runs/execute` streaming + node statuses (PENDING/RUNNING/SUCCESS/FAIL). | 3.5 Thesis Ch.1 Introduction (8-10 p, Times 12pt, 1.5 line, IEEE refs). 3.6 Ch.2 Problem Statement + 4-gap table (6-8 p). 3.7 Send Ch.1-2 for guide feedback. 3.8 CODS-COMAD: draft Abstract + §1 Introduction. | MS2: 100-RUN DETERMINISM AUDIT PASSED (0 variance)
W3    | Sep 21–27 | 1.8 Add 6-tier memory promotion controller tests (scripts/test_tier_promotion.py): 1000 working-memory insert → verify promotion to T2 T3 with provenance SHA-256. 1.9 Add TTL tests for T4→T5 strategic tier. 1.10 Wire MemoryAgent to promotion controller in `noesis/agents/core.py`. 1.11 pytest — 256 → 260+ green (4 new tests). | 2.10 Rewire Timeline drill-down → live `listTraces()` + ExecutionPlan waterfalls. 2.11 Rewire Metrics page → 12-tile Recharts dashboard (use `ObservabilitySummarySchema` 7-day buckets). 2.12 Rewire Settings page: LLM provider picker (Ollama default), API key masked input, theme toggle cookie, RBAC role picker stubs. 2.13 Add OpenAPI iframe `/settings/openapi`. | 3.9 Thesis Ch.3 Literature Survey + 4-col comparison table (12-15 p, 10+ refs, IEEE). 3.10 Paper draft §2 Related Work comparison table + 6 cites. 3.11 Start thesis Ch.4 Design Principles (6 maxims from plan). | MS3: 6-TIER PROMOTION CONTROLLER + FRONTEND 8-PAGE LIVE WIRE
W4    | Sep 28–Oct4 | 1.12 LLM factory unified audit: scripts/audit_llm_providers.py → smoke-test 4 providers (OpenAI/Ollama/OpenRouter/LlamaCpp) with single prompt → all return structured JSON with schema-valid answers. Add fallback provider selection. 1.13 Add `LLM_FALLBACK_PROVIDER` env var. 1.14 Add `/llm/benchmark` endpoint (prompt-tokens/sec, first-token-latency). | 2.14 `npm run build` → `.next/standalone` production build + test `start`. Fix any hydration errors. 2.15 Add Playwright E2E skeleton: `frontend/tests/e2e/setup.ts` + 3 tests: 01_conversation_smoke.spec.ts 02_memory_explorer.spec.ts 03_agent_workbench.spec.ts. 2.16 Accessibility audit: axe-core axe-core-npm dev dependency + `axe-core/playwright` → run against /dashboard → 0 critical / <5 minor violations required. | 3.12 Thesis Ch.4 Design Principles + 5 layered kernel architecture TikZ diagram. 3.13 Thesis Ch.5 Implementation Details (18–22 p, 2 figures: kernel architecture + agent roster table). 3.14 Paper draft: §3 Kernel Architecture + Fig1 diagram. | MS4: LLM FACTORY UNIFIED + FRONTEND PRODUCTION BUILD
W5    | Oct 5–11  | 1.15 Release candidate RC1 package: `hatch build` → dist/noesis-0.1.0rc1.tar.gz + wheel. 1.16 Smoke `pip install dist/*.whl` into fresh venv → import noesis → run `pytest` 256/256 in fresh env. 1.17 PyPI Test upload `twine upload -r testpypi dist/*`. 1.18 Publish GitHub release `v0.1.0-rc1` (pre-release tag) + 4 audit artifacts (MAC manifest, determinism manifest, tier-promotion manifest, provider-manifest). | 2.17 `/onboarding` 4-step wizard: Step1 connect LLM (Ollama auto-detect on :11434) → Step2 upload first doc → Step3 run first agent → Step4 invite teammate. 2.18 Empty-state shimmer skeletons (8 pages, 18 skeletons total) + loading spinners during Suspense. 2.19 RTL layout + i18n strings (English only; future Hindi extensibility). | 3.15 Paper draft §4 Three Contributions (C1/C2/C3 + figure 2 memory pyramid). 3.16 Thesis Ch.6: Capability Model + AND-Mask Spawn Minting formalization (6–8p, diagram). 3.17 Start paper §5 Methodology. | MS5: PYPI TEST INSTALL WORKS → pip install -i test.pypi noesis ✅
W6    | Oct 12–18 | 1.19 E2E kernel: scripts/run_full_seeded_pipeline.py (`--goal "Build a Rust CLI todo list"`) → end-to-end 12-agent execution. 1.20 Capture outputs to `docs/artifacts/sample_pipeline_rustcli.md`. 1.21 Add Executor Kriyakarī tri-state decision {signoff / reject / replan} unit tests for replan loop: bad plan → reject → replan → signoff (3 loops). 1.22 pytest add 4 tests → 264 green. | 2.20 Final Viva Demo Mode: add `?demo=true` URL param that seeds conversation + pipeline so viva panel sees a deterministic pre-built workflow on page load. 2.21 Studio polish: Sanskrit codename badges on Workbench node labels, KPI tiles accent icons, purple brand gradient tooltips. 2.22 Copy to clipboard buttons on all code/pre blocks. | 3.18 Thesis Ch.7 Preliminary Benchmark Setup (describe 4 benchmarks, install scripts). 3.19 Thesis Appendix A: LAPTOP ENVIRONMENT SETUP 1-pg cheat sheet. 3.20 Full thesis draft v0.1 (Chapters 1-7) shared with guide. | MS6: 12-AGENT FULL PIPELINE REPLAN LOOP ✅
W7    | Oct 19–25 | BENCHMARKS WEEK — Kernel. 1.23 Install `huggingface-hub[cli]` → `hf download openai/openai_humaneval`. 1.24 Create `benchmarks/humaneval/` harness. 1.25 Baseline runs: standalone qwen2.5-coder:7b 1-problem pass@1. 1.26 Full-Noesis pipeline runs: `noesis bench humaneval --subset 164 --llm qwen2.5-coder:7b --mode full_pipeline`. 1.27 Same harness for MBPP (1000 problems, Austin 2021). 1.28 Collect CSV raw outputs → `docs/benchmarks/raw/`. | 2.23 Add /benchmarks results hub page (React app hidden route `app/benchmarks` — internal, read-only for viva panel) that reads from published CSV → renders Recharts pass-rate per-benchmark bar charts. 2.24 Finalize Playwright E2E suite: 15 tests across 5 pages. Capture video of runs on failure. | 3.21 Paper §6 Evaluation setup: 4 benchmarks, 2 baselines, statistical test (McNemar). 3.22 Collect 95% bootstrap CIs on W7 baseline numbers. 3.23 Guide approval on Ch.1-7 draft + corrections list. | MS7: BENCH BASELINE + HUMANEVEL 164 RUNS COMPLETE
W8    | Oct 26–Nov1 | BENCHMARKS WEEK 2. 1.29 Full-Noesis vs standalone pipeline on HumanEval. 1.30 Full-Noesis vs standalone on MBPP. 1.31 Add SWE-bench-Lite harness: `pip install swebench` → run on subset 30 PRs first. 1.32 SWE-bench 300 full runs (overnight batch on laptop). Use Windows Subsystem for Linux if needed. | 2.25 Lighthouse audit — 8 pages. Performance ≥85, Accessibility ≥90, Best Practices ≥90, SEO ≥80. 2.26 Accessibility — tab-through entire Studio app without mouse (100% keyboard navigable). 2.27 Screen-reader (NVDA on Windows / VoiceOver macOS) sanity pass of 3 main pages. | 3.24 Paper §6 Results: 4 tables with +X% improvements, p-value McNemar significance bars. 3.25 Paper draft v0.9 full 6-page first draft (Title/Abstract/1-8 + Refs). 3.26 Thesis Ch.7 Evaluation Results full chapter rewrite with W8 numbers. | MS8: HUMANEVAL PASS@1 ≥ +8%, MBPP ≥ +12% (distinction bar)
W9    | Nov 2–8   | BENCHMARKS WEEK 3. 1.33 ★ Noesis Self-Host 10-PR benchmark: curated 10 small feature requests on Noesis repo itself. 1.34 Score each PR: `pytest tests/unit + ruff` → both green = success. 1.35 Script `scripts/audit_selfhost.py` → runs all 10 end-to-end. 1.36 Statistical analysis module → p-values, effect sizes, 95% CIs. 1.37 Publish to `docs/benchmarks/results/` (4 tables). 1.38 Add McNemar test script `scripts/stats_mcnemar.py`. | 2.28 Deploy Studio to Vercel Hobby: `vercel link && vercel deploy --prod`. Add deploy hook to GitHub Actions frontend CI. 2.29 Custom domain option: point studio.noesis.dev (buy if desired) or just use `noesis-<your-handle>.vercel.app`. | 3.27 Address guide feedback → thesis v0.2 fully corrected, 60 page length hit, IEEE format lock. 3.28 CODS-COMAD Paper Final polish: 6p + 8 refs + 4 figs + 4 tables. 3.29 Generate ACM PDF with Acmart + BibTeX. | MS9: NOESIS SELF-HOST BENCH ≥ 5/10 PRs GREEN (distinction target)
W10   | Nov 9–15  | 1.39 Final Noesis package RC2. PyPI upload → `pip install noesis == 1.0.0rc2`. 1.40 `twine check dist/*` + `hatch build` idempotent. 1.41 Push Docker image to `ghcr.io/dhruvshah11/noesis:v1.0.0-rc2`. 1.42 SBOM generation with `syft packages` → SPDX 2.3 JSON. 1.43 Trivy container image scan — 0 HIGH/CRITICAL. | 2.30 Deploy backend to Render/Hetzner/Fly.io free tier (tiny VM). 2.31 Frontend CI in `.github/workflows/frontend-ci.yml`: lint + typecheck + vitest + playwright + lighthouse. Add to repo. 2.32 Final Marp PPT export to pptx, animations applied. | 3.30 CODS-COMAD PAPER SUBMISSION DEADLINE (typical ~mid-Nov). Submit final PDF + authorship + copyright form. 3.31 Simultaneously upload arXiv:cs.AI preprint with DOI-reserved citation ID. 3.32 Thesis Ch.8 Future Work + Appendix B Benchmark raw data tables + provenance. | MS10: PAPER SUBMITTED ✦ THESIS DRAFT V0.3 COMPLETE
W11   | Nov 16–22 | 1.44 GitHub Release v1.0.0 RC3 tags + Release Notes. 1.45 Release Changelog: CHANGELOG.md auto-generated from conventional commits. 1.46 Add 4 demo YouTube links (14-min walkthrough, 3-min trailer, 2-min MAC demo, 2-min Determinism demo) to release notes. Upload videos to unlisted YouTube. 1.47 Full regression on 3 platforms: Win x64 / mac arm64 / Linux arm64 (use VMs/CI) → all 264+ tests green. | 2.33 Finalize Studio polish: `/help` overlay, keyboard shortcuts legend, dark/light + high-contrast themes. 2.34 Finalize PPT appendix slide deck (extra failure-case tables + cost breakdowns). 2.35 Export PPT with embedded video clips + speaker notes. | 3.33 Address any guide-requested final edits on final thesis draft v0.4. 3.34 Turnitin plagiarism check: <10% similarity, zero uncited copy-paste. 3.34 Format pass: Times 12pt, 1.5 line, 1-inch margins all around, IEEE references style. | MS11: RC3 FULL 3-PLATFORM REGRESSION + THESIS V0.4 FORMAT-LOCKED
W12   | Nov 23–29 | 1.48 Final kernel bug-fix only. Triage regressions from W11. 1.49 Final `noesis --version` CLI prints exact git SHA from hatch-vcs. 1.50 Stable logo brand (SVG) → `docs/brand/` published. | 2.36 Final UI screenshots (36) for thesis chapter figures (hi-res 2x PNG). 2.37 Print-friendly `app/?demo=true` no-scroll layout for screenshot capture. 2.38 Final E2E run video capture (14-min file) + 30s trailer cut for viva. | 3.35 FINAL THESIS 60-PAGE SUBMISSION to university portal. Signed declaration + plagiarism report + guide co-approval form uploaded. 3.36 Physical spiral-bound printing (2 copies: submission + personal). | MS12: UNIVERSITY FINAL THESIS SUBMITTED
W13   | Nov 30–Dec6 | 1.51 (Optional, based on CODS-COMAD reviews) Camera-ready paper revision: address reviewer comments, update refs, submit CR + bib. 1.52 arXiv paper v2 updated with reviewer changes if any. | 2.39 Final accessibility Lighthouse pass on deployed studio.noesis.* (≥90 a11y). 2.40 Final Studio demo video: 14-min professionally captioned (auto-captions edited). | 3.37 Dry-run viva #1: present to family/friends/colleagues for flow + timing (14 min exactly). 3.38 Record dry run on phone → watch back; cut 10% of words. Cut slides if timing is over. Fix body language + Q&A prep. | MS13: DRY VIVA #1 ≤14:00 RUNTIME
W14   | Dec 7–13  | 1.53 🏷️ GitHub Release `v1.0.0` — STABLE, non-RC. 1.54 PyPI stable release `noesis 1.0.0`. 1.55 Docker image `:v1.0.0` stable. 1.56 SBOM + license compliance report published. 1.57 Laptop demo scripts laminated cheat sheets printed. | 2.41 Vercel + backend deploy promoted to "stable" channel. 2.42 Final PPT: animations, Sanskrit cell icons (Canva Hindu Spiritual pack), embedded video links, appendix slides. Export 2x: with-build + without-build versions. 2.43 USB × 2 digital copies uploaded (thesis, PPT, videos, data). | 3.39 Dry-run viva #2 with guide + any available committee member. 3.40 Fix feedback. 3.41 Q&A practice list: 50 most-asked capstone questions + scripted answers (ELEVATOR PITCH memorized). | MS14: GITHUB + PYPI v1.0.0 STABLE RELEASE
W15   | Dec 14–20 | 1.58 Final pre-viva hardware setup checklist: laptop on UPS, Docker Desktop + Ollama + noesis running 30 min before VIVA. 1.59 Run all 4 viva demo scripts back-to-back 3x → 100% success. 1.60 Demo server running on `http://localhost:3000/?demo=true` + `http://localhost:8000/docs` preloaded in Chrome tabs. | 2.44 Studio `/demo=true` page auto-run agent workflow at page load (no clicks required). 2.45 Project logo sticker printing (optional). | 3.42 Final thesis plagiarism + format re-check. 3.43 Viva cue cards (12-point Times) printed for 4 live demos. 3.44 Committee meeting scheduled, room + projector confirmed. | MS15: PRE-VIVA LAPTOP STABLE, NO REBOOTS NEEDED DURING VIVA
W16   | Dec 21–27 | 🔶 (OPTIONAL HARDWARE SPRINT — NON-BLOCKING, JETSON NOW) 1.61 Jetson Orin Nano 8GB procurement + JetPack 6.2 flash. 1.62 Run `scripts/bootstrap_jetson.sh` → 256/256 pytest green + Qwen2.5-Coder-7B 10-14 t/s. 1.63 Optional: Jetson as "physical viva demo appliance" (plug into projector). 1.64 NOT required for thesis/paper. | 2.46 Winter break only: prepare optional 4-slide appendix deck Jetson deployment case-study + on-device privacy/on-prem TCO table. | 3.45 Winter break — rest. Read any CODS-COMAD first-look reviews if back. 3.46 If rejected from primary conference → submit arXiv v2 + resubmit to ICAC3 2027 fallback by Jan 3. | MS16: JETSON OPTIONAL HARDWARE DEMO (NON-BLOCKING)
W17   | Dec 28–Jan3 | 1.65 Kernel freeze. Only security patches if any upstream deps flagged by dependabot. 1.66 Final paper camera-ready (if accepted) — 1 round final edits + ACM author agreement. | 2.47 Studio stable. No new features — only bug triage if viva panel found anything during dry-run. 2.48 Demo page auto-scrolls through workflow + plays embedded audio narration (optional). | 3.47 Revisit 50 Qs + answers, refine. 3.48 CODS-COMAD Camera Ready Final if accept notification out. 3.49 ICAC3 2027 fallback submission if needed. | MS17: KERNEL + STUDIO CODE FREEZE
W18   | Jan 4–10 | ✅ VIVA WEEK. 1.67 Boot everything 30 min early. 1.68 Run 4 viva demo scripts once in warm-up. 1.69 Deliver presentation (14 min) → Q&A. | ✅ VIVA WEEK. Studio up on big projector, viva demo mode active. | 3.50 VIVA + GRADES. After viva → upload thesis final to arXiv (Educational). 3.51 Final GitHub repo archived if desired. Celebrate 🧠✨. | 🚀 SHIP COMPLETE
================================================================================
3.  FINANCIAL COST PROJECTION (LAPTOP-FIRST MODE — ZERO TOKEN FEES FOREVER)
================================================================================

| Item | Cost | One-time or Recurring? |
|:-:|:---|:---:|
| Dhruv's laptop | Already owned → $0 | N/A |
| Ollama + qwen2.5-coder + deepseek-coder-v2 models (Hugging Face download) | $0, Apache 2.0/RAIL-M licensed commercial use | N/A |
| Electricity for 18 weeks × 6 hrs/day × 65W laptop avg load × $0.14/kWh | $6.87 TOTAL for 18 weeks | $7 one-time energy cost |
| Docker Desktop (personal / student license) | $0 | N/A |
| Vercel Hobby frontend deploy | $0 | N/A |
| GitHub Pro Student Pack (free with edu email) | $0 | N/A |
| PyPI publishing + TestPyPI | $0 | N/A |
| University synopsis/thesis admin fees (if any) | Dept-dependent, typically $0 | N/A |
| Conference registration + travel (CODS-COMAD 2027 at IIT Bombay — STUDENT RATES) | ₹2,500 – ₹4,000 registration + travel | $30–$50 if accepted |
| OPTIONAL — Jetson Orin Nano 8GB dev kit (W16 showcase only) | $139 Dev Kit + $70 1TB NVMe = $209 | One-time, NON-BLOCKING |
| OPTIONAL — Custom domain studio.noesis.dev / noesis.dev | $15/yr if bought | ~$1.25/month optional |

--------------------------------------------------------------------
18-WEEK LAPTOP-FIRST PROJECT TOTAL ALL-IN COST →  $7 – $57 💸💸💸
--------------------------------------------------------------------
(Only if you go conference + domain. $7 pure electricity otherwise. No token bills ever.)

================================================================================
4.  6-PAGE RESEARCH PAPER SPECIFICATION (ACM SIGCONF 2-col)
================================================================================

Target Venues:
  A) CODS-COMAD 2027 (primary, Jan 2027, IIT-B, Scopus-indexed, Indian-friendly,
     travel grants for student authors, deadline mid-Nov 2026 abstract/full)
  B) ICAC3 2027 (fallback, tier-1 Scopus, Dec 2026 abstract / Jan 2027 conf)
  C) arXiv:cs.AI preprint always (W10 same day as paper submission).

Title:
  Noesis: A Kernel Architecture for Deterministic, Secure, Memory-Hierarchical
  Multi-Agent Autonomy

Authors:
  Dhruv Shah  (Student, University _______________)
  Prof. _______________  (Guide, co-author, corresponding author)
  (optional third author if needed — Jetson hardware mentor)

6-PAGE 2-COL ACM SIGCONF TEMPLATE WORD BUDGET:

  PAGE 1
    Abstract (250 words)
    1. Introduction (650 words)
      • Gap paragraph (LangChain 4 failures)
      • 3 Contributions (C1/C2/C3) as bold bullet list
      • Evaluation summary (+X% HumanEval, +Y% MBPP)
      • Outline of rest

  PAGE 2
    2. Related Work (650 words)
      • 4-col comparison table: Framework / Memory Hierarchy / Capability Spawn MAC /
        Deterministic Kernel / Open-Source (HumanEval benchmark row / LangChain /
        AutoGen / CrewAI / SWE-bench baselines / Noesis)
      • 8 cites [1-8] + 2 optional citations (Miller Capability Myths, Unix TSS)

  PAGE 3
    3. Noesis Kernel Architecture (700 words)
      • 3.1 Layered Overview
      • 3.2 Typed 12-Agent Roster (Sanskrit codenames + roles table)
      • 3.3 CapabilityKernel AND-Mask Spawn Minting
      • Figure 1 (1-col): Layered Kernel Architecture diagram (from PPT Slide 8)

  PAGE 4
    4. Three Core Contributions (700 words)
      • 4.1 C1: Six-Tier Νόησις Memory Model
      • 4.2 C2: Capability-Gated AND-Mask Spawning
      • 4.3 C3: Deterministic Seeded 12-Agent Orchestration
      • Figure 2 (1-col): Memory Tier Pyramid (T1→T6 Sanskrit labels)

  PAGE 5
    5. Methodology (300 words)
    6. Evaluation (500 words)
      • Track T1 Systems Correctness (264/264 tests green)
      • Track T2 Benchmark Performance (4 tables: HumanEval, MBPP, SWE-bench-Lite,
        ★ Noesis Self-Host)
      • McNemar p-values, bootstrap 95% CIs on +8% / +12% gaps
      • Table 2 HumanEval Pass@1: Baseline (7B) | Full Noesis (7B) | delta
      • Table 3 MBPP Pass@1: same structure
      • Table 4 SWE-bench-Lite resolved-rate (300 PRs subset)
      • Table 5 Self-Host 10 PR resolved (count green)
      • Figure 3 (1-col): Determinism histogram (100-runs variance = 0)

  PAGE 6
    7. Threats to Validity (250 words)
    8. Future Work + Roadmap (200 words)
    References (800 words · ACM numeric [1] style · 12–16 entries)
  APPENDIX (SUPPLEMENTARY PDF, NOT COUNTED IN 6-PAGE LIMIT)
    Appendix A. Jetson Orin Nano 1-yr on-device TCO table ($257 TCO vs cloud).
    Appendix B. 100-Consecutive Run Determinism manifest (5 lines sample).
    Appendix C. Sanskrit → English Agent Codename Glossary (12-entry table).
    Appendix D. Reproducibility — GitHub Commit SHA + pip freeze output.

Statistical Significance (REQUIRED FOR ACCEPTANCE):
  Use `statsmodels.stats.contingency_tables.mcnemar(exact=True)` for each
  benchmark to test pairwise significance of Noesis-vs-baseline on a
  problem-by-problem 2×2 table (both correct / only baseline / only Noesis /
  neither). Any +8% delta without p < 0.05 → call out limitation honestly.

================================================================================
5.  LAPTOP WEEK 1 — ACTION ITEMS — DO TODAY (non-negotiable)
================================================================================

  1. Install Ollama for Windows/macOS → `ollama pull qwen2.5-coder:7b-instruct-q4_K_M`
     (40-min download, do it in background while Week 1 code work happens).
  2. Submit university synopsis portal RIGHT NOW. Use title from §0.
  3. Send plan to project guide for approval. Mark title page with date.
  4. Open `backend/.env.example` → create `backend/.env.local` with Ollama
     defaults from §1.
  5. Start backend + frontend to verify laptop stack works:
     ```bash
     # Terminal 1
     cd backend && .\.venv\Scripts\activate && uvicorn noesis.api.main:app --host 127.0.0.1 --port 8000 --reload
     # Terminal 2
     cd frontend && set PATH=%CD%\.node;%PATH% && npm run dev
     # Browser
     start http://localhost:3000/?demo=true
     ```
  6. Call me (type "start week 1 code now") → I'll execute all W1 tasks in
     parallel systems+frontend as a single TodoWrite plan.

================================================================================
6.  WEEK 1 CODE SUBTASKS — BREAKDOWN (for reference — executed by next "go")
================================================================================

🟥 KERNEL & SYSTEMS (W1 — ~6 hours):
  K1. `backend/pyproject.toml` → `requires-python = ">=3.10,<3.13"`
  K2. Verify OllamaProvider is wired (it's at `noesis/llm/ollama_provider.py`).
      Add unit test `tests/unit/test_llm_provider.py::test_ollama_provider_url_parse`.
  K3. Create `backend/.env.local.example` laptop template (from §1).
  K4. Create `docker/docker-compose.laptop.yml` — single-up: backend+sqlite+qdrant+redis
      on laptop, platform=linux/amd64 + qdrant aarch64 image for Apple Silicon.
  K5. Add `noesis run --goal STR [--seed INT] [--deterministic] [--agent AGENT]`
      CLI subcommand to `backend/noesis/cli.py`.
  K6. Run 256/256 + ruff + format. Update tests count if added.

🟪 FRONTEND STUDIO (W1 — ~6 hours):
  F1. `cd frontend && npm install @tanstack/react-query @tanstack/react-query-devtools sonner`
  F2. Create `frontend/src/app/providers.tsx` (QueryClientProvider + devtools).
      Import in `app/layout.tsx` as first child.
  F3. Rewrite `app/page.tsx` Dashboard → call fetchObservability() wrapped in
      `useQuery({queryKey:['observability','3600'], queryFn: ..., refetchInterval:60000})`.
      Remove buildMock* seed imports; keep buildMock as Suspense fallback skeleton.
  F4. Add `Toaster` from `sonner`; in `src/lib/api/http.ts`, on HttpError
      status 401/403, `toast.error("Session expired (401): …")` typed messages.
  F5. Run `npm run lint` → `npm run typecheck` → `npm test` Vitest.
  F6. Git commit to new branch `chore/week1-laptop-only`.

🟩 THESIS + PAPER (W1 — ~4 hrs, done by Dhruv; no code needed):
  T1. Fill university synopsis form (1hr).
  T2. Email guide for synopsis approval with plan + title (30 mins).
  T3. Register paper title in CODS-COMAD (if portal open).
  T4. Create `docs/thesis/` + `docs/paper/` folders in repo; add empty
      `docs/thesis/chapters/01_intro.md` etc scaffolding files.

================================================================================
END OF LAPTOP-FIRST SHIP PLAN v1.1
================================================================================
