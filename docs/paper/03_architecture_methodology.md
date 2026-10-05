# 3. Architecture and Methodology (CODS-COMAD 2027 §3 · pages 2–3 · 850 words target)

> Paper-ready ACM SIGCONF style · Capability Ring / Cognition Ring / Adapter Ring + 6 maxims + 12 Sanskrit agent topology + memory bus invariants

## 3.1 Hexagonal Architecture

Noesis adopts a three-ring hexagonal (ports-and-adapters) architecture [17] that structurally enforces C2's non-bypassability claim by design. (i) The innermost **Capability Ring** (`noesis.kernel`) defines the `CapabilityToken` type, the 15 CapabilityOps bitmask (OP_READ, OP_WRITE, OP_SPAWN, OP_INVOKE, OP_PROMOTE, OP_DEMOTE, OP_COMPACT, OP_MINT, OP_SCHEDULE, OP_AUDIT_TOKEN, OP_SIGN_OFF, OP_ARCHIVE, OP_REVOKE, OP_EXPORT, OP_IMPORT), the `AgentRoster.spawn()` 3-term AND-mask gate, and the `ToolRegistry.invoke()` 4-term AND-mask gate. Critically, the Capability Ring imports *nothing* from the outer rings — it does not parse LLM output, it does not touch prompt strings — so the gates are not reachable from prompt content. (ii) The middle **Cognition Ring** (`noesis.agents`, `noesis.memory`) implements the 12 Sanskrit-named agents and the six-tier memory bus, communicating with the Capability Ring exclusively via typed port calls. (iii) The outermost **Adapter Ring** contains inference adapters (`OllamaInferenceAdapter`, `DeterministicSentinelInferenceAdapter` for the C3 deterministic path), the FastAPI HTTP adapter, the Next.js dashboard adapter, the Typer CLI adapter for the manifest harness, and the optional Jetson Orin Nano W16 GPIO adapter. Three type-level invariants are enforced by Pydantic v2 validators: (I1) every agent carries exactly one immutable `CapabilityToken` at construction; (I2) every memory write to T2–T6 transits `MemoryBus.promote()`; (I3) every OS side effect transits exactly one of `spawn()` or `invoke()`.

## 3.2 Twelve-Agent Roster Topology

The 12 Sanskrit-named roles form a fixed-topology DAG with a single source (Nirikshak), a single planner (Manan), an 8-agent wide fan-out, a synthesiser (Samanyakā), a tri-state executor gate (Kriyākārī), and a supervisor sink (Nirikshak). Formally:

R = { Manan (Planner), Darshak (Analyst), Vidya (Coder), Parikshak (Tester), Karmakarta (Tooler), Anveshak (Researcher), Vivechak (Critic), Paalak (Memory), Rakshak (Security), Samanyakā (Synthesizer), Kriyākārī (Executor), Nirikshak (Supervisor) }.

The canonical pipeline is:

**Nirikshak → Manan → { Darshak ∥ Vidya ∥ Parikshak ∥ Karmakarta ∥ Anveshak ∥ Vivechak ∥ Paalak ∥ Rakshak } → Samanyakā → Kriyākārī → [ ACCEPT→archive | REVISE≤3→Vivechak→Manan loop | REJECT→audit ].**

Karmakarta (Tooler) is the *only* role granted OP_INVOKE for file-system/OS/network tools, so Vidya (Coder) cannot write to disk directly; it must emit a patch that Karmakarta then invokes through the gate. Kriyākārī (Executor) is a *purely logical gate with no OS side effects*; it emits one of {ACCEPT, REVISE(loop_counter), REJECT(reason)} and never calls `ToolRegistry.invoke()`. Nirikshak (Supervisor) is the *only* role holding OP_MINT, so it alone signs `CapabilityToken`s with an HMAC-SHA256 key loaded once at boot, then deleted from `os.environ` to prevent exfiltration.

## 3.3 Six-Tier Memory Bus

The six tiers form a totally ordered set Θ = {T1 < T2 < T3 < T4 < T5 < T6} with the following canonical semantics and write invariants: T1 Indriya (Sensory, ephemeral, ring buffer, any agent may `write_t1`), T2 Kushalata (Skills, per-tool, Redis LRU), T3 Gyān (Knowledge, factual, SQLite FTS5 + Qdrant local vector), T4 Ranniti (Tactical, per-task, Redis hash + JSONL), T5 Yojana (Strategic, per-project, Git-tracked YAML), T6 Tattva (Principles, immutable, read-only YAML pinned at boot by SHA-256). The bus exposes only four typed methods: `read(tier, id, token)`, `write_t1(content, token)`, `promote(id, token, vivechak_sig)`, `demote(id, token, vivechak_sig)`. The absence of a `write(tier > T1)` method enforces the C1 invariant at the API level: every cell at τ > T1 has a Vivechak-signature chain of tier-adjacent promotions back to a T1 cell. T6 Tattva has no write API at all; it can only be modified out-of-band by a human sysadmin with file-system write.

## 3.4 Six Epistemological Maxims

The architecture is constrained by six maxims that jointly imply C1 ∧ C2 ∧ C3, stated here with their engineering implication: (1) *Indriya-prāpta prathamam* (Sensory first) → no back-door writes to T2–T6. (2) *Kārye kṣamā na* (No forgiveness on capability) → mask violations raise immediately, never warn-and-continue. (3) *Bījānuśāsanam* (Seed governs all) → every scheduling decision and identifier is a deterministic function of the global seed. (4) *Vivekena vivekaḥ* (By the Critic, discrimination) → only Vivechak holds OP_PROMOTE/OP_DEMOTE. (5) *Kriyā vinā niṣkāraṇam* (No action without sign-off) → no archival before Kriyākārī ACCEPT, loop counter ≤ 3. (6) *Nirikṣaṇaṃ nityam* (Supervision is perpetual) → only Nirikshak holds OP_MINT.

## 3.5 C2 AND-Mask MAC Sketch

A `CapabilityToken` = (agent_id, seed, nonce, roles_mask 12-bit, tiers_mask 6-bit, ops_mask 15-bit, signature=HMAC-SHA256(root_key, payload)). `AgentRoster.spawn(parent_token, child_role)` computes: `mask_pass = (parent.roles ∧ CHILD_REQUIRED_ROLES[child] ≠ 0) ∧ (parent.tiers ⊇ child.required_tiers) ∧ (OP_SPAWN ∈ parent.ops)`. If mask_pass is False the method raises before constructing the child. `ToolRegistry.invoke(caller_token, tool_name)` adds a fourth term: `tool.REQUIRED_CAP ⊆ caller.ops`. A repository-wide grep confirms that every `subprocess.Popen`, `subprocess.run`, `os.system`, and `pathlib.Path.write_text` call site lives inside a `REGISTERED_TOOLS[x]._run()` body called exclusively from `invoke()`; this structural invariant is enforced by CI grep, not merely by unit tests.
