# Chapter 3 — System Architecture

> IEEE-style chapter · Formal Pydantic-level type sketches
> 12 Sanskrit codenames, 6 memory tiers, Kriyākārī tri-state gate

## 3.1 Architectural Principles and Hexagonal Ports

Noesis adopts a hexagonal (ports-and-adapters) kernel architecture [26] with three concentric rings: (i) the innermost **Capability Ring** (`noesis.kernel`) containing the MAC token mint, spawn gate, and invoke gate — formally verified by exhaustive unit-test branch coverage rather than mechanical proof; (ii) the middle **Cognition Ring** (`noesis.agents`, `noesis.memory`) containing the 12 Sanskrit-named agents and the six-tier memory bus; (iii) the outermost **Adapter Ring** (`noesis.adapters`) containing the Ollama inference adapter, FastAPI HTTP adapter, Next.js dashboard adapter, CLI adapter, and optional Jetson Orin Nano W16 GPIO adapter. The hexagonal layering guarantees that the Capability Ring imports nothing from the Cognition or Adapter rings, so the spawn-and-invoke gates cannot be tainted by prompt content or LLM output — this is the structural root of the C2 non-bypassability claim. All inter-ring communication flows via typed `Port` interfaces: for example, `InferencePort` (pure abstract) has implementations `OllamaInferenceAdapter` and `DeterministicSentinelInferenceAdapter`, the latter of which returns seeded canned responses without calling any model, enabling the C3 manifest. The three architectural invariants that Noesis enforces at the type level (Pydantic v2 validators) are: (I1) every agent carries exactly one `CapabilityToken` at construction time; there is no setter or mutator for `agent.token` post-construction; (I2) every memory write on tiers T2–T6 transits `MemoryBus.write(tier, cell, token)` and never reaches the backing store directly; (I3) every OS side effect transits exactly one of `AgentRoster.spawn()` or `ToolRegistry.invoke()`, both of which are in the Capability Ring.

## 3.2 The 12-Agent Roster Topology

The roster is a directed acyclic graph with a single source (Manan), a single sink (Nirikshak), a wide fan-out of eight worker agents, a single synthesiser node, and a tri-state gate. Let R denote the set of 12 agent roles with Sanskrit codenames, formally:

R = { Manan, Darshak, Vidya, Parikshak, Karmakarta, Anveshak, Vivechak, Paalak, Rakshak, Samanyakā, Kriyākārī, Nirikshak }

Each role has an English gloss, a canonical scope, a capability mask template `τ_default(R)`, and a canonical memory tier write set. Table 3.1 enumerates all 12 roles with their scope and default mask template.

**Table 3.1 — The 12 Sanskrit-Named Agent Roles (Canonical Scope & Default Mask Template)**

| # | Sanskrit codename | English gloss | Canonical scope | Default mask template `τ_default(R)` (role bits / tier bits / op bits) |
|---|---|---|---|---|
| 1 | **Manan** | Planner (from *manana*, "reflection") | Goal decomposition into *k* ordered PlanSteps, dependency DAG, uuid5 deterministic step IDs | ROLE_MANNAN / T1_T2_RW T3_R / OP_READ OP_WRITE OP_SCHEDULE |
| 2 | **Darshak** | Analyst (from *darśana*, "viewpoint") | Static analysis of code/text: AST diffs, type contracts, dependency injection maps, complexity analysis | ROLE_DARSHAK / T1_R T2_T3_RW / OP_READ OP_WRITE OP_PROMOTE_T1_T2 |
| 3 | **Vidya** | Coder (from *vidyā*, "learning/skill") | Code synthesis, refactoring, patch emission; writes to T2 Kushalata skill templates | ROLE_VIDYA / T1_R T2_T3_RW / OP_READ OP_WRITE OP_INVOKE |
| 4 | **Parikshak** | Tester (from *parīkṣak*, "examiner") | Unit/integration test generation, pytest runners, mutation testing; signs off test pass | ROLE_PARIKSHAK / T1_R T2_R T3_T4_RW / OP_READ OP_WRITE OP_INVOKE |
| 5 | **Karmakarta** | Tooler (from *karmakārta*, "one who performs actions") | **ONLY agent holding OP_INVOKE for file system / OS / network tools;** gate for all OS side effects | ROLE_KARMAKARTA / T1_RW T2_R / OP_READ OP_WRITE OP_INVOKE (15 CapabilityOps) |
| 6 | **Anveshak** | Researcher (from *anveśhak*, "investigator") | Retrieval: web search, doc lookup, repo grep, dependency version pinning, upstream issue search | ROLE_ANVESHAK / T1_RW T3_RW / OP_READ OP_WRITE OP_INVOKE |
| 7 | **Vivechak** | Critic (from *vivechak*, "analyst/critic") | **ONLY agent holding OP_PROMOTE across tiers;** signs off tier-adjacent promotion certificates; triages Kriyākārī revise loop | ROLE_VIVECHAK / T1–T6_R / OP_READ OP_PROMOTE OP_DEMOTE |
| 8 | **Paalak** | Memory (from *pālak*, "keeper/guardian") | Bus agent for memory routing, dedup, TTL eviction, cold-tier compaction of T4–T5 | ROLE_PAALAK / T1–T6_RW / OP_READ OP_WRITE OP_COMPACT |
| 9 | **Rakshak** | Security (from *rakshak*, "protector") | Static SAST, dependency CVE scan, prompt-injection detection on input prompts, capability token signature audit | ROLE_RAKSHAK / T1_RW T3_R T6_R / OP_READ OP_WRITE OP_AUDIT_TOKEN |
| 10 | **Samanyakā** | Synthesizer (from *sāmānyakā*, "generaliser") | Fan-in reduction of 8 workers: unifies Darshak/Vidya/Parikshak/Karmakarta/Anveshak/Vivechak/Paalak/Rakshak outputs into one aggregate | ROLE_SAMANYAKA / T2–T4_R / OP_READ OP_WRITE |
| 11 | **Kriyākārī** | Executor (from *kriyākārī*, "one who acts") | **Tri-state sign-off gate** — every pipeline terminates here; emits one of { ACCEPT, REVISE(loop_count), REJECT(reason) }; NO OS side effects, purely an audit gate | ROLE_KRIYAKARI / T1–T4_R / OP_READ OP_SIGN_OFF |
| 12 | **Nirikshak** | Supervisor (from *nirīkshak*, "overseer") | **ONLY agent holding OP_MINT for CapabilityToken;** archival to T5/T6, pipeline manifest emit, spawn of Manan at boot | ROLE_NIRIKSHAK / T1–T6_RW / OP_MINT OP_SPAWN OP_READ OP_WRITE OP_ARCHIVE |

The canonical execution DAG, fixed for all pipelines (no dynamic topology in the capstone scope), is:

**Nirikshak → Manan → { Darshak ∥ Vidya ∥ Parikshak ∥ Karmakarta ∥ Anveshak ∥ Vivechak ∥ Paalak ∥ Rakshak } → Samanyakā → Kriyākārī → ( ACCEPT → Nirikshak archive | REVISE → Vivechak → Manan loop ) | REJECT → Nirikshak audit log**

The Kriyākārī tri-state gate is not an agent *acting* on the world — it is a typed verification gate. If Kriyākārī emits ACCEPT, the pipeline is complete and the aggregate is archived. If Kriyākārī emits REVISE (with a signed reason string and a loop counter bounded to 3 iterations per pipeline to prevent infinite loops), the Vivechak (Critic) rewrites the goal context and returns it to Manan (Planner) for a second decomposition with updated memory state. If Kriyākārī emits REJECT, the pipeline aborts with a signed audit entry, and no memory cell above T1 is touched.

## 3.3 The Six-Tier Semantic Memory Bus

Formally, let Θ = {T1, T2, T3, T4, T5, T6} be the totally ordered tier set, with total order < defined by promotion direction: T1 < T2 < T3 < T4 < T5 < T6. A memory cell M is a tuple `(cell_id: uuid5, tier: Θ, content: bytes, content_hash: sha256, promoted_by: VivechakSignature | None, promoted_from: Θ | None, created_at: datetime | EPOCH_SENTINEL, ttl_seconds: Optional[int])`. The MemoryBus exposes four typed methods only:

```python
class MemoryBus(Port):
    def read(self, tier: Θ, cell_id: UUID, token: CapabilityToken) -> MemoryCell: ...
    def write_t1(self, content: bytes, token: CapabilityToken) -> MemoryCell: ...
    def promote(self, cell_id: UUID, token: CapabilityToken, vivechak_sig: bytes) -> MemoryCell: ...
    def demote(self, cell_id: UUID, token: CapabilityToken, vivechak_sig: bytes) -> MemoryCell: ...
```

Three type-level invariants are enforced by Pydantic v2 validators, not merely by convention: (M1) there is no `write(tier > T1)` method; the *only* way a cell arrives at tier τ > T1 is via `promote()` called with a Vivechak signature. (M2) `promote()` only accepts a cell at tier τ and produces a cell at tier τ + 1; there is no skip-tier promotion code path. (M3) `promoted_by` and `promoted_from` are frozen fields post-promotion; no agent may overwrite them. Table 3.2 enumerates each tier's canonical semantics, backing store, write policy, eviction policy, and representative contents drawn from the Noesis-SE50 G0 Rust CLI todo task.

**Table 3.2 — Six-Tier Semantic Memory Hierarchy T1 Indriya → T6 Tattva (Canonical Semantics)**

| Tier | Sanskrit name | English gloss | Semantic lifespan | Canonical backing store | Write policy | Eviction policy | Representative contents (G0 Rust CLI task) |
|---|---|---|---|---|---|---|---|
| **T1** | Indriya | Sensory | Ephemeral per step (seconds–minutes) | In-process ring buffer `collections.deque(maxlen=4096)` | Any agent may `write_t1()`; append only; no mask needed for write (read still requires T1_R) | LRU ring; evicts oldest after 4 096 entries; never persisted to disk | `cargo init` stdout line "Created binary (application) `todo` package"; raw LLM stream tokens; `vim` keystroke buffer; unparsed error message "error[E0433]: failed to resolve: maybe a missing crate `clap`?" |
| **T2** | Kushalata | Skills | Per-tool / per-pattern (hours–days) | Redis LRU, keyed by `tool_name:pattern_hash` | Require AND(token.roles, τ_DEFAULT(role), TIER_T2_WRITE); may be written only by promote(T1→T2) signed by Vivechak | TTL 86 400 s (24 h) / LRU 65 536 entries | Pattern "how to add clap derive macros to Cargo.toml"; Bash invocation `cargo add clap --features derive`; TypeScript zod schema pattern; Python visitor-pattern template |
| **T3** | Gyān | Knowledge | Factual / project-globally true (weeks–months) | SQLite FTS5 table `gyan_cells` + Qdrant local vector index `collection=gyan` (cosine sim, 384-dim nomic-embed-text v1.5 4-bit) | Require AND(token.roles, TIER_T3_WRITE); written only by promote(T2→T3) | Manual compaction via Paalak (Memory) agent; no auto-eviction | "Rust crates using clap v4 must use `#[derive(Parser)]` not the old `App::new()` builder"; "Python visitor pattern requires `visit(node)` dispatch on `type(node).__name__`"; "Jest tests live in `__tests__/` or `*.test.ts`" |
| **T4** | Ranniti | Tactical | Per-pipeline / per-task (minutes–days) | Redis hash keyed by `task_id`; JSONL snapshot on disk at `/tmp/noesis/ranniti/{task_id}.jsonl` | Require AND(token.roles, TIER_T4_WRITE); written only by promote(T3→T4) | TTL 604 800 s (7 d) → archivable to T5 with Vivechak sign-off | "G0 Rust CLI plan: add todo/list/done flags → Step 1 cargo add clap → Step 2 struct Cli → Step 3 match cli.command → Step 4 cargo test"; Parikshak test plan: 3 unit tests (add/list/done) + 1 integration test |
| **T5** | Yojana | Strategic | Per-project / per-capstone (months–semester) | Git-tracked YAML `$PROJECT_ROOT/.noesis/yojana/*.yaml`; SHA-256 pinned on every commit | Require AND(token.roles, TIER_T5_WRITE, Nirikshak co-sign); written only by promote(T4→T5) | Never evicted; Git history is the audit log; manual archival to frozen T6 on project completion | "18-week Noesis capstone Gantt: W1–W6 kernel + bus, W7–W12 roster, W13–W16 evaluation, W17 paper, W18 viva"; "G0 Rust CLI acceptance criteria: `todo add 'x'` persists to ~/.todo.db, `todo list` prints pending, `todo done 1` marks complete" |
| **T6** | Tattva | Principles | Immutable, boot-time pin (lifetime of system install) | Read-only YAML file `/etc/noesis/tattva.d/*.yaml` (Linux) or `%PROGRAMDATA%\Noesis\tattva.d\` (Windows); SHA-256 pinned at boot by Nirikshak; no write API exposed | **No write method exists in the bus;** contents may only be edited out-of-band by a human sysadmin with file-system write; Nirikshak computes a boot hash | Never evicted; boot failure if any tattva file hash is mutated between boots | "Prefer composition over inheritance"; "Never invoke a shell command with unescaped user input (CWE-78)"; "Every tool invocation must have a REVOCABLE capability mask"; "No code may call subprocess.Popen outside ToolRegistry"; "Kriyākārī loop counter ≤ 3 per pipeline" |

The C1 invariant (§1.7) — "for any memory cell M at tier τ and any agent A, if A writes M then (i) τ = T1, or (ii) ∃ agent A' = Vivechak such that A' signed a promotion certificate for M' at τ − 1 to τ" — is therefore enforced by the combination of the type-level invariants (M1)–(M3), the `promote()` signature check, and the absence of any `write(tier > T1)` method. The type system, not convention, is the guarantor.

## 3.4 Capability Kernel: C2 AND-Mask Spawn Minting

The C2 kernel lives in `noesis.kernel.capability` and defines three 64-bit integer bitmasks per `CapabilityToken`: a 12-bit `roles_mask` (one bit per Sanskrit role), a 6-bit `tiers_mask` (one bit per T1–T6), and a 15-bit `ops_mask` (one bit per CapabilityOp). The 15 CapabilityOps are:

```
OP_READ=1, OP_WRITE=2, OP_SPAWN=4, OP_INVOKE=8, OP_PROMOTE=16, OP_DEMOTE=32,
OP_COMPACT=64, OP_MINT=128, OP_SCHEDULE=256, OP_AUDIT_TOKEN=512, OP_SIGN_OFF=1024,
OP_ARCHIVE=2048, OP_REVOKE=4096, OP_EXPORT=8192, OP_IMPORT=16384
```

A `CapabilityToken` also carries three identity fields plus an HMAC-SHA256 signature:

```python
class CapabilityToken(BaseModel):
    agent_id: UUID              # uuid5, NOESIS_NAMESPACE_AGENT
    seed: int                   # from the global pipeline seed
    nonce: bytes                # 32 random bytes minted by Nirikshak
    roles_mask: Annotated[int, Field(ge=0, le=2**12 - 1)]
    tiers_mask: Annotated[int, Field(ge=0, le=2**6 - 1)]
    ops_mask: Annotated[int, Field(ge=0, le=2**15 - 1)]
    signature: Annotated[bytes, Field(min_length=32, max_length=32)]  # HMAC-SHA256
```

The signature is computed over `b"NOESIS-CAP-V1" + agent_id.bytes + seed.to_bytes(8,'big') + nonce + roles_mask.to_bytes(2) + tiers_mask.to_bytes(1) + ops_mask.to_bytes(2)`, keyed by a `NIRUKSHAK_ROOT_KEY` 32-byte environment variable loaded once at boot into the Nirikshak agent only. The signature check is performed at every spawn/invoke gate *before* the mask check, so a tampered token (e.g., LLM output trying to flip OP_MINT bit) fails the signature check first, producing a `CapabilityTokenTamperedError` that is logged to T1 but never promoted.

### 3.4.1 The Spawn Gate (3-term AND-mask)

`AgentRoster.spawn(parent_token, child_role, extra_tiers=None)` performs:

1. Verify `parent_token.signature` against root key → if fail raise `CapabilityTokenTamperedError`.
2. Compute `spawn_mask = (parent_token.roles_mask & ROLE_SPAWN_ALLOWED[child_role]) != 0  AND  (parent_token.tiers_mask & CHILD_REQUIRED_TIERS[child_role]) == CHILD_REQUIRED_TIERS[child_role]  AND  (parent_token.ops_mask & OP_SPAWN) != 0`.
3. If `spawn_mask` is False → raise `CapabilityMintError`; no child is constructed.
4. Nirikshak (and only Nirikshak) mints a new child token with `τ_default(child_role)` ORed with `extra_tiers` if the parent holds `OP_MINT`; otherwise child inherits parent's tiers intersected with the child's role template.

### 3.4.2 The Invoke Gate (4-term AND-mask)

`ToolRegistry.invoke(caller_token, tool_name, **kwargs)` performs:

1. Verify `caller_token.signature`.
2. Retrieve `tool = REGISTERED_TOOLS[tool_name]`; every tool declares a constant `tool.REQUIRED_CAP` bitmask.
3. Compute `invoke_mask = (caller_token.roles_mask & tool.REQUIRED_ROLES) != 0  AND  (caller_token.tiers_mask & tool.REQUIRED_TIERS) == tool.REQUIRED_TIERS  AND  (caller_token.ops_mask & OP_INVOKE) != 0  AND  (caller_token.ops_mask & tool.REQUIRED_CAP) == tool.REQUIRED_CAP`.
4. If `invoke_mask` is False → raise `CapabilityInvokeDenied`; the tool body is never entered.

A repository-wide grep for `subprocess.Popen`, `subprocess.run`, `os.system`, `os.open`, `pathlib.Path.write_text` confirms that every call site lives inside exactly one `REGISTERED_TOOLS[*]._run()` method; there are zero call sites outside the ToolRegistry. This is the structural basis for the C2 claim of non-bypassability.

## 3.5 C3 Seeded Orchestration Architecture

The C3 determinism architecture isolates all nondeterminism to the `InferencePort` adapter only; the entire Capability Ring + Cognition Ring (kernel, bus, roster, planner, synthesiser, executor) is written in pure Python with no I/O beyond the typed ports. The seeded path uses the following four mechanisms, all of which have code pointers in §5.4. (i) **Seeded PRNG:** `PlannerAgent._rng` is a `mulberry32` seeded PRNG derived from `(goal, seed)` via `seed_str = f"{seed}:{len(goal)}:{hashlib.sha256(goal.encode()).digest()[:16].hex()}"`; every scheduling decision (fan-out order, tie-breaking in equal-priority steps) uses this RNG. (ii) **Type-5 deterministic UUIDs:** all `PlanStep.id` and `ExecutionPlan.id` are RFC-4122 type-5 UUIDs (SHA-1 name-based) against a fixed namespace `NOESIS_NAMESPACE_PLAN = uuid5('1b030f78-2b6b-4aa0-9ddc-7a6d82c0d5e5')`; no UUID4 random identifiers are used in the deterministic path. (iii) **Epoch sentinel timestamps:** `ExecutionPlan.deterministic(seed)` sets every `created_at`, `started_at`, `finished_at` field to the constant `EPOCH_SENTINEL = datetime(1970, 1, 1, 0, 0, 0, tzinfo=UTC)`, so wall-clock cannot leak into the manifest. (iv) **Audit scrub of residual leakage:** `determinism_manifest._strip_wall_clock()` removes 12+ transient field names and regex-scrubs patterns like `Parent token=…`, `workspace='…'`, `ctx<uuid>` before hashing, so the SHA-256 measures semantic content rather than transient id strings. §5.4 presents the 100-run manifest results.

## 3.6 Adapter Ring & Frontend Dashboard

The outermost adapter ring exposes five concrete port implementations. (i) `OllamaInferenceAdapter` implements `InferencePort` via HTTP POST to `http://127.0.0.1:11434/api/generate` with a configurable model (default `qwen2.5-coder:7b-instruct-q4_K_M`), temperature 0.0, and seeded `options.seed` equal to the global pipeline seed. (ii) `FastAPIHTTPAdapter` implements `ControlPort`, exposing `/v1/pipeline/run` POST, `/v1/capabilities/inspect` GET, `/v1/memory/{tier}` GET. (iii) `NextjsDashboardAdapter` is a TypeScript Next.js 14 App Router dashboard with three tabs: Pipeline Visualiser (DAG of the 12 agents, colour-coded by Kriyākārī gate), Memory Tier Browser (browse T1–T6 with tier colour palette and promote history), and Capability Inspector (hex dump of token masks with per-bit legend). (iv) `CLIAdapter` implements a Typer-based CLI for the determinism manifest (`py scripts/determinism_manifest.py`). (v) The optional `JetsonGpioAdapter` (planned for Week 16) implements a `ControlPort` over Jetson Orin Nano W16 GPIO pins for headless edge triggering.

---

**References for Chapter 3:**

[26] Cockburn, "Hexagonal Architecture," https://alistair.cockburn.us/hexagonal-architecture, 2005.
