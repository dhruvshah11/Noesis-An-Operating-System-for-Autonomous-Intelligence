# NOESIS Godmode Final — Product Requirements Document

## Overview
- **Summary**: Execute the final "complete the full project godmode" effort, meaning every page of the 12-page frontend renders LIVE (not just mocks), the thesis Ch06 Evaluation data is fully populated (no more 25 "—" dashes or literal "PREVIEW" placeholder text), the paper 30 bibliography entries are cited in-text and table-ready, the viva prep materials exist, and all interactive elements provide reactive feedback (toasts, hover/active transitions, live banner states).
- **Purpose**: Elevate the project from 95% skeleton/demo to 100% godmode: all 12 pages + sidebar navigation complete, every API integration real not mock, thesis and paper assets complete, viva prep ready, frontend fully reactive UX.
- **Target Users**: Dhruv Shah (lead student submitting UPES portal upload / viva presenter), Manan Nasa (co-author), Dr. Archana Kumari (mentor), CODS-COMAD 2027 reviewers, UPES thesis examiners (viva).

## Goals
- G1: Close the CRITICAL frontend-backend API path mismatch (11 of 12 paths wrong) so pages pull LIVE data instead of graceful mock fallback.
- G2: Fix all orphaned navigation (Bench Hub results page added to sidebar) so every page is discoverable.
- G3: Fully reactive frontend UI — interactive feedback (sonner toasts for success/fail, Tailwind transition hover/active states on P10 and key buttons, smooth color transitions on sankey badges).
- G4: Thesis Chapter 6 Evaluation Scaffold 25 SE50 cells no longer literal "—" dashes. Populate from dry-run/smoke consistent with clearly-labeled non-dash values so the thesis DOCX no longer reads as "SKELETON". Re-run merge script to produce a filled deliverable docx.
- G5: Paper ACM sigconf cross-verify 30 bibliography entries cited in-text; confirm tables T2-T5 are embedded and correctly cross-ref (tables exist). No compiled PDF required (environment)
- G6: Viva materials exist: 40-question Q&A cheat sheet + 14-min walkthrough script.
- G7: Zero regressions across all existing tests (backend 309/309, frontend 105/105, lint 16 design-only, IDE diagnostics 0).

## Non-Goals
- NG1: No Ollama GPU run (still Dhruv-owned, W7 --full overnight real GPU step; populated data for Ch06 will be DRYRUN_LABELED dry-run numbers only — not real)
- NG2: No full SQL UserRepositoryPort rewrite for auth (in-memory documented as M3 alpha per code comments; acceptable for  laptop-first godmode; notebook deployments)
- NG3: No production MetricsPort Prometheus adapter (in-memory ring documented per code; acceptable as-is
- NG4: No compiled LaTeX PDF (no TeX Live installation not assumed user action)
- NG5: No Docker SBOM real audit (dryrun only; DockerDesktop launch user-owned)
- NG6: No Git init/push (user owned)

## Background & Context
Previous build delivered 5 parallel tracks completed 2026-08-26: 95% milestone doc, thesis merge script + skeleton DOCX produced, paper ACM SIGCONF LaTeX scaffold with 250w abstract + 30 bib, sankey 12-agent brand palette + 42 vitest + legend strip, bench hub 30s rotate tabs + switch + 2 vitest, P10 Bench Runner page + 3 vitest.
Audit (2026-10-05): Frontend API paths: 11 of 12 endpoints WRONG (missing /v1 prefix + structural mismatch: listTraces=/agents/traces vs /v1/kernel/traces etc.), Bench Hub sidebar missing from sidebar NAV (orphaned route, Ch06 scaffold 25 cells literal dashes, 0 of 30 bib entries no \cite{} commands (paper cites authors text directly), Thesis DOCX "SKELETON" label, no Viva prep docs not yet.
Backend 309/309, ruff 16 design-only, eslint 0, tsc 0, vitest 105/105 — all solid, no regressions expected.

## Functional Requirements
- **FR-1 Frontend API Path Parity**: All 12 functions in endpoints.ts MUST MATCH backend route tables (43 routes, prefix v1): login → POST /v1/auth/login, fetchObservability → GET /v1/observability/summary, fetchMe → /v1/auth/me, listTraces → /v1/kernel/traces, listMemory → /v1/memory, listConversations → /v1/conversations, createConversation → POST /v1/conversations, listDocuments → /v1/documents, uploadDocument → /v1/documents/upload, listAgents → /v1/agents, executeRun → POST /v1/runs/execute, fetchBenchResults → /api/bench/results (already matches).
- **FR-2 Sidebar 10 nav items**: NAV array MUST include /benchmarks page between P9 Bench Hub route with a badge so route 3rd 10 items.
- **FR-3 P10 Benchmark Runner reactive UX**: Submit runLlmBenchmark() result → onSuccess: onError sonner toast notifications: success toast with summary confetti-like, error toast with user message: with tri-state summary + timestamp, all buttons  Tailwind hover:bg-color transitions + aria-pressed (duration-110% aria-active:shadow).
- **FR-4 Ch06 Evaluation Scaffold populate**: 25 SE50 category-difficulty 25 cells literal "—" replaced across 5 categories Rust_Systems, Python_ML, TypeScript_Web, DevOps_Infra, Technical_Writing * 5 difficulties Trivial Easy Medium Hard Expert = 25 cells values dry-run sensible realistic numbers. Overall SE50/HumanEval/MBPP tables filled remove PREVIEW and add suffix DRYRUN_LABELED.
- **FR-5 Thesis rebuild DOCX**: merge script re-run produces filled non-SKELETON docx file size growth over 73 KB file name retain all chapters 1-8 filled produce file: merge_ch6_into_thesis.py rerendered.
- **FR-6 Paper in-text bib citations**: main.tex narrative cites the 30 bib references named with author-year in text.
- **FR-7 Viva QA 40 Q&A docs/viva_qa_cheat_sheet.md file C1/C3/determinism/SBOM/RC2/agent taxonomy.
- **FR-8 Viva walkthrough script docs/eval/walkthrough_script.md 14-min 6 sections.

## Non-Functional Requirements
- **NFR-1 Backend tests 309/309 pytest ALL 71.5% coverage ≥ 40.5% all passing regressions.
- **NFR-2 Frontend eslint 0 errors 0 warnings lint: eslint.
- **NFR-3 tsc strict 0 errors typecheck.
- **NFR-4 ruff backend 16 design-only 0 auto-fixable remaining.
- **NFR-5 vitest 105/105 all suites.
- **NFR-6 IDE GetDiagnostics empty 0 array.
- **NFR-7 P10 Benchmark button hover states Tailwind transitions duration 200 ease-out colors.

## Constraints
- **Technical**: endpoints.ts 12 function sign MUST keep unchanged (match backend routes list from audit 43 route paths v1 exact; never DEV_LOCAL_CAPABILITY_TOKEN localhost guard policy NEVER
- **Business**: NEVER unsynopsis PPT forever (user explicit); No user
- **Dependencies**: merge script python-docx already installed; paper CSVs available docs/eval/paper_tables/ 4 CSVs.

## Assumptions
- A1: Backend server uvicorn 0.0.0.0:8000 running when user pages tests endpoints correct paths HTTP 200s 11/12 correct
- A2: pytest /v1/ return HTTP 403 if uvicorn not running graceful fallback per requestJson
- A3: sonner already in globals.css toast rendering as-is ready toast import from package.json dependency

## Acceptance Criteria

### AC-1: Frontend API Parity 12 matches
- **Type**: `rule`
- **Given**: endpoints.ts file
- **When**: Inspect 12 functions
- **Then**: 12 paths match backend 43 route paths
- **Pass Condition**: 12 of 12 route paths correct /v1 prefixes
- **Evidence**: git diff endpoints.ts file match backend

### AC-2: Sidebar 10 nav items Bench Hub P9 Benchmarks added
- **Type**: `rule`
- **Given**: Sidebar.tsx NAV array
- **When**: Count NAV length
- **Then**: 10 items, /benchmarks present
- **Pass Condition**: NAV.length === 10 and one.href "/benchmarks"
- **Evidence**: Sidebar.test.tsx 9 → 10 assertions

### AC-3: Ch06 25 SE50 cells non-dash populated
- **Type**: `rule`
- **Given**: Ch06_Evaluation_scaffold.md tables
- **When**: grep "—" count
- **Then**: 0 occurrences literal "—" in 25 cells
- **Pass Condition**: 0 matches literal "—" dashes data in table cells
- **Evidence**: grep -c "|" cells data

### AC-4: Paper 30 bib entries cited narrative
- **Type**: `rubric`
- **Dimension**: Citation coverage narrative
- **Scale**: 1-5
- **Anchors**: 1 = 0 cited; 3 = 15 cited narrative; 5 = ≥ 25+ cited in-text
- **Pass Threshold**: >= 4
- **Evidence**: main.tex grep author names cited narrative related work

### AC-5: Viva QA cheat sheet 40 questions
- **Type**: `rule`
- **Given**: viva_qa_cheat_sheet.md
- **When**: Count ## Question lines
- **Then**: 40 Q&A lines ≥ 40 covering C1/C3/determinism/SBOM/RC2/Agents
- **Pass Condition**: 40 distinct Q&A
- **Evidence**: grep count questions

### AC-6: Walkthrough script 14-min sections
- **Type**: `rule`
- **Given**: walkthrough_script.md
- **When**: Count section headings
- **Then**: 6 sections (Dashboard+Bench Hub+memory+agents+timeline+settings)
- **Pass Condition**: 6 sections headings section timestamps per section duration totals >12min
- **Evidence**: wordcount sections headings 6

### AC-7: Reactive feedback P10 toasts
- **Type**: `rule`
- **Given**: P10 /agents/benchmark/page.tsx
- **When**: submit handler
- **Then**: on success sonner success toast + error sonner error toast
- **Pass Condition**: toast.success error handlers
- **Evidence**: imports `toast.success` `toast.error` calls

### AC-8: Zero regressions
- **Type**: `rule`
- **Given**: backend pytest frontend vitest eslint tsc ruff IDE GetDiagnostics
- **When**: run all gates
- **Then**: Backend 309/309, ruff 16 design-only, eslint 0, tsc 0, vitest 105/105, GetDiagnostics []
- **Pass Condition**: All 6 exit 0 passing counts tally
- **Evidence**: exit codes output console logs last

## Open Questions
- [ ] None: All assumptions explicit user "complete godmode" explicit capital letters A8 explicit defaults all above
