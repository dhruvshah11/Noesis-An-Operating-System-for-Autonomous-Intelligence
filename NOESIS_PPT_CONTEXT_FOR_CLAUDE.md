================================================================================
NOESIS — MAJOR PROJECT SYNOPSIS PPT DECK: COMPLETE CONTEXT FILE FOR CLAUDE
================================================================================
AUTHOR: Dhruv Shah (@dhruvshah11) · Final Year B.Tech / B.E. Capstone
FORMAT TO PRODUCE: Markdown → then Claude can convert to /save as .pptx or to
Marp/DeckDeckGo/Google Slides markdown that Dhruv can export to PPTX.
VISUAL MANDATE: Strictly match the 2 reference slides Dhruv already uploaded —
                deep navy #0b0f1a background, grid-dotted work surfaces, purple
                sapphire #6E56CF primary accent, mint green #22c55e success,
                amber #f59e0b warn, red #ef4444 danger, rounded 12px cards with
                1px white/5 borders and soft drop shadows, ALL sanskrit
                codenamed agent and memory tiers exactly as in the ref images.

================================================================================
(1) EXPLICIT INSTRUCTIONS FOR YOU, CLAUDE, READ FIRST
================================================================================

You are producing Dhruv Shah's FINAL-YEAR MAJOR PROJECT SYNOPSIS PPT.
The audience is a capstone viva panel (3-4 Indian university professors,
electronics/computer science dept — 14–18 minute talk + 5 min Q&A).

MANDATORY RULES — VIOLATE NONE:

A) DECK LENGTH: Exactly 17 content slides + 1 cover + 1 thank-you/Q&A = 19 slides.
B) VISUAL LOCK: Match the EXACT aesthetic of the 2 uploaded reference slides:
   - Dark navy background #0b0f1a (NOT pure black), subtle 60px dot-grid
     (#ffffff04) layered over background on every slide except title slide;
   - Deep purple sapphire brand primary: #6E56CF; Hover/Highlight purple: #8b5cf6
   - Secondary blue: #3b82f6; Mint success: #22c55e; Amber warn: #f59e0b; Red: #ef4444
   - Typography: Display headers = "Space Grotesk Bold 700" (28pt slide titles),
     body = "Inter 400 Regular 14pt", tables/code = "Fira Code 12pt"
   - Cards: 12px border-radius, 1px solid #ffffff0a, box-shadow:
     0 4px 24px -2px #000000aa, inset 0 1px 0 #ffffff06
   - Slide chrome: 40px purple top-border accent 2px, 1px bottom rule,
     "NOESIS" top-left slide watermark 10pt uppercase semi-bold #ffffff60,
     slide number top-right same style + Dhruv's capstone batch.
C) USE SANSKRIT AGENT/TIER NAMES EXACTLY as Dhruv's reference slide uses them.
   DO NOT use the earlier English-only agent names from the code repo —
   the presentation rebrands them to Sanskrit for the viva (makes the project
   feel more distinctive, ties to the Greek "Noesis / Nous" etymology).
   See §(5) below for the full 12-agent + 6-tier Sanskrit codename tables.
D) SPEAKER NOTES: 4–6 BULLETED LINES PER SLIDE under a `Speaker Notes:`
   section. Dhruv will memorize these — they must be ready for viva delivery.
E) CITE SOURCES IEEE-style [1]–[8] superscript inline on Literature Survey and
   Methodology slides. References section at slide 17.
F) DO NOT make up "results numbers" — every number must come verbatim from §(6).
G) Dhruv uploaded 2 HIGH-FIDELITY REFERENCE SLIDES as attachments:
   • Ref Slide A = "NOESIS KERNEL ARCHITECTURE" overview (left innovations column
     + center 3-block kernel + right workflow/security/deployment + 4 bottom tables)
     → You will RECREATE THIS EXACT LAYOUT for SLIDE 8 verbatim (same col widths,
       same 6 left-side Key Innovations checkmarks, same 3x3 center kernel,
       same 4 bottom Testing/Evaluation/Deliverables/Repos tables).
   • Ref Slide B = "NOESIS STUDIO DASHBOARD" (dark Next.js UI with sidebar,
     live status top-right pills, active workflow graph, I/O/code/logs/metrics
     footer quadrants) → Use this as visual source for SLIDE 10 (Dashboard mock).
H) OUTPUT: A single complete deck written in DECK.MD / MARP-compatible markdown
   syntax, with HTML/CSS inlines where needed to match colors. Use MARP front
   matter `---\nmarp: true\ntheme: gaia\n---` and override CSS with <!-- style:
   --> blocks so Dhruv can paste the deck into https://demo.marp.app and export
   to PPTX directly.

================================================================================
(2) PROJECT IDENTITY (title, subtitle, author, uni placeholders, 17-slide index)
================================================================================

--- HEADER BLOCK for every slide's footer watermark row (2 lines each slide) ---
LEFT footer tiny 10pt:  NOESIS — Final Year Major Project, 2026 Batch
RIGHT footer tiny 10pt: Dhruv Shah · Dept of __________________ · Enrl: ________

17 SLIDE INDEX — YOU WILL PRODUCE EACH VERBATIM IN ORDER:
 Slide | Title
-------|--------------------------------------------------------------
   0   | 🟪 COVER / TITLE SLIDE (centered, logo + Sanskrit subtitle)
   1   | Agenda / Roadmap (16 points mapped to remaining slides)
   2   | Problem Statement (4 critical gaps in LangChain/AutoGen/CrewAI)
   3   | Motivation & Why Now (LLM commoditization → kernelization gap)
   4   | Objective (Primary + Secondary — copy from §7 verbatim)
   5   | Literature Survey / Related Work (8 papers, 4-col comparison table)
   6   | Research Contributions & Novelty (C1, C2, C3 — bold)
   7   | Design Principles (6 OS-inspired maxims + 3-tiered kernel diagram)
   8   | ⭐ NOESIS KERNEL ARCHITECTURE OVERVIEW (verbatim Ref Slide A layout!)
   9   | 12-Agent Typed Roster Deep Dive (2x6 grid, Sanskrit codenames + roles)
  10   | ⭐ NOESIS STUDIO Dashboard Mockup (Ref Slide B visual copy layout)
  11   | Νόησις Six-Tier Memory Hierarchy (T1–T6 Sanskrit names, retention matrix)
  12   | Security Model — Capability-Based MAC (AND-Mask Mint, deny-first)
  13   | Testing Strategy & Evaluation Plan (3 tracks table)
  14   | Deployment Target — NVIDIA Jetson Orin Nano (cost, perf, power draw TCO)
  15   | Project Timeline / Gantt (14 weeks, color coded)
  16   | Expected Outcomes, Future Roadmap M8–M11, Limitations
  17   | References (8 entries IEEE format) + Acknowledgements
  18   | ❔ Q&A / Thank You (single line: νους — "Intellect through Reason")

================================================================================
(3) BRAND PALETTE — LOCKED COLORS FOR ALL SLIDES (use hex codes)
================================================================================

Token               Hex        Usage
-----------------   --------   ------------------------------------------------
--bg-0              #070b14    Slide base (deeper than grid bg)
--bg-1              #0b0f1a    Content card base
--bg-2              #111827    Section block bg (KPI tiles, tables headers)
--grid-dot          #1a2033    60px × 60px dotted background noise
--brand-purple      #6E56CF    Primary (borders, title underlines, active pills,
                               completed workflow node border)
--brand-purple-2    #8b5cf6    Hover/gradient end stop (logo gradient top)
--brand-purple-3    #b29bff    Purple glow (kernel block header text)
--brand-blue        #3b82f6    Routes / HTTP verbs / Tertiary accent / links
--brand-cyan        #06b6d4    Memory tier icons / memory explorer chips
--mint              #22c55e    Status: PASS / Healthy / Completed node check
--amber             #f59e0b    Status: WARN / In Progress / waiting node
--red               #ef4444    Status: FAIL / Reject / PermissionDenied box
--ink-100           #f3f4f6    Main body
--ink-400           #9ca3af    Secondary text / footer watermarks
--ink-600           #4b5563    Tertiary metadata / timestamps
--white-5           #ffffff0a  Card border 1px solid
--white-3           #ffffff05  Divider rule / inner inset border
--shadow-lg         0 4px 24px -2px rgba(0,0,0,.7), inset 0 1px 0 rgba(255,255,255,.04)
--shadow-md         0 2px 10px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.03)

LOGO: 512x512 "NOESIS" wordmark using a 6-edge convex polyhedron wireframe
(geodesic dome / nous-orb glyph) to the left of word "NOESIS" Space Grotesk
700 48pt white. The glyph uses 2-color stroke #6E56CF→#06b6d4 purple-cyan
gradient. Top-right corner of logo has a tiny Greek "Νόησις" 9pt subtitle.

================================================================================
(4) SANSKRIT CODENAME DICTIONARY — LOCKED. DO NOT DEVIATE FROM THESE NAMES.
================================================================================

The reference slides use Sanskrit codenames (chosen for the etymological link
between Greek "νόησις" = thinking / Sanskrit "मनन" = reflection). You MUST use
these codenames everywhere — in architecture diagram, roster slide, workflow
graph, even inside code snippets. Match the parenthesized format:
"EnglishName (SanskritCodename)".

--- 12-AGENT ROSTER (2x6 grid on Slide 9) ---
Slot  AgentClass         Sanskrit   Role / Responsibility
----  ----------------   --------   ------------------------------------------
 1    PlannerAgent       Manan      Goal decomposition · 12-step DAG map
 2    AnalystAgent       Darshak    Intent parsing · risk map · constraints
 3    CoderAgent         Vidya      Code synthesis · diff · migrations
 4    TesterAgent        Parikshak  Unit + integration tests · pytest runner
 5    ToolerAgent        Karmakarta Shell · file IO · vendor API invocations
 6    ResearcherAgent    Anveshak   Multi-source RAG synthesis + citations
 7    CriticAgent        Vivechak   5-axis quality rubric scoring
 8    MemoryAgent        Paalak     Tier promotion · eviction · persistence
 9    SecurityAgent      Rakshak    Prompt injection scan · capability audit
10    SynthesizerAgent   Samanyakā  Consolidates multi-agent outputs
11    ExecutorAgent      Kriyakārī  Tri-state signoff: {Sign-Off / Reject / Replan}
12    SupervisorAgent    Nirikshak  Spawn-tree · AND-Mask subtoken minting
 (orchestrator sits ABOVE these 12 · join policy engine)

--- 6 MEMORY TIERS (Slide 11) ---
Tier  Name (Sanskrit)   English       Typical size  Retention  Backing
----  ----------------  ------------  ------------  ---------  --------
 T6   Transcendent      Long-term     < 1% hot      Years      S3 / tar.gz immutable
      (Tattva)          Wisdom
 T5   Strategic         Episodic       5% hot       Quarters   Qdrant + Graph (Neo4j)
      (Yojana)          Projects
 T4   Tactical          Working        15% hot      Weeks      SQLite Structured-JSON
      (Ranniti)         Memory
 T3   Semantic          Facts /        40% hot      Months     Qdrant vector DB
      (Gyaan)           Concepts
 T2   Procedural        Skills /       30% hot      Months     Redis + Local FS
      (Kushalata)       Routines
 T1   Sensory           Raw IO /       100% hot     Minutes    Ring buffer (mem)
      (Indriya)         Events

================================================================================
(5) VERBATIM TEXT BLOCKS — COPY-PASTE THESE DIRECTLY INTO SLIDES. NO REWORDS.
================================================================================

==(SLIDE 0 COVER)==
# NOESIS
## An Operating System Kernel for Autonomous Multi-Agent Intelligence
### *"νόησις — Intelligence through Reason"*
#### Final Year Major Project Synopsis · 2025–2026
Department of ________________________
__________________________ University
Presented by: **Dhruv Shah**  ·  Enrollment No. _______________
Project Guide: **Prof. ________________________**
Viva Date: ________________ 2026

==(SLIDE 1 AGENDA)==
# Roadmap
1.  **Problem Statement** — The 4 unpatched gaps in today's agent frameworks
2.  **Motivation & Why Now** — LLM commoditization → kernelization is the next step
3.  **Objective** — Primary & secondary capstone goals
4.  **Literature Survey** — 8 papers & 4-framework comparison
5.  **Novelty & 3 Core Contributions (C1/C2/C3)**
6.  **Design Principles** — 6 OS-inspired engineering maxims
7.  **⭐ Kernel Architecture Overview** (Ref Slide A layout)
8.  **12-Agent Typed Roster Deep-Dive** (Sanskrit codename grid)
9.  **⭐ Noesis Studio Dashboard Mockup** (Ref Slide B layout)
10. **Νόησις 6-Tier Memory Hierarchy** (promotion matrix)
11. **Security Model: Capability-Based MAC** (AND-Mask spawn minting)
12. **Testing + Evaluation Plan** (3 tracks)
13. **Deployment: Jetson Orin Nano — Cost / Performance / TCO**
14. **14-Week Gantt Timeline**
15. **Expected Outcomes + Future Roadmap M8→M11**
16. **References & Acknowledgements**
17. **Q&A**

==(SLIDE 2 PROBLEM STATEMENT)==
# Problem Statement: 4 Unpatched Gaps
## Every mainstream agent framework fails 4 systems tests

| Gap | Root failure | Real-world consequence |
|:---:|---|---|
| 🧱 **Flat Memory** | Only flat vector-store search exposed. No working/episodic/archive tiering. | Lost-in-the-middle degradation[1] on tasks >16k ctx. Agents forget goals after 12+ steps. |
| 🔒 **Zero Security** | Any agent calls any tool + spawns any child. No gate. | Prompt injection → arbitrary shell, exfil of codebase to 3rd-party APIs. No enterprise will deploy[10]. |
| 🎲 **Non-Determinism** | LLM temp>0 + unseeded tool ordering = no reproducibility. | Same goal → wildly differing outputs. Can't audit, can't regression-test → non-compliant for HIPAA/SOX[9]. |
| ♻️ **No Lifecycle** | No kernel-level spawn/join/checkpoint/recovery hooks. | Long-running workflows (100+ step PR, legal discovery) silently die on transient HTTP errors. No resume. |

— *Today's frameworks are prompt-toolkit libraries. **Not operating systems.** — *

==(SLIDE 3 MOTIVATION)==
# Motivation & Why Now
## LLM inference is now a commodity. The next frontier is **systematization.**

3 converging trends make 2026 the correct year for Noesis:
 1. **Commoditized inference.**  Qwen2.5-Coder-7B[7] / DeepSeek-V2-16B[8] run
    locally on <$150 edge silicon for $0.00 in token fees → closed SaaS APIs
    are no longer a moat. The moat is the orchestration kernel.
 2. **Enterprise agent failures.**  74% of Fortune-1000 LLM-agent pilots were
    shelved in 2024 due to prompt-injection and reproducibility failures
    (Gartner, "AI Engineering 2025").
 3. **OS design patterns finally applied to AI.**  Classical Unix has solved
    spawn/join, memory hierarchy, and capability security for 50 years[9][10].
    Noesis lifts these battle-tested primitives → first-class LLM-agent
    abstractions. No prior open framework does all three together.

==(SLIDE 4 OBJECTIVE)==
# Objective
### 🎯 Primary Objective
Design, implement, and evaluate an open kernel substrate for agentic AI
that closes the four critical gaps in §Slide 2: flat memory, un-gated
spawning, non-deterministic execution, and absent agent lifecycle hooks.

### 🎯 Secondary Objectives (measurable, for viva distinction)
(a) Ship a typed 12-agent roster (Manan→Nirikshak) with signed-off
    tri-state Executor (Kriyakārī) gates and Supervisor Nirikshak
    AND-Mask subtoken minting on every spawn.
(b) Demonstrate **≥ +8% pass@1 improvement** on HumanEval[2] and
    **≥ +12% pass@1 improvement** on MBPP[3] code benchmarks when
    comparing the full Noesis 12-agent pipeline against a standalone
    Qwen2.5-Coder-7B[7] baseline.
(c) Native production deployment package for NVIDIA Jetson Orin Nano
    (≈$139 hardware, 7–15 W, 0 token fees forever).

==(SLIDE 5 LITERATURE SURVEY)==
# Literature Survey — Related Work
## 8 sources, tabular comparison

| Ref | Work | Memory Hierarchy | Capability Spawn MAC | Deterministic kernel | Open-Source |
|:---:|---|:---:|:---:|:---:|:---:|
| [1] | Liu, *Lost in the Middle* (ACL 2023) — documents ctx failure modes ✗ partial (prompt-level) ✗ — ✗ Analyzed ctx windows, proposed 2-tier retrieval only | ✗ (analytical only) | ✗ | ✗ | N/A |
| [2] | Chen, *HumanEval* (2021) — established pass@1 metric | ✗ | ✗ | ✗ | benchmark only |
| [3] | Austin, *MBPP* (2021) — 1k entry-level code problems | ✗ | ✗ | ✗ | benchmark only |
| [4] | Jiménez, *SWE-bench* (ICLR 2024) — real GitHub PRs | ✗ | ✗ | ✗ | benchmark only |
| [5] | LangChain v0.3 — industry agent toolkit | ✗ (flat vector only) | ✗ | ✗ non-det prompt chains | ✔ MIT |
| [6] | Microsoft AutoGen — multi-agent negotiation framework | ✗ shared dict only | ✗ | ✗ | ✔ MIT |
| [7] | Qwen Team, Qwen2.5-Coder-7B — target on-device LLM | N/A model only | N/A | N/A | ✔ Apache 2 |
| [8] | DeepSeek-Coder-V2 Lite 1.3B / 16B — secondary baseline | N/A model only | N/A | N/A | ✔ DeepSeek Open RAIL-M |
| [9] | Ritchie & Thompson, *Unix TSS* (1978) — kernel patterns[9] ✔ (7 canonical layers) ✔ (uid/gid) ✔ (fork/join) N/A founding paper | ✔ (canonical) | ✔ (uid/gid) | ✔ (fork/join) | N/A |
| [10] | Miller *Capability Myths Demolished* (HP Labs, 2003) — ✔ (immutable tokens) ✔ (AND-Mask spawn) ✔ N/A capability MAC design pattern[10] | ✔ (tokens) | ✔ (AND-Mask) | N/A | N/A |

**Gap analysis:** Rows [5] and [6] (the industry-standard frameworks) score a
3-column ❌ on memory/MAC/determinism — which this project's 3 contributions C1/C2/C3 close.

==(SLIDE 6 NOVELTY / 3 CONTRIBUTIONS)==
# Novelty & Core Research Contributions
## Three original, verifiable systems contributions

🟣 **C1 — Six-Tier Typed Νόησις Memory Model**
  Noesis formalizes *Sensory (T1) → Procedural (T2) → Semantic (T3) → Tactical
  (T4) → Strategic (T5) → Transcendent (T6)* with typed Pydantic schemas,
  per-tier retention TTLs, and an automatic tier-promotion controller:
  working-memory lines surviving 3 evictions are promoted to episodic with
  SHA-256 provenance hashes. Named for the Greek *νόησις* = *intellection* to
  reflect its cognitive-science grounding (Atkinson-Shiffrin 1968 extended).

🟢 **C2 — Capability-Gated Spawn Model (AgentRoster)**
  Supervisor Nirikshak mints scoped CapabilityTokens on EVERY child spawn
  using a **set-theoretic AND-MASK** against the parent token, not blanket
  inheritance. Spawn-deny paths are first-class typed `PermissionDenied(op,
  target, missing_list)` with explicit unit coverage. Agentic equivalent of
  Linux `seccomp-bpf` syscall filtering[10].

🔵 **C3 — Deterministic Seeded 12-Agent Orchestration**
  All 12 roster agents run as pure functions over a fixed seed; Orchestrator
  enforces `{all, any, majority}` join policies; Judge Vivechak produces
  typed `ranked_candidates[] + tie_flag` tuples; Executor Kriyakārī produces
  a tri-state `{signoff, reject, replan}` gate. **Fixed seed → bit-exact
  reproducibility for audits.** Industry-first property among open frameworks.

==(SLIDE 7 DESIGN PRINCIPLES)==
# Design Principles — 6 OS-Inspired Maxims
## "Kernelize first, optimize later."

1. 🛡️ **Deny-First Security**  No operation is permitted by default. Every
   spawn/tool-call requires an explicit `Capability(CapabilityOp.X, target)`
   entry in the token — seccomp-bpf for agents[10].
2. 🔍 **Everything Observable**  All transitions emit typed audit events.
    No opaque LLM prompt-chains.
3. 🧱 **Separation of Concerns**  Each agent has exactly ONE typed report
    schema. No monolithic "catch-all" JSON blobs. 12 agents = 12 reports.
4. 💾 **Promotion, Not Eviction**  Memory never disappears; it gets
    tier-promoted. A T1 (Sensory) event that survives 3 cycles → T4 (Tactical).
5. 🎲 **Determinism Default-ON**  Pure-Python seeded execution for tests and
    replay; LLM calls are a *Strategy plugin* that can be swapped out (or
    disabled entirely) without kernel changes.
6. 🪜 **Protocol Before Implementation**  Universal Agent Protocol v1
    (Protobuf contract) defines every wire format **before** any agent code
    is written. Clients can be rewritten in Rust/Go without backend changes.

==(SLIDE 8 KERNEL ARCHITECTURE)==
# NOESIS — Kernel Architecture Overview
## [RECREATE REF SLIDE A LAYOUT EXACTLY HERE — 4-COLUMN TABLE]

Use the EXACT layout and copy from Dhruv's uploaded "KERNEL ARCHITECTURE" image.

COLUMN 1 (left sidebar, 14% width, purple glow):
  ▼ KEY INNOVATIONS (8 checkmarks):
    ✅ Typed 12-Agent Roster
    ✅ Six-Tier Νόησις Memory Hierarchy
    ✅ Capability-based MAC for Agent Spawning
    ✅ Deterministic Fixed-Seed Execution
    ✅ Workflow Orchestrator with All/Any/Majority
    ✅ OpenAPI 3.1 Contracts
    ✅ 256 Passing Pytest Tests
    ✅ Jetson Orin Nano Edge Deployment

  ▼ TECH STACK (below Innovations, small cards):
    • Backend Kernel:   Python 3.12+
    • Frontend Studio:  Next.js 14 + TypeScript · React
    • Database/Memory:  SQLite  ·  Qdrant  ·  Redis
    • LLM/Inference:    OpenAI / Ollama / vLLM (Local + Edge)
    • Infra/Deployment: Docker  ·  NVIDIA Jetson Orin Nano

CENTER PANEL (60% width, nested 3-tiered kernel):
  LAYER 5: USER → 6-icon Noesis Studio strip → OpenAPI 3.1 → HTTP/WebSocket
  LAYER 4: DETERMINISTIC ORCHESTRATOR bar — 5 subpill icons:
           DAG Executor · Join Policies · Fixed-Seed RNG · Replay & Audit · Event Bus
  LAYER 3: 3 adjacent cards 33/33/33% width:
           LEFT (green-mint gradient border): CAPABILITY KERNEL (MAC)
                 5 rows: CapabilityToken(Typed) · AND-Mask Spawn Minting ·
                 Deny-First Policy · PermissionDenied(op,target,missing_list) ·
                 Audit Log Immutable
           CENTER (purple border): 12-AGENT ROSTER (TYPED)
                 3×4 numbered grid with Sanskrit codenames in each cell
           RIGHT (blue border): MEMORY CONTROLLER (Νόησις — Six Tiers)
                 6 rows T1→T6, each with Sanskrit tier name + English + data store
  LAYER 2: KERNEL UTILITIES & SERVICES bar — 6 subpill icons:
           Tool Registry (Whitelisted) · LLM Gateway (Strategy Pattern) ·
           Config & Secrets (Env/Vault) · Telemetry & Metrics (Prometheus) ·
           Logging & Tracing (Structured) · Backup & Recovery (Snapshots)
  LAYER 1: DATA PLANE — 3 large cards:
           SQLite (System/Config/Audit) ·
           Qdrant (Vector Memory) ·
           Redis (Cache/Sessions)

COLUMN 3 (right sidebar, 18% width, 4 stacked vertical sections):
  ▼ WORKFLOW EXECUTION FLOW (top, directed node graph vertical):
        ● START (mint)
        ● Agent A — Planner (Manan)
        ◇ split — Agent B Analys (Darshak) | Agent C Coder (Vidya)
        ◇ Join Policy (rhombus, purple)
        ● Agent D Tester (Parikshak) · Agent E Critic (Vivechak)
        ● Memory Update — Νόησις (Paalak)
        ● END

  ▼ SECURITY MODEL (MAC) (second section):
        ● Parent Agent Set → spawn AND-Mask → ◇ Child Derived Capabilities
        ❌ Red X gate → red "PermissionDenied (Non-bypassable)" card

  ▼ DEPLOYMENT TARGET (third section):
        "NVIDIA Jetson Orin Nano" (big mint text)
        4 bullets: Edge Inference · Low Power · Real-time Agents · On-device Privacy
        (plus a small icon of the Jetson module)

BOTTOM ROW (spans full width, 4 equal tiles):
  🧪 TESTING & QUALITY:  256/256 Pytest Tests, 5 sub-checks
  📊 EVALUATION TRACKS:  3 color-coded tiles Track1/Track2/Track3
  📦 PROJECT DELIVERABLES:  7 checkmarks (OSS, OpenAPI, docs, docker, Jetson, repro)
  📁 REPOS & MODULES:  3 rows: noesis-kernel, noesis-studio, noesis-docs

FOOTER TAGLINE (centered 12pt italic purple):
  "NOESIS — Kernelizing Intelligence. Securing Autonomy. Ensuring Determinism."

==(SLIDE 9 12 AGENT ROSTER)==
# 12-Agent Typed Roster (Sanskrit Codenames)
## 2×6 grid — each cell: Slot # · Class · Codename · 1-line role + Icon emoji

Use exact §(4) dictionary. Top row slots 1–6, bottom row 7–12. Each cell has:
  (a) Bold slot number top-left in a 20x20 purple pill
  (b) AgentClass Space Grotesk 18pt
  (c) "(Codename)" italic Sanskrit 12pt amber
  (d) Single-line responsibility
  (e) 1 emoji icon bottom-right (Planner=🧭, Analyst=🔍, Coder=💻, Tester=🧪,
      Tooler=🔧, Researcher=📚, Critic=⚖️, Memory=🧠, Security=🛡️,
      Synthesizer=🧬, Executor=✅, Supervisor=👁️)

==(SLIDE 10 NOESIS STUDIO MOCKUP)==
# Noesis Studio — Dashboard UI
## [RECREATE REF SLIDE B LAYOUT EXACTLY HERE — DARK STUDIO MOCK]

Use Dhruv's uploaded second image as source of truth. Layout:

TOP BAR (status row, full width):
  • Left 40px: Noesis orb glyph + "Welcome back, Dhruv 👋" (16pt) + 10pt subtitle
    "Design, run and audit deterministic multi-agent workflows."
  • Right 3 green/amber/mint status pills:
    🟢 Kernel Online · ✅ Deterministic Mode · 🔒 Seed: 42

LEFT SIDEBAR (16% width, 8 nav entries + 3 quick actions + Kernel Status mini):
  Nav list: Dashboard (selected purple) · Workflow Studio · Agents · Memory
  Explorer · Logs & Audit · Capabilities (MAC) · Tools & Registry · Settings
  Quick Actions: ＋ New Workflow · ↓ Load Workflow · ⤴ Import YAML
  Kernel Status card bottom: Healthy · Uptime 2h34m · v0.1.0 · Jetson Orin Nano · Python 3.12.3

MAIN CONTENT (84% width, 4 rows stacked):
  1. ACTIVE WORKFLOW HEADER ROW (1 card):
     "Code Generation & Review Pipeline  v1.0.0"  ID: wf_20250524_142530  Created:
     24 May 2025, 02:25 PM   Status pill Running+ · Progress 6/10 (60%) bar ·
     Duration 00:02:14 · Policy: ALL (Join) · Stop/Pause/View YAML buttons
  2. WORKFLOW GRAPH (80%) + Νόησις MEMORY EXPLORER side panel (20%):
     Main graph: Start → Manan → split Darshak/Anveshak → Vidya → Parikshak →
                Vivechak → Join → Paalak → End  ·  Graph legend bottom
     Memory side: 6 tier chips T6→T1 with Sanskrit names + count badges,
                  Total Items: 8,808
  3. SECOND ROW — 3 equal cards Workflow I/O (tabs Input/Config) · Agent Output
     (Vidya live code sample, with Copy/Open in Editor) · Logs & Audit (live
     scroll timestamped log tail + View Full Logs link)
  4. THIRD ROW — side-right ACTIVE AGENTS (Live list, 8 rows count down
     Completed/In Progress/Waiting + durations)
  5. FOOTER EVAL+PERF ROW (2 cards):
     Left EVALUATION: Tests Passed 256/256 · Determinism Bit-Exact ✅ ·
                     Reproducibility 100% · MAC Violations 0 · Policy ALL (Join)
     Right PERFORMANCE (Live): Total Tokens 12,842 · Latency(p95) 1.32s ·
                              Throughput 9.7 tok/s · GPU Power 6.4 W · Temperature 48.3 °C

==(SLIDE 11 MEMORY HIERARCHY)==
# Νόησις Memory Model — Six Tiered Hierarchy
## T1→T6 promotion paths · retention times · storage backing

Column layout: Left = tier pyramid (6 stacked horizontal bars growing from T1=100%
hot → T6=1% hot, colors red→amber→mint→cyan→blue→purple), Center = table
(§4 tier dictionary matrix + 1 extra column: "Promotion trigger" — e.g.
"T1 survives 3 ring-buffer wraps → promote to T2; T2 survives Redis LRU
eviction → promote to T3 …"), Right = 2 mini cards:
  • RIGHT TOP PROMOTION CONTROLLER CARD:
    Icon flowchart of auto-promotion + "SHA-256 provenance hash per tier jump"
  • RIGHT BOTTOM BENEFIT CARD:
    "Why this works: 42% longer task retention on 48-step workflows (internal
    pilot, n=50 runs) vs. flat-vector LangChain baseline."

==(SLIDE 12 SECURITY MODEL)==
# Security: Capability-Based MAC (AND-Mask Spawn Minting)
## Seccomp-bpf for agents — non-bypassable deny-first

3 column layout:
  LEFT: 5 numbered rules list (deny first, typed tokens, AND-mask, immut
  audit log, typed PermissionDenied exceptions + example code snippet in
  Fira Code red-bordered box of the spawn deny path raising PermissionDenied
  with `op=spawn_agent target=supervisor missing=[CAP_SPAWN_AGENT:*]`)
  CENTER: directed AND-Mask mint diagram (parent token {CAP_A, CAP_B, CAP_C,
  CAP_D}  →  AND-Mask = {CAP_A, CAP_B only}  →  child derives only {A,B};
  any attempt to call C raises ❌)
  RIGHT: Security audit table (4 first-class viva demo scenarios, each with
  "Expected Outcome" / "Demonstrable?" column:
    1 Spawn with 0 caps → PermissionDenied ✔ live demo
    2 JWT signature tamper → 401 reject ✔ live demo
    3 Tool with empty caps → PermissionDenied ✔ live demo
    4 Fixed seed 2-run → bit-exact match (minus request_id) ✔ live demo

==(SLIDE 13 TESTING + EVAL PLAN)==
# Testing Strategy & Evaluation Plan
## Three tracks · Systems correctness · Agentic bench · Live demos

Big 3-column 3-tile layout matching ref Slide A's EVALUATION TRACKS styling
(colored tiles Track1=mint, Track2=purple, Track3=amber, white bold title
each tile, bullet body):

🟢 T1 · Systems Correctness — 100% Automated Gate
  256 / 256 pytest kernel tests (non-negotiable gate) ·
  100% ruff check/ruff format compliance ·
  0 VS Code diagnostics ·
  OpenAPI contract snapshot invariant (byte-stable /openapi.json)
  → Gate threshold: **100% to submit capstone.**

🟣 T2 · Benchmark Performance (code gen)
  4 benchmarks scored pass@1:
   • HumanEval[2] (164 problems)
   • MBPP[3] (1000 problems)
   • SWE-bench-Lite[4] (300 PR-resolution)
   • ★ Custom Noesis Self-Host Bench (10 PRs on Noesis repo itself,
     pytest+ruff still green after apply)
  → Distinction target: +8% HumanEval / +12% MBPP over standalone 7B baseline,
     ≥ 5/10 Self-Host PRs closed green.

🟡 T3 · Live Viva Demonstrations (4 scenarios)
   • MAC gate non-bypassability — 0 caps → typed exception before LLM runs
   • Fixed-seed reproducibility — 2x POST /v1/runs/execute → byte-identical
     report fields (minus request_id / wall timestamps)
   • End-to-end workflow — live code PR generation + ruff + pytest
   • Jetson offline mode — run full pipeline with no internet, 0 token fees

==(SLIDE 14 JETSON ORIN DEPLOYMENT)==
# Deployment Target: NVIDIA Jetson Orin Nano 8GB
## $139 one-time hardware · 7–15 W · 0 token fees forever

Top = 4 KPI cards row:
  💰 1-yr TCO = ~$257 total (HW + NVMe + $1.05/mo power @ 24/7)
  ⚡ End-to-end PR pipeline = ~2m 20s (Qwen2.5-Coder-7B Q4, native CUDA)
  🔋 Power draw = 6.4 W (GPU active pipeline avg)
  🤏 Hardware budget = $139 Dev Kit · $70 1TB NVMe · $10 SD card

Middle LEFT = Model compatibility matrix (fit on 8GB / 4GB module, t/s real):
      Model                        8GB OK   4GB OK   t/s (8GB meas)
      Qwen2.5-Coder-7B-Instr Q4_K_M ✔       ✗        10–14 t/s
      DeepSeek-V2-Lite-1.3B Q4_K_M  ✔       ✔        30–40 t/s
      Qwen2.5-Coder-3B-Instr Q4_K_M ✔       ✔        14–18 t/s

Middle RIGHT = 3-YEAR TCO comparison table (5 rows, color winners green):
      Setup (3 yr, 5 PRs/day × 22 d)   Total 3-yr cost
      Jetson + local Qwen 7B             $257  🟢 BEST
      Jetson + DeepSeek OpenRouter         $288  🟢
      Laptop + Ollama Qwen 7B             $1,184  🔵
      GPT-4o cloud API only              $713  🔵
      GitHub Copilot Ent + Cursor Pro    $2,124  🔴

Bottom = One-line "Why it matters" callout in mint pill:
 → Hardware pays for itself in 3 weeks of not paying GPT-4o bills.

==(SLIDE 15 TIMELINE / GANTT)==
# 14-Week Project Execution Plan
## Gantt chart, color-coded workstreams (Systems / Frontend / Eval / Docs)

Draw a 14-column horizontal Gantt (week #1 at left → #14 right) with 8 thick
horizontal color-coded bars spanning weeks:
  purple (Systems kernel)      Wk1→Wk4  ( Jetson boot / LlamaCpp provider)
  blue (Frontend Studio)       Wk3→Wk6  ( 8 pages, remove mocks → live API)
  amber (Evaluation benches)   Wk7→Wk9  (4 benchmarks baseline + full pipeline)
  mint (Security audit)        Wk10     ( 4 live demo scenarios recorded)
  cyan (Report writing)        Wk11     (60 page IEEE thesis)
  red (Dry-run viva)           Wk12     (internal dry-run + bug fixes)
  purple (Final submission)    Wk13     (report / code / video annex)
  green (Viva day)             Wk14     (demonstration + Q&A)

Below the Gantt, a 5-line legend + 4 milestone diamond pills for freeze
points: v0.1 (synopsis Wk1) · v0.2 (benchmark baseline freeze Wk7) ·
v0.9 (code freeze Wk12) · v1.0 (vida release Wk14).

==(SLIDE 16 EXPECTED OUTCOMES + FUTURE)==
# Expected Outcomes · Limitations · Roadmap M8→M11

3 equal columns:

🟢 EXPECTED OUTCOMES (left, 6 bullets + checkmarks):
 ✅ Distinction-grade deployable release Noesis v1.0 (Dhruv Shah @dhruvshah11)
 ✅ `pip install noesis` PyPI package (entry-point `noesis` CLI)
 ✅ 60-page IEEE-style thesis report · 14-min Viva video annex
 ✅ Hugging Face card — Jetson-tuned Qwen2.5-Coder-7B prompt template
 ✅ Jetson Orin Nano bootstrap shell script `bootstrap_jetson.sh` 1-command
 ✅ 256/256 pytest gate · ≥+8% HumanEval · ≥+12% MBPP · ≥5/10 Self-Host

🟡 LIMITATIONS (middle, 4 honest bullets — examiners love honesty):
 • 12-agent roster tuned for software-engineering vertical; e-discovery /
   clinical research agents require domain-specific prompt tuning
 • Orchestrator runs on single node; multi-node MPI (32-agent fan-out) is M9
 • Local GPU Jetson code quality ≈ GPT-3.5-level; GPT-4o parity needs cloud
 • No formal GPU kernel-scheduler (TensorRT-LLM) yet; vLLM support in M8

🔵 ROADMAP M8 → M11 (right, 4 milestones):
  M8  Multi-tenant Noesis Cloud SaaS (Stripe, RBAC, regional deploy)
  M9  Multi-node MPI Orchestrator (32-agent parallel spawns) + TensorRT-LLM
  M10 Tauri v2 NoesisOS desktop (Windows/macOS/Linux offline installers)
  M11 Polyglot UAP SDK v1.0 (Rust · Go · Swift bindings)

==(SLIDE 17 REFERENCES & ACKNOWLEDGEMENTS)==
# References · IEEE Format [1]–[10] + Acknowledgements

[1]  N. F. Liu *et al.*, "Lost in the Middle: How Language Models Use Long
     Contexts," in *ACL*, 2023, DOI: 10.18653/v1/2023.acl-long.243.
[2]  M. Chen *et al.*, "Evaluating Large Language Models Trained on Code,"
     [HumanEval Benchmark], arXiv:2107.03374, Jul. 2021.
[3]  J. Austin *et al.*, "Program Synthesis with Large Language Models,"
     [MBPP Dataset], arXiv:2108.07732, Aug. 2021.
[4]  C. E. Jiménez *et al.*, "SWE-bench: Can Language Models Resolve
     Real-World GitHub Issues?" in *ICLR*, 2024, arXiv:2310.06770.
[5]  LangChain Contributors, *LangChain v0.3*, MIT, 2024.
     https://github.com/langchain-ai/langchain
[6]  Microsoft Research, *AutoGen: Enabling Next-Gen LLM Applications via
     Multi-Agent Conversation*, MIT, 2024.
[7]  Qwen Team, "Qwen2.5-Coder Technical Report," Alibaba Group,
     arXiv:2409.12186, Sep. 2024.
[8]  DeepSeek Team, "DeepSeek-Coder V2: All Models Are Great," DeepSeek,
     arXiv:2405.12466, May 2024.
[9]  D. M. Ritchie and K. Thompson, "The UNIX Time-Sharing System,"
     *Bell Syst. Tech. J.*, vol. 57, no. 6, 1978.
[10] M. S. Miller, K.-P. Yee, and J. Shapiro, "Capability Myths
     Demolished," HP Laboratories, Tech. Rep. SRL2003-02, 2003.

———— Acknowledgements (bottom 3 rows, 12pt) ————
• Guide Prof. ____________ for kernel architecture and security feedback.
• Departmental computing lab for GPU hours on evaluation bench T2.
• Qwen[7] & DeepSeek[8] open research teams + llama.cpp (ggerganov, MIT) for
  making on-device evaluation feasible on student hardware.

==(SLIDE 18 Q&A THANK YOU)==
# 🙏 Thank You
# νους — "Intelligence through Reason"
Dhruv Shah  ·  @dhruvshah11  ·  https://github.com/dhruvshah11/noesis
### Questions?
Noesis logo bottom-center large · Purple gradient footer rule.

================================================================================
(6) SPEAKER NOTES — 4-6 BULLETS FOR EACH SLIDE (Dhruv's viva speaking script)
================================================================================

For EVERY SLIDE (0–18), append a 4-6 bullet `### Speaker Notes:` section
under the Marp slide content. Use Dhruv's 1st-person voice ("I chose…",
"My novelty claim is…"). Key 3-sentence LangChain-vs-Noesis elevator pitch
goes into Slide 6 Speaker Notes (exact copy from our earlier synopsis):

ELEVATOR PITCH for viva Q&A (MEMORIZE — every examiner will ask this):
  "Three things make Noesis NOT just another LangChain wrapper.  ONE: LangChain
  has flat memory only; I have a 6-tier typed promotion controller (C1).
  TWO: LangChain has zero security boundary — any agent spawns anything; I
  implemented capability-based AND-Mask gates like Linux seccomp (C2).
  THREE: LangChain prompt chains are completely non-deterministic; my 12
  agents ship as seeded pure functions with bit-exact replay-ability (C3).
  LangChain is a prompt toolkit. Noesis is a kernel."

================================================================================
(7) MARP / DECK.MD RENDER INSTRUCTIONS FOR CLAUDE — EXPORT TO PPTX HOW-TO
================================================================================

After you produce the full deck in Marp markdown, append a 1-paragraph block:

"## 🛠️ Dhruv's Export Guide: Marp → PPTX (5 clicks)
  1. Open https://demo.marp.app in browser.
  2. Delete the default sample deck.
  3. Paste entire markdown into the Marp editor (left pane).
  4. Click 'Export' top-right → choose 'PowerPoint File (.pptx)' — Chrome
     downloads the 19-slide deck fully styled with all gradients and cards.
  5. Open in PowerPoint; tweak any image placements manually if needed;
     upload Sanskrit-codename icons from Canva's 'Hindu Spiritual' icon set
     for Slide 9 cells (optional)."

================================================================================
END OF CONTEXT FILE — you now have 100% of Dhruv's intent. Produce the deck.
================================================================================
