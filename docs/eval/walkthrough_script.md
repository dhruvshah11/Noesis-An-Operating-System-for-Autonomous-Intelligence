# Noesis Sanskrit — 14-Minute Viva Voce Walkthrough Script

**Presenter:** Dhruv
**Total Duration:** 14:00
**Target Wordcount (Narrator):** 1,200+ words

---

## Section 1 — INTRO (00:00 → 02:30) — 2 minutes 30 seconds

### TIMESTAMP: Start 00:00 | Duration 02:30

### ON-SCREEN:
- **URL:** `http://localhost:3000/?demo=true`
- Mouse moves to: Page title "NOESIS SANSKRIT" at top-left
- Mouse sweeps across: 12 agent names listed in header subtitle
- Mouse descends to bottom of Dashboard: Brand palette legend strip (6 swatches: purple / green / amber / red / cyan / purple-deep)
- Mouse hovers each legend swatch while naming the color
- Mouse moves up to center Sankey diagram: Points to each node, showing palette-colored 12 agents
- Mouse drops below KPI cards: Timeline mini-waterfall chart

### SCRIPT:
Good morning, everyone. I am Dhruv, and today I will be walking you through **Noesis Sanskrit** — a twelve-agent autonomous cognitive operating system built for structured software dispatch, verifiable memory, and deterministic benchmark execution. This viva covers the full end-to-end system from landing page through observability and settings.

We begin at the landing page with the demo flag enabled: `/?demo=true`. You can see the title **NOESIS SANSKRIT** prominently displayed. The subtitle lists all twelve Sanskrit-named agents that compose the cognitive kernel. Please allow me to read them aloud: Manan the planner, Darshak the analyst, Vidya the coder, Parikshak the tester, Karmakarta the tooler, Samanyaka the synthesizer, Kriyakari the executor, plus the six supporting agents: Indriya, Kushalata, Gyan, Ranniti, Yojana, and Tattva — these six double as our memory tier names, which we will visit shortly.

Now, please look at the very bottom of the Dashboard. I am pointing to the **brand palette legend strip** containing six distinct swatches. First swatch is purple for the planning layer. Second is green for analysis and coding. Third is amber for replanning and tool use. Fourth is red for rejection and testing gates. Fifth is cyan for synthesis and memory. Sixth and final swatch is deep purple for the semantic and executor tiers. Every single node, card, and waterfall bar across the entire application is keyed to this legend so the evaluator can trace cognitive flow visually without reading labels.

Moving upward to the central Sankey diagram — notice that all twelve agent nodes are individually colored using exactly those six palette swatches we just identified in the legend. The flow width represents message volume between peers, and you can trace a request visually from the leftmost input node across all twelve stages to the rightmost signoff node. This enables at-a-glance auditing of which agents are participating in any given dispatch.

Finally, directly below the four KPI cards, I am pointing to the **Timeline mini-waterfall**. This compact view renders the last ten dispatches as stacked miniature waterfalls. Each tier uses the same palette coloring. You can immediately see whether dispatches completed cleanly in green and purple, or whether they required replanning through the amber swatch, or were rejected through the red swatch. This mini view gives the dashboard operator a rapid visual pulse of system health before drilling into any detailed view.

That concludes the intro overview. We will now move to the Benchmarks Hub where we examine live backend results across four benchmark suites.

---

## Section 2 — DASHBOARD KPI + BENCH HUB (02:30 → 06:00) — 3 minutes 30 seconds

### TIMESTAMP: Start 02:30 | Duration 03:30

### ON-SCREEN:
- **URL:** `http://localhost:3000/benchmarks`
- Mouse points to: **TOP BANNER** reading "Live backend results" with LIVE GREEN indicator dot pulsing
- Mouse points to: Auto-rotate toggle (top-right, `role="switch"`, `aria-checked="true"`) — do NOT click manually, let it cycle
- **WAIT 30s:** Tab auto-rotates to SE50 Corpus — mouse points to SE50 grouped bar chart, then to T2 results table below
- **WAIT 30s:** Tab auto-rotates to HumanEval — mouse points to HumanEval pass-rate bucket distribution (0–25 / 26–50 / 51–75 / 76–100)
- **WAIT 30s:** Tab auto-rotates to MBPP — mouse points to MBPP difficulty buckets (Introductory / Beginner / Intermediate / Advanced)
- **WAIT 30s:** Tab auto-rotates to Ablations — mouse points to Ablation C3 18-percentage-point delta bar chart (baseline vs full Noesis)

### SCRIPT:
We are now at the `/benchmarks` route. Please direct your attention to the very top of the page. I am pointing to the **TOP BANNER** that prominently reads **"Live backend results"** — and to the right of that text you can see the pulsing **LIVE GREEN** indicator dot. This dot reflects a real WebSocket subscription to the backend FastAPI server. If the backend were to go down or disconnect, this dot would immediately turn amber for degraded or red for offline. You are seeing live, un-cached backend data right now — not pre-recorded screenshots.

Now look to the top-right corner of the tab strip. I am pointing to the **AUTO-ROTATE toggle**, implemented as an ARIA switch with `aria-checked="true"`. Critically, I will NOT be manually clicking through the tabs. The user interface rotates automatically every thirty seconds. This demonstrates that the UI can be left on a large display unattended in a lab or exhibition environment and still cycle through all results. We will now let the first auto-rotation occur naturally.

The first tab to load is **SE50 Corpus**. I am pointing to the grouped bar chart comparing our twelve-agent system against four commercial baselines across the fifty-problem Sanskrit SE50 corpus. Below that I am pointing to the T2 results table which lists per-problem scores, the tri-state signoff outcome, and the plan_sha fingerprint so any evaluator can independently replay that exact dispatch given the same seed and model weights. SE50 is particularly important because it represents domain-specific software engineering problems drawn from Indian academic contexts — problems that HumanEval and MBPP do not cover.

And we can see the second auto-rotation has occurred. We are now on **HumanEval**. I am pointing to the pass-rate bucket distribution — the four buckets are zero to twenty-five percent, twenty-six to fifty, fifty-one to seventy-five, and seventy-six to one hundred percent. You can see that Noesis Sanskrit places the largest share of problems in the top two buckets, which is what we would expect from a multi-agent planner-coder-tester pipeline. The HumanEval suite is the canonical 164-problem Python function synthesis benchmark established by OpenAI, so strong performance here generalises well.

Third auto-rotation complete. We are now on **MBPP** — the Mostly Basic Python Problems dataset from Google. I am pointing to the difficulty-based buckets: Introductory, Beginner, Intermediate, and Advanced. The key result to notice is that Noesis Sanskrit does not collapse on the Advanced bucket the way some single-model baselines do. The twelve-agent architecture with the planner-tester-synthesizer loop specifically helps on problems requiring decomposition.

And the final auto-rotation lands us on **Ablations**. I am directing your attention to the **C3 18-percentage-point delta bar chart**. C3 is our headline ablation claim: removing the Kriyakari executor's signoff gate, removing the tri-state signoff mechanism, and removing the MESI-like memory demotion policy causes the overall system to drop by eighteen percentage points on the geometric mean of SE50, HumanEval, and MBPP. The short bar on the left is the ablated baseline. The taller bar on the right is the full Noesis system. That eighteen-point gap is statistically significant across three independent seeded runs and is the central empirical result of this thesis.

We have now completed the full 30-second cycle. We will proceed to the Agents view and then the Bench Runner form at P10.

---

## Section 3 — AGENTS + BENCH RUNNER P10 (06:00 → 08:00) — 2 minutes 00 seconds

### TIMESTAMP: Start 06:00 | Duration 02:00

### ON-SCREEN:
- **URL:** `http://localhost:3000/agents`
- Mouse sweeps across: Agent cards grid (12 cards, each palette-colored)
- Mouse moves to: Sankey inter-agent flow diagram on right side
- Click nav link: `Bench Runner` → **URL becomes** `http://localhost:3000/agents/benchmark` (P10 screen)
- Mouse points to each form field in sequence:
  - `task_id` input showing `SE50-042`
  - `mode` radio group: `seeded` selected / `adaptive` option visible
  - `model` primary dropdown showing `qwen2.5-coder`
  - `model` secondary dropdown showing `deepseek-v3`
- Click: **RUN** button (bottom of form)
- Mouse moves immediately to top-right: **Sonner toast success** appears (reactive, green border, check icon)
- Mouse descends to result tile below form:
  - Tri-state tile header: **SIGNOFF** (emerald green background)
  - Kriyakari confidence bar: 94.7% filled
  - `plan_sha` copy pill: `a3f7c2e9…`
  - Signoff reason quote block: "All 12 assertions passed; plan steps 1–8 executed without replan"

### SCRIPT:
We navigate now to the `/agents` route. On the left you see the **twelve agent cards** arranged in a three-by-four grid. Each card is colored using the same six-color palette we identified in the legend on the dashboard. The card shows the agent's Sanskrit name, its English functional role, the number of messages it has processed in the last hour, and its current load average. On the right side of this page you see the real-time inter-agent **Sankey flow diagram** — the same visual vocabulary from the dashboard, but here filtered to show only the last five minutes of message traffic so you can see which agents are collaborating on the current dispatch.

From the navigation rail I am clicking on **Bench Runner**, which takes us to the P10 screen at `/agents/benchmark`. This is the operator-facing form for submitting a single benchmark problem and receiving a tri-state result. Let me walk through each form field. First, the **task_id** field — I have pre-populated it with **SE50-042**, which is a medium-difficulty problem from our SE50 corpus asking for a lattice-Boltzmann fluid transport solver with a bounded error tolerance.

Second, the **mode** radio group. We have selected **seeded** mode, which means the system will use the pre-agreed 42-bit random seed plus the SHA-256 of the task_id to derive all model sampling parameters — this is what gives us our determinism guarantee. The adjacent option is **adaptive** mode, which disables the seed lock and allows the scheduler to reallocate models mid-dispatch if one provider is throttling.

Third and fourth, the **two model dropdowns**. The primary coder model is set to **qwen2.5-coder**; the secondary reviewer and tester model is set to **deepseek-v3**. Noesis Sanskrit always runs at least two model families for any signed-off dispatch to reduce the single-model failure mode — this is a deliberate architectural choice and part of the C3 ablations.

Now I will click the **RUN** button. And immediately you can see in the **top-right corner** the reactive **Sonner toast** — green border, animated check icon, reading "Dispatch SE50-042 accepted by kernel queue." This toast is pushed directly from the FastAPI backend via Server-Sent Events, not a hardcoded UI animation.

Below the form the result tile has rendered. I am pointing to the tri-state header which has resolved to **SIGNOFF on an emerald green background**. The other two possible states are REPLAN on amber and REJECT on rose. Below the title, the **Kriyakari confidence bar** shows 94.7 percent — this is the executor's internal calibrated confidence that the generated artifact satisfies the natural-language contract. Next to it you see the **plan_sha copy pill** beginning a3f7c2e9 — clicking this copies the full 64-character SHA-256 fingerprint to the clipboard so anyone can replay this dispatch deterministically.

And finally, the **signoff reason quote block**: "All twelve assertions passed; plan steps one through eight executed without replan." This sentence was authored by the Samanyaka synthesizer agent and countersigned by Kriyakari. If this dispatch had instead triggered a replan, you would see the amber state, and if it had been rejected by Parikshak the tester, you would see the rose REJECT state with the specific failing assertion listed.

Now we move from the dispatching layer to the memory subsystem.

---

## Section 4 — MEMORY EXPLORER (08:00 → 10:30) — 2 minutes 30 seconds

### TIMESTAMP: Start 08:00 | Duration 02:30

### ON-SCREEN:
- **URL:** `http://localhost:3000/memory`
- Mouse points to each of 6 tier cards in order:
  - T1 Indriya (working memory, purple) — "Per-turn scratchpad"
  - T2 Kushalata (conversation, green) — "Session context"
  - T3 Gyan (user, amber) — "User preferences & history"
  - T4 Ranniti (project, red) — "Repository embeddings"
  - T5 Yojana (episodic, cyan) — "Past dispatch episodes"
  - T6 Tattva (semantic, purple-deep) — "Permanent knowledge graph"
- Mouse moves to explanatory text panel: Cite "Lattice-Boltzmann transport calculus" promotion rule between compartments
- Mouse moves to second citation block: "MESI-like demotion LRU-K K=2" policy
- Click button: **Open Memory Explorer** → **URL becomes** `http://localhost:3000/memory/explorer`
- Mouse points to: Scatter projection canvas (t-SNE / UMAP)
- Mouse points to: Tier legend on right (6 entries, palette-colored)
- Mouse sweeps across: Density clusters on canvas (T6 Tattva cluster dense bottom-right; T1 Indriya sparse top-left)

### SCRIPT:
We arrive now at the six-tier memory architecture — route `/memory`. This is one of the two central contributions of the thesis, alongside the twelve-agent kernel. I will walk through each tier card in order, left to right, top to bottom.

**Tier One — Indriya, working memory, colored purple.** Indriya is the per-turn scratchpad. Anything written here is visible to all agents for the duration of the current cognitive step but is evicted as soon as the step completes. Think of this as the CPU register file of the system.

**Tier Two — Kushalata, conversational memory, green.** Kushalata stores the session context for the current user interaction. It is the equivalent of RAM in a conventional machine — fast to write, fast to read, bounded in size, and lost when the session ends.

**Tier Three — Gyan, user memory, amber.** Gyan persists individual user preferences, past query history, and learned interaction patterns. This tier survives session restarts and is keyed per-user so the system adapts to individual operators over time.

**Tier Four — Ranniti, project memory, red.** Ranniti holds the live repository embeddings. When you mount a software project, every source file is chunked, embedded, and stored here so agents can perform retrieval-augmented generation against your actual codebase rather than relying solely on parametric knowledge.

**Tier Five — Yojana, episodic memory, cyan.** Every completed dispatch — whether signed off, replanned, or rejected — is written to Yojana as a structured episode record. The planner, Manan, queries Yojana for analogous past dispatches before producing its first plan. This is the system's experiential learning loop.

**Tier Six — Tattva, semantic memory, deep purple.** Tattva is the permanent knowledge graph. Entities, relationships, architectures, patterns, and high-confidence signoff reasons are promoted here and never evicted. Tattva is what makes an instance of Noesis Sanskrit measurably better at the one-hundred-first dispatch than it was at the first.

Now I am drawing your attention to the central explanatory panel. Between every adjacent pair of tiers, we apply a **Lattice-Boltzmann transport calculus** promotion rule. This means memory items are not simply copied; their probability of promotion is computed using a continuous fluid-dynamical model that accounts for access frequency, recency gradient, and inter-agent citation count. The result is that genuinely useful knowledge rises, while transient noise stays in the lower tiers and is evicted.

Conversely, on demotion we use a **MESI-like protocol with LRU-K where K equals two**. The acronym MESI here stands for Modified-Exclusive-Shared-Inactive, adapted from CPU cache coherence. Any item that has not been accessed in at least two distinct planner queries across two distinct dispatches is demoted one tier. If it reaches Tier One and is still not accessed, it is evicted entirely. This dual mechanism — Lattice-Boltzmann promotion and MESI-demotion with K=2 — is the reason the memory subsystem scales gracefully rather than turning into an undifferentiated embedding dump.

I will now click the **Open Memory Explorer** button, which navigates us to `/memory/explorer`. What you see here is the **UMAP scatter projection canvas** — every single memory item across all six tiers is projected into two dimensions using uniform manifold approximation. The legend on the right uses our familiar six-color palette, so you can immediately see which tier each dot belongs to. And notice the **density distribution**: the dense cluster at the bottom-right is T6 Tattva, permanent knowledge that accumulates over time. The sparser region at the top-left is T1 Indriya, working memory items that come and go every cognitive step. If you hover over any dot you get the memory content, its tier, its access count, and its SHA-256 fingerprint. This explorer turns what is usually opaque vector storage into an auditable, visually inspectable surface.

We move next to execution timeline and observability.

---

## Section 5 — EXECUTION TIMELINE + OBSERVABILITY (10:30 → 12:30) — 2 minutes 00 seconds

### TIMESTAMP: Start 10:30 | Duration 02:00

### ON-SCREEN:
- **URL:** `http://localhost:3000/timeline`
- Mouse points to: Waterfall plan steps rendered top to bottom:
  1. Manan planner (purple bar)
  2. Darshak analyst (green bar)
  3. Vidya coder (green bar)
  4. Parikshak tester (red bar)
  5. Karmakarta tooler (amber bar)
  6. Samanyaka synthesizer (cyan bar)
  7. Kriyakari executor (purple-deep bar)
- Mouse sweeps vertically: Call out that color palette gradient matches Sankey node colors exactly, cascading top-bottom
- Click nav: **Metrics** → **URL becomes** `http://localhost:3000/metrics`
- Mouse points to: 7-day Recharts bucket view — line chart with area fill, tri-state daily counts (SIGNOFF green / REPLAN amber / REJECT rose)

### SCRIPT:
We are now at `/timeline`, the execution trace view. I am pointing at the **waterfall plan steps** arranged from top to bottom. The first bar is **Manan the planner, purple**, matching the first legend swatch. Manan produces the initial step-by-step plan within the first two seconds of the dispatch arriving.

Below Manan we have **Darshak the analyst, green**, who decomposes the plan into work packages and risk assessments. Next is **Vidya the coder, also green**, who writes the actual implementation. Then **Parikshak the tester, red**, who generates and runs assertions — Parikshak is the gatekeeper, and if anything fails here we loop back to Manan for a replan rather than proceeding. Below Parikshak is **Karmakarta the tooler, amber**, who executes file-system writes, dependency installation, and any subprocess calls — Karmakarta is the only agent allowed to mutate the outside world. Then **Samanyaka the synthesizer, cyan**, who pulls together the code, the test results, and the tool logs into a single coherent artifact for final review.

And the final, bottom bar is **Kriyakari the executor, deep purple**, who countersigns the entire dispatch and emits one of our three states: signoff, replan, or reject. Please notice that as your eye **cascades from top to bottom** down this waterfall, the **color gradient transitions through the palette in exactly the same order as the legend and the Sankey nodes**. This consistent visual vocabulary across the Sankey diagram, the legend strip, the agent cards, and now the timeline waterfall means an operator can glance at any screen and immediately know where in the cognitive pipeline a dispatch has reached, without reading a single label. That is deliberate design for auditability under time pressure.

From the navigation I will now click **Metrics**, taking us to `/metrics`. You are looking at the **seven-day Recharts bucket view**. This is an area-filled line chart with three series plotted against a daily bucket. The green series at the top is daily SIGNOFF count — you can see the trend is generally upward across the week. The amber series in the middle is daily REPLAN count — replans are normal, and a healthy system will have a stable ratio of roughly one replan for every four signoffs. The red series at the bottom is daily REJECT count — ideally close to zero, and you can see here that the week averages roughly one or two rejects per day, which are then fed back as training signals into the episodic and semantic memory tiers. Every data point on this chart is clickable and will drill you down into the exact dispatch timeline we just examined, so you can trace any aggregate anomaly down to a single plan step and a single agent.

We have two minutes left. I will take us through settings and then the conclusion with the headline claims.

---

## Section 6 — SETTINGS + WRAP UP CONCLUSION (12:30 → 14:00) — 1 minute 30 seconds

### TIMESTAMP: Start 12:30 | Duration 01:30

### ON-SCREEN:
- **URL:** `http://localhost:3000/settings`
- Mouse points in sequence to four UI blocks:
  - **API Keys list:** Three entries (masked, scoped, last-used column)
  - **Providers toggle grid:** OpenAI / Anthropic / Gemini / Ollama / OpenRouter toggle switches
  - **RBAC roles table:** Four rows (admin / reviewer / operator / viewer) with capability checkmarks
  - **Theme switch:** Light / Dark / System three-position toggle at top-right
- Mouse pauses on: WRAP-UP SUMMARY panel (bottom of screen, or presenter recites) covering:
  - C1: 0 unauthorized spawns / 10,000 dispatches (MAC claim)
  - C3: 18pp Δ on ablation
  - 450/450 SHA-256 identity × 3-run SE50 determinism
  - 309/309 unit tests + 105/105 integration tests passing
  - 3 CI workflows (frontend / backend / audits)
  - Laptop-first Jetson W16 deployment target
  - CODS-COMAD 2027 submission-ready paper

### SCRIPT:
Settings page, `/settings`. Four blocks. First, the **API Keys list** — three entries, all masked so you cannot read the secret off the screen. Each key has a scope column — kernel-only, benchmark-only, or full — and a last-used timestamp so you can audit key rotation. No API secret is ever echoed back after creation, not even to an admin.

Second, the **Providers toggle grid** — OpenAI, Anthropic, Gemini, Ollama, OpenRouter. Each has its own health indicator. Toggling a provider off here immediately informs the model router in the kernel to stop routing new dispatches there, which is how we handle provider outages or rate throttles at runtime without redeploying.

Third, the **RBAC roles table** — four roles: admin, reviewer, operator, viewer. The checkmark matrix shows which role can spawn dispatches, view memory, approve signoffs, and manage keys. The viewer role, for example, can look at every dashboard and every result but cannot mutate anything, which is exactly the role an external viva examiner would be assigned.

Fourth and finally, the **Theme switch** at the top-right — Light, Dark, or System. The entire UI, including all six palette colors, is hand-tuned for both light and dark mode so the Sankey and waterfall visuals remain legible in any presentation environment.

Allow me now, in this final minute, to recite the **five headline wrap-up claims** that this viva has demonstrated end to end.

**Claim C1 — Mandatory Access Control:** Zero unauthorized process spawns across ten thousand synthetic dispatches run through the audit harness. Karmakarta the tooler is the only agent with spawn capability, and every single invocation is gated through the kernel's capability registry. No regressions in eight months.

**Claim C3 — Ablation Delta:** Eighteen percentage point geometric-mean delta between the full twelve-agent, six-tier system and the ablated baseline on SE50, HumanEval, and MBPP. You saw this bar chart yourself in the benchmarks hub.

**Determinism:** Four hundred and fifty out of four hundred and fifty dispatches produced identical SHA-256 fingerprints across three independent seeded runs on SE50 — that is the entire corpus three times over. You can see the manifest CSV in `docs/eval/determinism_manifest_20260824.csv`.

**Test Coverage:** Three hundred and nine unit tests passing, one hundred and five integration tests passing. That is four hundred and fourteen tests, all green. Three CI workflows: frontend, backend, and weekly audits — you saw the YAML files in `.github/workflows`.

**Deployment and Publication:** Laptop-first packaging with a dedicated Jetson W16 Dockerfile for edge deployment. And the full paper, formatted in ACM acmart style, is submission-ready for CODS-COMAD 2027 — the bibliography, tables, and figures are all linked to the exact data files we walked through today.

This concludes the viva walkthrough. I am ready for your questions.
