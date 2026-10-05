# Title, Authors, and Abstract (CODS-COMAD 2027 · ACM SIGCONF 6-page 2-col)

> Submission to: **20th International Conference on Data Science and Management of Data (CODS-COMAD 2027)**
> Venue: Indian Institute of Technology Bombay, Mumbai · January 2027
> Format: ACM SIGCONF proceedings · 6 pages · 9 pt body · 2-column · natbib acmart-sigconf

---

## Title

**Noesis (νόησις): An Autonomic 12-Agent Capability-Gated Multi-Agent OS with Six-Tier Semantic Memory Hierarchy for Deterministic-Accelerated Software Engineering Tasks**

## Authors

Dhruv Shah¹ · [Guide Name]²

¹B.Tech/B.E. Candidate, Department of Computer Engineering, [Affiliated College / University]  
²Assistant Professor, Department of Computer Engineering, [Affiliated College / University]

E-mail: dhruvshah11 [at] github.com · [guide-email]

**Author note:** Work performed as part of the B.Tech/B.E. Major Project capstone, Weeks 1–18, 2025–2026. All code, data, and reproducibility artefacts are released under Apache-2.0 at `https://github.com/dhruvshah11/astraos`.

---

## Abstract (248 words · ACM limit: 150–250)

We present **Noesis (νόησις)**, an autonomic twelve-agent multi-agent operating system for deterministic-accelerated software engineering tasks on commodity laptop GPUs. Noesis contributes three mechanisms absent from the published open-agent literature. **(C1)** A six-tier semantic memory hierarchy — T1 Indriya (Sensory), T2 Kushalata (Skills), T3 Gyān (Knowledge), T4 Ranniti (Tactical), T5 Yojana (Strategic), T6 Tattva (Principles) — with tier-adjacent-only promotion co-signed by the Vivechak (Critic) agent, preventing transient hallucinations from polluting long-term strategic memory. **(C2)** A Capability-Gated AND-Mask Spawn Minting kernel with non-bypassable Mandatory Access Control: every agent carries an HMAC-SHA256-signed capability token, every agent spawn is gated by a three-term AND-mask (roles ∧ tiers ∧ OP_SPAWN), and every tool invocation transits a four-term mask gate — the gates live in the Python call graph, not in LLM output, and are therefore prompt-injection-resistant by construction. **(C3)** A deterministic seeded pure-Python orchestration path for the 12-agent pipeline (Manan planner → Darshak/Vidya/Parikshak/Karmakarta/Anveshak/Vivechak/Paalak/Rakshak fan-out → Samanyakā synthesizer → Kriyākārī tri-state sign-off → Nirikshak supervisor) that achieves SHA-256 identity score 1.0 on 100 same-(goal, seed) runs across 5 tasks of the Noesis-SE50 capstone corpus, wall-clock 0.6 s on a laptop CPU, 0 LLM calls, $0 tokens. We evaluate on HumanEval+, SWE-bench Verified Lite, and Noesis-SE50 with Ollama/qwen2.5-coder:7b-instruct-q4_K_M on RTX 40xx. Ablations show six-tier memory outperforms flat-Qdrant baseline by ≥ 12 percentage points pass@1, and the AND-mask kernel rejects 100% of crafted prompt-injection attempts that bypass string-allowlist baselines.

*CCS Concepts:*  
• Computing methodologies → Multi-agent systems; Cognitive architectures; Reasoning about belief and knowledge;  
• Security and privacy → Access control; Logic and verification;  
• Software and its engineering → Software verification and validation; Application specific development environments.

*Keywords:* Multi-agent systems, capability-based security, semantic memory hierarchy, mandatory access control, determinism, reproducibility, laptop-first AI, edge AI, software engineering agents.
