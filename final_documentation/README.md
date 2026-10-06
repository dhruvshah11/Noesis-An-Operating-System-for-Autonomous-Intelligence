# NOESIS — Final Documentation Package (6 October 2026)

| Deliverable | Files | Size |
|---|---|---|
| Software Requirements Specification v1.0 | `NOESIS_SRS_v1.0.docx` / `.pdf` | 157 pages, 21 chapters + appendices A–G, 65 FRs, 33 NFRs, 18 use cases, 42 API operations, RTM |
| Major Project Report (thesis) | `NOESIS_Thesis_Major_Project_Report.docx` / `.pdf` | 74 pages, 9 chapters + appendices A–G |
| End-term presentation (UPES template) | `NOESIS_Final_Project_Presentation.pptx` / `.pdf` | 28 slides with speaker notes |
| Figures | `figures/` | 32 diagrams + 14 charts from measured data (PNG, 230 dpi) |
| Screenshots | `screenshots/` | 13 dashboard routes + Swagger UI, from the running app |
| Evidence | `evidence/` | OpenAPI dump, pytest/JUnit/coverage, Vitest/ESLint output, API scenarios, measurements, collection scripts |

## How the content was produced
- **Read-only audit.** Nothing in the repository was modified. Tests, servers and measurements ran on copies in a temporary directory with their own SQLite databases. Your servers on ports 3000/8000 were not touched.
- **Evidence labels.** Every number is labelled *measured* (this audit), *derived* (computed from code constants) or *reported* (re-analysed from `docs/eval`).
- **Environment.** Windows 11, Python 3.13.2, Node 20.18.1, Ollama with `qwen2.5-coder:7b-instruct-q4_K_M`.

## Key measured results
- Backend: 310 passed, 2 xfail, 0 failed (312 tests); 70.01 % line coverage.
- Frontend: Vitest 103/105 (the 2 failures follow the uncommitted `http.ts` change); `tsc` 0 errors; ESLint 0/0.
- Planner: 50/50 SE-50 goals bit-identical over 3 runs; median 1.05 ms per plan.
- Capability gate: all denial scenarios rejected with specific codes. Resource routes are unauthenticated.
- Local LLM: about 23 completion tokens/s. A 5-step run takes 60.4 s with the LLM and 1.96 s without (median of 10; most of that 1.96 s is the Windows health-probe timeout, not the run itself).

## Please confirm before submission
1. **Department line** on the title pages ("Department of Informatics", taken from your earlier SRS). Confirm it applies to both authors.
2. **Certificate signatories** (guide / head of department) and the blank revision-history table.
3. **Reference metadata.** Page numbers and DOIs were compiled carefully but should be checked against the publishers' records.
4. **When you open the `.docx` files in Word**, accept "Update fields" if prompted. The PDFs already contain the final page numbers.

## Important differences from the project README
SRS Appendix F lists every README claim that the code does not support. Examples: test counts, route names, comparative GPT-4o/Claude/Gemini benchmark figures, LangGraph orchestration, BCa intervals, memory-tier names and backends, and the Jetson deployment. The new documents follow the code.
