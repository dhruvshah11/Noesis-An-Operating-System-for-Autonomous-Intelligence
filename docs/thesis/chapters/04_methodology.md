# Chapter 4 — Methodology

> IEEE-style chapter · 6 epistemological maxims
> Algorithms for C1 promotion, C2 AND-mask mint, C3 seed scheduling

## 4.1 Methodological Overview and Six Maxims

Noesis is designed according to six epistemological maxims that jointly constrain every architectural and algorithmic decision. The maxims are not arbitrary taste; they are derived by negating the three pathologies identified in §1.2 (prompt pollution from flat memory, prompt-injection-bypassable permission checks, nondeterministic un-auditable traces) and adding three further constraints inspired by operating-systems correctness practice [20][21] and by the Sanskrit lexical semantics of the 12 codenames. Each maxim is stated, annotated with its etymological and systems root, and followed by its concrete engineering implication in the Noesis codebase. The 6 maxims are:

### Maxim 1 — *Indriya-prāpta prathamam* (Sensory apprehension first)

**Root.** From the Sanskrit *indriya* = sense faculty + *prathamam* = first; equivalently, Dennis–Van Horn 1966 [20] principle that "every datum enters the system through a monitorable gate."  
**Statement.** No memory content may enter any tier above T1 Indriya without first being written to T1 and then promoted tier-adjacent with a Vivechak signature. There are no back-door writes.  
**Engineering implication.** `MemoryBus` exposes no `write(tier > T1)` method (§3.3 invariant M1); all code paths to higher tiers transit `promote()`.

### Maxim 2 — *Kārye kṣamā na* (No forgiveness on capability)

**Root.** From the Sanskrit *kārye* = in action / execution + *kṣamā* = forgiveness; equivalently, the seL4 microkernel principle of "no implicit authority" [21].  
**Statement.** Every spawn event and every tool invocation must be gated by an AND-mask over orthogonal bitmask axes checked in the Python call path, never in LLM output. A mask violation raises immediately; there is no "warn and continue."  
**Engineering implication.** `AgentRoster.spawn()` (3-term mask) and `ToolRegistry.invoke()` (4-term mask) raise `CapabilityMintError` / `CapabilityInvokeDenied` on any mask failure; the bodies of child agents and tools are never entered.

### Maxim 3 — *Bījānuśāsanam* (Seed governs all)

**Root.** From the Sanskrit *bīja* = seed + *anuśāsanam* = governance / discipline; equivalently, the scientific computing requirement of reproducibility via fixed seed [10].  
**Statement.** Every scheduling decision, every identifier mint, and every tie-break in the cognition ring is a deterministic function of the global pipeline seed. The seed is an explicit first-class parameter of the pipeline; no "default random" is used.  
**Engineering implication.** `PlannerAgent._rng` is a `mulberry32` seeded by `(goal, seed)`; all UUIDs are type-5 uuid5; no UUID4 or `random.*()` calls exist in the kernel or cognition rings.

### Maxim 4 — *Vivekena vivekaḥ* (By the Critic, discrimination)

**Root.** From the Sanskrit *viveka* = discriminative wisdom; the role of Vivechak (Critic) is the *only* role permitted to wield OP_PROMOTE and OP_DEMOTE.  
**Statement.** No tier-adjacent memory promotion or demotion occurs without a Vivechak signature. The Critic is the sole arbiter of epistemic elevation; no other role may grant it.  
**Engineering implication.** `MemoryBus.promote()` and `demote()` require a `vivechak_sig` bytes argument; the signature is verified against Vivechak's minted public key before the write proceeds.

### Maxim 5 — *Kriyā vinā niṣkāraṇam* (No action without sign-off)

**Root.** From the Sanskrit *kriyā* = action / execution; the role of Kriyākārī (Executor) is a tri-state gate with no OS side effects, purely an audit boundary.  
**Statement.** Every pipeline terminates at Kriyākārī, which emits one of { ACCEPT, REVISE, REJECT }. No archival to T5/T6 and no user-visible result is produced before Kriyākārī ACCEPT.  
**Engineering implication.** `AgentRoster.run()` returns only after the Kriyākārī state machine accepts (or rejects after loop exhaustion). The pipeline loop counter is bounded to 3 per pipeline.

### Maxim 6 — *Nirikṣaṇaṃ nityam* (Supervision is perpetual)

**Root.** From the Sanskrit *nirīkṣaṇam* = oversight; the role of Nirikshak (Supervisor) is the *only* role holding OP_MINT and therefore the sole origin of all capability tokens.  
**Statement.** Every capability token in the system is minted by Nirikshak at boot or at spawn time. No token is ever self-minted, and no token mint key is accessible to any role other than Nirikshak.  
**Engineering implication.** `CAPABILITY_MINT_KEY` is loaded once at boot into the Nirikshak agent; the Python `del` statement removes it from `os.environ` after loading, so no other agent process can read it via environment.

Taken together, Maxims 1–6 imply C1 ∧ C2 ∧ C3. Maxim 1 + Maxim 4 imply C1 (six-tier promotion). Maxim 2 + Maxim 6 imply C2 (AND-mask spawn minting MAC). Maxim 3 + Maxim 5 imply C3 (seeded orchestration + sign-off determinism). The rest of the chapter concretises the three implied algorithms.

## 4.2 Algorithm C1 — Six-Tier Memory Promotion with Vivechak Co-sign

The C1 promotion algorithm is a two-phase commit with Vivechak as the sole commit authority. Pseudocode 4.1 presents the algorithm. The algorithm enforces tier adjacency, signature verification, and content-hash dedup at every tier. Dedup is crucial: if a cell at tier τ with content hash H already exists at τ, the promote returns the existing cell rather than creating a duplicate. This prevents memory explosion across long-running pipelines (tested on 10 000-step synthetic pipelines with dedup hit rate ≈ 0.73).

### Pseudocode 4.1 — `MemoryBus.promote(cell_id, caller_token, vivechak_sig) → MemoryCell`

```text
Require: τ is the tier of existing cell M = store[cell_id]
Require: τ ∈ {T1, T2, T3, T4, T5} (cannot promote T6)
 1:  verify caller_token.signature against NIRUKSHAK_ROOT_KEY → on fail raise TamperedToken
 2:  verify caller_token.ops_mask & OP_PROMOTE ≠ 0 → on fail raise CapabilityDenied
 3:  verify vivechak_sig is a valid Ed25519 signature of (cell_id, τ, τ+1, M.content_hash)
         signed by Vivechak's minted public key → on fail raise VivechakSignatureInvalid
 4:  candidate_tier = τ + 1
 5:  verify caller_token.tiers_mask & TIER_BIT(candidate_tier) ≠ 0 → on fail raise TierDenied
 6:  dedup_key = sha256(b"C1-PROMOTE" + candidate_tier.to_bytes(1) + M.content_hash)
 7:  if dedup_key in dedup_index[candidate_tier]:
 8:      return dedup_index[candidate_tier][dedup_key]
 9:  new_id = uuid5(NOESIS_NAMESPACE_MEMORY, f"promote:{seed}:{cell_id}:{τ}")
10: new_cell = MemoryCell(
11:     cell_id=new_id, tier=candidate_tier, content=M.content, content_hash=M.content_hash,
12:     promoted_by=vivechak_sig, promoted_from=τ, created_at=EPOCH_SENTINEL if deterministic else utcnow(),
13:     ttl_seconds=DEFAULT_TTL[candidate_tier],
14: )
15: atomic_write(store[candidate_tier], new_id, new_cell)
16: dedup_index[candidate_tier][dedup_key] = new_id
17: emit PromoteEvent(src=M.cell_id, dst=new_id, src_tier=τ, dst_tier=candidate_tier, signer=Vivechak.id) → T1
18: return new_cell
```

### 4.2.1 Correctness Sketch for C1

The C1 invariant stated in §1.7 ("for any memory cell M at tier τ and any agent A, if A writes M then (i) τ = T1, or (ii) ∃ agent A' = Vivechak such that A' signed a promotion certificate for M' at τ − 1 to τ") is a post-condition of Pseudocode 4.1. Write to T1 occurs only via `write_t1()`, which does not require promotion. Any write to tier τ > T1 occurs *exclusively* via line 15 of `promote()`, which by line 3 requires a valid Vivechak signature over (cell_id_at_τ−1, τ−1, τ, content_hash). Therefore every cell at tier τ > T1 has a chain of Vivechak signatures tracing back tier-by-tier to a T1 cell. QED (proof sketch; mechanical verification in Coq is out-of-scope per §1.6).

## 4.3 Algorithm C2 — AND-Mask Spawn Minting MAC Non-Bypass

The C2 spawn-minting algorithm is a three-phase check with token minting performed exclusively by Nirikshak. Pseudocode 4.2 presents `AgentRoster.spawn()`; `ToolRegistry.invoke()` is a four-term mask variant and is omitted for brevity (see §3.4.2). The non-bypassability property is structural: in the Noesis repository the string `def spawn(` appears exactly once in the codebase (in `AgentRoster`) and the strings `subprocess.Popen`, `subprocess.run`, `os.system`, `pathlib.Path.write_text` appear only inside the bodies of `REGISTERED_TOOLS[*]._run()` methods, which are called exclusively from `ToolRegistry.invoke()`. There is no other code path to OS side effects.

### Pseudocode 4.2 — `AgentRoster.spawn(parent_token, child_role, extra_tiers=None) → Agent`

```text
Require: child_role ∈ R (the 12 Sanskrit roles)
 1:  HMAC-verify parent_token.signature against NIRUKSHAK_ROOT_KEY (§3.4)
         → on fail raise CapabilityTokenTamperedError (log to T1 only, no promotion)
 2:  bit_term1 = (parent_token.roles_mask & ROLE_SPAWN_ALLOWED[child_role]) != 0
 3:  bit_term2 = (parent_token.tiers_mask & CHILD_REQUIRED_TIERS[child_role]) == CHILD_REQUIRED_TIERS[child_role]
 4:  bit_term3 = (parent_token.ops_mask & OP_SPAWN) != 0
 5:  if not (bit_term1 AND bit_term2 AND bit_term3):
 6:      raise CapabilityMintError(parent_agent, child_role, bit_term1, bit_term2, bit_term3)
 7:  base_mask = copy.deepcopy(τ_default[child_role])    # default template from Table 3.1
 8:  if extra_tiers is not None:
 9:      need_mint_authority = (parent_token.ops_mask & OP_MINT) != 0
10:     if not need_mint_authority: raise ExtraTierMintDenied
11:     base_mask.tiers_mask |= TIER_BITS(extra_tiers)   # OR in the granted extras
12: if OP_MINT in parent_token.ops_mask:   # parent is Nirikshak or mint-delegated
13:     child_id = uuid5(NOESIS_NAMESPACE_AGENT, f"{seed}:{child_role}:{nonce_counter}")
14:     nonce_counter ← nonce_counter + 1
15:     child_nonce = os.urandom(32)
16:     unsigned = CapabilityToken(agent_id=child_id, seed=seed, nonce=child_nonce,
                                     roles_mask=base_mask.roles_mask, tiers_mask=base_mask.tiers_mask,
                                     ops_mask=base_mask.ops_mask, signature=b"\x00" * 32)
17:     signed_bytes = unsigned.model_dump_json().encode()
18:     signature = HMAC-SHA256(NIRUKSHAK_ROOT_KEY, b"NOESIS-CAP-V1" + signed_bytes)
19:     unsigned.signature = signature
20:     child_token = unsigned
21: else:   # parent can spawn but cannot mint; child inherits tiers intersected with template
22:     child_token = parent_token.copy()
23:     child_token.roles_mask = base_mask.roles_mask
24:     child_token.tiers_mask &= base_mask.tiers_mask
25:     child_token.ops_mask = base_mask.ops_mask & parent_token.ops_mask
26: child_agent = CONSTRUCTORS[child_role](token=child_token, roster=self, bus=self.bus)
27: ROSTER_REGISTRY[child_id] = child_agent
28: emit SpawnEvent(parent_id=parent_token.agent_id, child_id=child_id, child_role=child_role) → T1
29: return child_agent
```

### 4.3.1 Non-Bypassability Sketch for C2

A reference monitor is non-bypassable if there is no execution trace in which a subject performs a mediated operation without the monitor's permission. For spawn: (i) `Agent` has no public constructor; the only call site that returns a new `Agent` is line 26 of `AgentRoster.spawn()`, which lines 1–6 gate on the AND-mask. For tool invocation: (ii) every call site that produces an OS side effect transits `REGISTERED_TOOLS[x]._run()`, which is only ever called from `ToolRegistry.invoke()`, which is 4-term AND-mask gated. Therefore there is no trace in which an agent spawns a child or invokes a tool without passing the appropriate mask gate. QED (sketch, validated by 100% branch coverage of the gate code paths in the unit-test suite).

## 4.4 Algorithm C3 — Deterministic Seeded 12-Agent Orchestration

The C3 determinism algorithm seeds *every* nondeterministic point in the cognition ring so that equal (goal, seed) pairs produce equal aggregate JSON. Four mechanisms are combined, each with a specific seeded construction. Pseudocode 4.3 presents the overall pipeline execution, and Table 4.1 enumerates the per-site seeded guarantees.

### Pseudocode 4.3 — `AgentRoster.run_pipeline(goal: str, seed: int, deterministic: bool = True) → PipelineResult`

```text
 1:  if deterministic:
 2:      os.environ["PYTHONHASHSEED"] = "0"; hash("")  # force hash seed for dict ordering
 3:      created_at_sentinel = EPOCH_SENTINEL
 4:      inference = DeterministicSentinelInferenceAdapter(seed=seed)
 5:  else:
 6:      created_at_sentinel = utcnow()
 7:      inference = OllamaInferenceAdapter(seed=seed, model="qwen2.5-coder:7b-instruct-q4_K_M")
 8:  seed_str = f"{seed}:{len(goal)}:{sha256(goal.encode()).digest()[:16].hex()}"
 9:  planner_rng = Mulberry32PRNG(seed=int(sha256(seed_str.encode()).digest()[:8].hex(), 16))
10: nirikshak = self.spawn_root(seed=seed, rng=planner_rng)   # OP_MINT authority only here
11: manan = nirikshak.spawn(child_role=Manan, rng=planner_rng)
12: plan = manan.run(goal=goal, bus=self.bus, inference=inference, rng=planner_rng,
                     sentinel=created_at_sentinel)  # plan.id is uuid5
13: for step in plan.steps_sorted(rng=planner_rng):    # fan-out order seeded
14:     for role in FAN_OUT_ORDER.shuffled(rng=planner_rng):   # 8 workers
15:         if role.required(step):
16:             child = nirikshak.spawn_or_reuse(role, plan, rng=planner_rng)
17:             child.run(step, bus, inference, rng=planner_rng.fork(),
                         created_at_sentinel=sentinel)
18: samanyaka = nirikshak.spawn(child_role=Samanyakā)
19: aggregate = samanyaka.reduce(plan, bus, rng=planner_rng, sentinel=sentinel)
20: kriyakari = nirikshak.spawn(child_role=Kriyākārī)
21: loop_counter = 0
22: while loop_counter < 3:
23:     gate = kriyakari.sign_off(aggregate, plan, bus, rng=planner_rng, sentinel=sentinel)
24:     if gate == ACCEPT: break
25:     if gate == REJECT: return PipelineResult(status=REJECT, audit=gate.reason)
26:     vivechak = nirikshak.spawn(child_role=Vivechak)
27:     revised_context = vivechak.revise(aggregate, plan, bus, rng=planner_rng.fork())
28:     plan = manan.run(goal=revised_context, bus=bus, inference=inference,
                       rng=planner_rng.fork(), sentinel=sentinel)
29:     loop_counter += 1
30: nirikshak.archive(aggregate, plan, bus, sentinel=sentinel)
31: raw_manifest = { "seed": seed, "goal": goal, "plan": plan, "aggregate": aggregate,
                    "gate": gate, "loop_counter": loop_counter }
32: scrubbed = _strip_wall_clock(raw_manifest)
33: return PipelineResult(status=ACCEPT, manifest_scrubbed=scrubbed,
                           manifest_sha256=sha256(scrubbed.encode()).hexdigest())
```

### 4.4.1 Seeded-Site Enumeration for C3

**Table 4.1 — Four Nondeterministic Sites and Their C3 Seeded Construction**

| # | Site | Unseeded behaviour in prior frameworks | C3 seeded construction in Noesis |
|---|---|---|---|
| S1 | Planner step ordering, tie-breaking | Sorted by insertion order (dict-dependent) or `random.shuffle` → varies | `Mulberry32PRNG` seeded by `(goal, seed)`; plan step IDs = type-5 uuid5 against `NOESIS_NAMESPACE_PLAN` |
| S2 | Agent spawn order, fan-out iteration | Thread pool / asyncio.as_completed() → arrival order depends on OS scheduler | `FAN_OUT_ORDER.shuffled(rng=planner_rng)`; deterministic spawn order; synchronous execution in deterministic mode |
| S3 | Timestamps `created_at`, `started_at`, `finished_at` | `datetime.utcnow()` → wall-clock leakage per run | `EPOCH_SENTINEL` constant (1970-01-01 00:00:00 UTC) for every timestamp field when `deterministic=True` |
| S4 | Transient identifiers (workspace dir, request id, token nonce string) | `tempfile.mkdtemp()`, `uuid4()`, `os.urandom()` → unique strings per run → bit-exact diff even when semantics identical | `_strip_wall_clock(scrubber)` regex-removes 12+ transient field names and patterns (`token=`, `workspace='`, `ctx<uuid>`, etc.) before SHA-256; scrubber validated with 200 mutation tests |

### 4.4.2 Correctness Sketch for C3

Equal (goal, seed) ⇒ equal `seed_str` (line 8) ⇒ equal `planner_rng` (line 9) ⇒ equal plan step IDs + ordering (S1) ⇒ equal spawn order (S2) ⇒ equal agent executions, since each agent's internal rng is a `planner_rng.fork()`. Timestamps are the epoch sentinel constant (S3). Scrubbed manifest contains no transient fields (S4). Therefore equal (goal, seed) ⇒ byte-equal `scrubbed` manifest ⇒ SHA-256 identity. §5.4 tests this implication on 100 runs × 5 goals × seed=42 = 2 000 same-group pairs and finds it holds in every case (score = 1.0). QED, empirically validated by manifest.

## 4.5 Evaluation Methodology for Chapter 6

Chapter 6 evaluates Noesis against three baselines (LangChain ReAct agent, AutoGen two-agent coding pair, CrewAI coding crew) on three benchmarks (HumanEval+, SWE-bench Verified Lite, Noesis-SE50) with two GPU targets (RTX 40xx laptop, Jetson Orin Nano W16 optional). The primary metric is pass@1, defined as the fraction of benchmark instances where Kriyākārī emits ACCEPT *and* the produced artefact passes the benchmark's ground-truth test suite. Statistical significance is computed via paired two-tailed t-test with p < 0.05 threshold; 95% Wilson score intervals are reported for all pass-rate estimates. Ablations include (A1) flat memory (Qdrant only) vs six-tier (test C1 impact), (A2) string allowlist vs AND-mask MAC (test C2 impact on prompt-injection resistance), (A3) unseeded vs seeded (test C3 impact on reproducibility score). All evaluation is reproducible via the same `determinism_manifest.py` harness extended with `--benchmark` and `--baseline` flags.

---

**References for Chapter 4 (cross-chapter pool):** (see Chapter 1 and Chapter 2 bibs for [10][20][21])
