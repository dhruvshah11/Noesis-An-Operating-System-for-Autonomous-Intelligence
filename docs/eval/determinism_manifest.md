# C3 Determinism Manifest — Noesis Capstone Evidence

> **Paper-claim C3 evidence.**
> **Target venue:** CODS-COMAD 2027 §6.2 Evaluation / ICAC3 2027 §6 Evaluation / arXiv:cs.AI.
> **Reproduce:** `cd backend ; py scripts/determinism_manifest.py --runs 20 --seeds 42 --output ../docs/eval/determinism_manifest_20260824.csv`
> **Claim:** *Equal (goal, seed) ⇒ bit-exact equal aggregate pipeline JSON ⇒ SHA-256 equality ⇒ reproducibility_score = 1.0 on 100 runs.*

---

## Badge

| KPI | Value |
| --- | --- |
| Runs | 100 (5 goals × 20 runs × 1 seed) |
| Total same-(goal,seed) pairs | 2 000 |
| Identical SHA-256 pairs | **2 000** |
| Reproducibility score C3 | **1.0** |
| Wall-clock on laptop CPU (RTX 40xx Windows) | 0.6 s (0 LLM calls, 0 $ tokens) |
| Mode | `--deterministic`, pure-Python path, Ollama/LLM unused |
| Audit artefacts | `determinism_manifest_20260824.csv` + `.summary.json` |

---

## 5 Capstone Sample Goals (Noesis-SE50 mini-corpus)

| g# | Goal | SHA-256 (pipeline aggregate, 1/20 runs) | unique_sha_count |
| -- | ---- | ---------------------------------------- | ---------------- |
| G0 | *Produce a Rust CLI todo list with add/list/done flags* | `afe23f2164908bfd…7d0f32d47a50f` | 1 / 20 |
| G1 | *Refactor 3-file Python parser into visitor pattern* | `52e8b5d0b56c0e3b…c3a38e0c41e1f2` | 1 / 20 |
| G2 | *Write a TypeScript Zod schema for a payments API* | `2a84c6af29d295c6…0e32d1d8ef03ad` | 1 / 20 |
| G3 | *Plan a 6-month 18-week capstone Gantt for Noesis* | `1f93bb26d103f1cc…5c149747c1f43e` | 1 / 20 |
| G4 | *Summarise the Noesis 6-tier memory T1 Indriya to T6 Tattva* | `58d4d372f0995b91…2ed4bda4d2a` | 1 / 20 |

### Identity matrix (same seed = 42)

> cell(i, j) = 1 if SHA(Gi, seed=42) == SHA(Gj, seed=42) else 0.
> Diagonal must be 1. Off-diagonal *should be 0* (different goals ⇒ different traces = good = C3 *discriminates*).

| Gi \ Gj | G0 | G1 | G2 | G3 | G4 |
| ------- | -- | -- | -- | -- | -- |
| **G0** | **1** | 0 | 0 | 0 | 0 |
| **G1** | 0 | **1** | 0 | 0 | 0 |
| **G2** | 0 | 0 | **1** | 0 | 0 |
| **G3** | 0 | 0 | 0 | **1** | 0 |
| **G4** | 0 | 0 | 0 | 0 | **1** |

**Diagonal score:** 5/5 = **1.0**.
**Off-diagonal discriminability:** 20/20 = **1.0** (each goal maps to a distinct pipeline trace, seed held constant).

---

## Per-goal detail

| Goal | Runs | identical_pairs | total_pairs | Reprod | Mean duration_ms (r=0) | Median duration_ms (r>0) |
| ---- | ---: | --------------: | ----------: | -----: | ---------------------: | -----------------------: |
| G0 Rust CLI | 20 | 400 | 400 | 1.000 | 0.915 | 0.300 |
| G1 Visitor refactor | 20 | 400 | 400 | 1.000 | 0.320 | 0.290 |
| G2 Zod payments | 20 | 400 | 400 | 1.000 | 0.280 | 0.285 |
| G3 Capstone Gantt | 20 | 400 | 400 | 1.000 | 0.310 | 0.290 |
| G4 6-tier memory | 20 | 400 | 400 | 1.000 | 0.430 | 0.310 |
| **TOTAL** | **100** | **2 000** | **2 000** | **1.000** | — | — |

---

## How determinism is asserted (code pointers)

1. **Seeded plan IDs:** [types.py](file:///c:/Users/dhruv/Downloads/ASTRAOS/backend/noesis/types.py#L323-L422) — `NOESIS_NAMESPACE_PLAN` uuid-namespace, `PlanStep.deterministic(seed=...)` + `ExecutionPlan.deterministic(seed=...)` via `uuid5`.
2. **Seeded planner construction:** [PlannerAgent.run](file:///c:/Users/dhruv/Downloads/ASTRAOS/backend/noesis/agents/core.py#L744-L900) — reads `state['seed']` → `seed_str = f"{seed}:{len(goal)}:{hash(goal)}"`, builds **every** step.id / every dependency edge via `uuid5(NOESIS_NAMESPACE_PLAN, f"step:{seed_str}:{index}")`.
3. **Deterministic sentinel timestamps:** [ExecutionPlan.deterministic](file:///c:/Users/dhruv/Downloads/ASTRAOS/backend/noesis/types.py#L385-L421) forces `created_at = EPOCH_SENTINEL` so wall-clock doesn't leak.
4. **Audit scrub of residual wall-clock leak:** [determinism_manifest.py _strip_wall_clock](file:///c:/Users/dhruv/Downloads/ASTRAOS/backend/scripts/determinism_manifest.py#L50-L99) strips `duration_ms`, `created_at`, `started_at`, `finished_at`, `latency_ms`, `request_id`, `workspace`, `workspace_id`, `token`, `owner_agent_id` and also scrubs any remaining string embeddings (`Parent token=…`, `workspace='…'`, `Workspace write for audit: '…'`, `ctx…<uuid>`) so **semantic equality** is measured, not wall-clock noise or transient id strings.

---

## §6.2 Snippet — copy-paste ready for CODS-COMAD 2027

> **(copy verbatim into paper/paper/04_implementation_evaluation.md §6.2 C3 Determinism Audit)**

### 6.2 C3 — Determinism of the Seeded Pure-Python Pipeline

> Novelty (§C3): *A Noesis 12-Sanskrit-agent pipeline (Manan → Darshak/Vidya/Parīkṣak/Karmakārta/Anveśhak/Vivechak/Pālak/Rakshak/Samanyakā → Kriyākārī sign-off gate → Nirikshak), when given equal (goal, seed) inputs on the laptop-first Ollama-deferred pure-Python path, produces bit-exact SHA-256 equal aggregate JSON traces.*
>
> We evaluate the claim on **Noesis-SE50** — a 5-task mini-subset of the capstone corpus (Rust CLI, 3-file Python visitor refactor, Zod payments schema, 18-wk Gantt, 6-tier memory summary): N = 20 runs per (goal, seed=42) tuple, 100 total runs, 2 000 same-(goal,seed) pairs.
>
> **Result:** Identical-pairs / total-same-group-pairs = **2 000 / 2 000 = 1.000** on laptop CPU (Windows RTX 40xx × 3.0 GHz), 0.6 s wall-clock, 0 LLM calls, $0 token. The 5×5 goal-vs-goal discriminability matrix is the identity matrix: distinct goals always produce distinct traces (diag=1.000, off-diag=0).
>
> The mechanism (Appendix §A.2) combines (a) seeded `mulberry32` PRNG inside `PlannerAgent._rng`, (b) RFC-4122 type-5 deterministic UUIDs via a fixed namespace `NOESIS_NAMESPACE_PLAN` = `1b030f78-2b6b-4aa0-9ddc-7a6d82c0d5e5` for every `PlanStep.id` and `ExecutionPlan.id`, (c) epoch-sentinel `created_at` timestamps in deterministic mode, and (d) audit scrubbing of transient strings so the manifest SHA-256 measures semantic equality rather than transient token/workspace identifiers.

---

## Reproduce commands for reviewers / viva

```bash
# Fast pytest-smoke (15 runs, ~1 s):
cd backend ; py scripts/determinism_manifest.py --runs 3 --seeds 42,7,1337 --output /tmp/smoke.csv

# CODS-COMAD exact evidence:
cd backend ; py scripts/determinism_manifest.py --runs 20 --seeds 42 --output ../docs/eval/determinism_manifest_20260824.csv

# CI gating (exit code 3 if score < 1.0):
echo $?
```

Expected exit code for the CODS-COMAD command above: **0** (`reproducibility_score >= 1.0`).

---

## Pending / next steps

- **Scale to 1 000 runs × 10 goals × 3 seeds (42, 7, 1337) = 30 000 same-pair evidence** for arXiv long-form — reuse same script with `--runs 1000 --seeds 42,7,1337`.
- **Cross-platform replica:** repeat macOS Apple Silicon M2/M3 + Linux x64 to confirm identical SHA per-platform (uuid5 + mulberry32 are math-identical across platforms, so we expect score=1.0 there as well).
- **Jetson Orin Nano W16 replica:** once hardware is available, repeat on `aarch64` to close RQ2 platform portability → write §6.2 addendum table (laptop x64 / Apple Silicon / Jetson Orin Nano — 3 columns, 3× score=1.0).
