import type {
  BenchmarkResults,
  BenchmarkRow,
  BenchmarkSummary,
  ExecutionTrace,
  MemoryRecord,
  ObservabilitySummary,
} from "@/lib/schemas";

export interface Conversation {
  readonly id: string;
  readonly title: string;
  readonly preview: string;
  readonly agent: string;
  readonly status: "active" | "completed" | "paused" | "failed";
  readonly messages: number;
  readonly tokens: number;
  readonly updated_at: number;
  readonly tags: readonly string[];
}

export interface Document {
  readonly id: string;
  readonly name: string;
  readonly type: "pdf" | "md" | "docx" | "csv" | "html" | "txt";
  readonly size_kb: number;
  readonly status: "indexed" | "processing" | "failed" | "queued";
  readonly chunks: number;
  readonly owner: string;
  readonly uploaded_at: number;
}

export interface Agent {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly type: "planner" | "research" | "coding" | "rag" | "tool" | "reflection";
  readonly status: "online" | "busy" | "offline" | "error";
  readonly version: string;
  readonly capabilities: readonly string[];
  readonly invocations_24h: number;
  readonly avg_latency_ms: number;
}

// ===========================================================================
// Deterministic, reproducible mock datasets (seeded with a small LCG so tests
// don't flake).  Used when: (a) backend is not reachable, (b) in Vitest unit
// tests, (c) Storybook/offline preview.
// ===========================================================================

function mulberry32(seed: number): () => number {
  let t = seed >>> 0;
  return function r(): number {
    t = (t + 0x6d2b79f5) >>> 0;
    let r = t;
    r = Math.imul(r ^ (r >>> 15), r | 1);
    r ^= r + Math.imul(r ^ (r >>> 7), r | 61);
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

export function buildMockObservability(seed = 42): ObservabilitySummary {
  const rand = mulberry32(seed);
  const toolBase = [
    { name: "shell", calls: 84, errs: 3, avg: 140 },
    { name: "python", calls: 51, errs: 1, avg: 920 },
    { name: "files", calls: 203, errs: 0, avg: 18 },
    { name: "web_fetch", calls: 44, errs: 5, avg: 1100 },
    { name: "calendar", calls: 12, errs: 0, avg: 55 },
  ];
  return {
    window_s: 3600,
    total_requests: 1337,
    total_prompt_tokens: 3_456_789,
    total_completion_tokens: 943_210,
    total_tokens: 3_456_789 + 943_210,
    total_cost_usd: 17.493,
    latency_ms: { avg: 682, p50: 512, p95: 1930, p99: 3780 },
    tools: toolBase.map((t) => ({
      tool_name: t.name,
      invocations: t.calls + Math.floor(rand() * 20),
      errors: t.errs,
      total_ms: t.calls * t.avg,
      avg_ms: t.avg,
      p50_ms: t.avg,
      p95_ms: Math.round(t.avg * (2.1 + rand() * 0.6)),
      p99_ms: Math.round(t.avg * (3.4 + rand() * 0.9)),
    })),
  };
}

export function buildMockTraces(seed = 7): ExecutionTrace[] {
  const rand = mulberry32(seed);
  const queries = [
    "Summarise Q2 OKRs in the docs/ folder and write a draft deck",
    "Implement user profile avatar upload with S3 pre-signed URLs",
    "Research vector databases: compare pgvector vs Qdrant vs Pinecone",
    "Build a habit tracker mobile UI — weekly heatmap + streak logic",
  ];
  const _statuses = ["success", "skipped", "running", "failed", "pending"] as const;
  type StepStatus = (typeof _statuses)[number];
  return queries.map((q, i): ExecutionTrace => {
    const created_at = Date.now() / 1000 - i * 3600 * (1 + rand());
    const statusFor: (sIdx: number) => StepStatus = (sIdx) => {
      switch (sIdx) {
        case 0:
          return "success";
        case 1:
          return i === 2 ? "success" : "skipped";
        case 2:
          return "success";
        case 3:
          return i === 0 ? "running" : i === 3 ? "failed" : "success";
        case 4:
          return i === 0 ? "pending" : "success";
        default:
          return "skipped";
      }
    };
    const agents = ["planner", "research", "rag", "coding", "reflection"] as const;
    const descriptions = [
      "Decompose goal into plan steps",
      "Gather reference material",
      "Retrieve relevant context from memory",
      "Write implementation + tests",
      "Verify result against acceptance criteria",
    ];
    const steps = agents.map((agent, sIdx) => ({
      idx: sIdx,
      agent,
      status: statusFor(sIdx),
      desc: descriptions[sIdx] ?? `Step ${sIdx}`,
    }));
    const plan_steps = steps.map((s, k) => {
      const duration = 10_000 + Math.floor(rand() * 90_000);
      const started_at = created_at + k * 60 + rand() * 15;
      const stepStatus = s.status;
      return {
        index: s.idx,
        description: s.desc,
        assigned_agent: s.agent,
        status: stepStatus,
        confidence: 0.65 + rand() * 0.3,
        depends_on: k === 0 ? [] : [k - 1],
        tool_calls:
          k === 3
            ? [
                {
                  id: `tc-${i}-${k}-1`,
                  name: "files",
                  args: { path: "src/app.tsx", op: "write" as const },
                  started_at: started_at + 5,
                  ended_at: started_at + 15,
                  success: true,
                  exit_code: 0,
                },
                {
                  id: `tc-${i}-${k}-2`,
                  name: "shell",
                  args: { command: "npm run test" },
                  started_at: started_at + 20,
                  ended_at: stepStatus === "failed" ? started_at + 42 : started_at + 38,
                  success: stepStatus !== "failed",
                  exit_code: stepStatus === "failed" ? 1 : 0,
                  stdout_snippet:
                    stepStatus === "failed"
                      ? "FAIL src/__tests__/app.test.tsx\n  ✗ should render avatar (ms)"
                      : "PASS 12 tests · 0 failures",
                },
              ]
            : [],
        started_at,
        ended_at: stepStatus === "pending" || stepStatus === "running" ? undefined : started_at + duration,
      };
    });
    const overallStatus: StepStatus = plan_steps.every((s) => s.status === "success")
      ? "success"
      : plan_steps.some((s) => s.status === "failed")
        ? "failed"
        : plan_steps.some((s) => s.status === "running")
          ? "running"
          : plan_steps.every((s) => s.status === "skipped")
            ? "skipped"
            : "pending";
    return {
      trace_id: `trace-${1_000_000 + i}`,
      user_query: q,
      plan_steps,
      status: overallStatus,
      created_at,
    };
  });
}

export function buildMockMemory(seed = 1337, n = 48): MemoryRecord[] {
  const rand = mulberry32(seed);
  const tiers = ["conversation", "semantic", "episodic", "working", "project", "user"] as const;
  const tagPool = ["okr", "spec", "code", "email", "meeting", "doc", "ticket", "research"];
  const sample = <T extends string>(arr: readonly T[], k: number): T[] => {
    const out = new Set<T>();
    const len = arr.length;
    while (out.size < k && out.size < len) {
      const idx = Math.floor(rand() * len);
      const val: T | undefined = arr[idx];
      if (val !== undefined) out.add(val);
    }
    return [...out];
  };
  const snippets = [
    "Q2 target: 70% code coverage for M3 agent suite and 99.9% login availability.",
    "The auth server must rotate refresh tokens on every use and persist old-token jti to a denylist for 2x TTL.",
    "Planner decomposes goals into ExecutionPlan with per-step dependencies and confidence.",
    "RAG hybrid search combines dense embeddings with BM25 via reciprocal rank fusion (k=60).",
    "Reflection agent performs mistake-detection pass using a verifier prompt that cites chain-of-thought.",
    "FilesTool must reject any path that escapes the workspace root — detected via realpath() comparison.",
    "For JWT signing we use HS256 with a 32+ byte secret; we validate the secret length on JWTService construction.",
    "ToolRegistry.invoke() gates every call on a Capability(CapabilityOp.TOOL_INVOKE, name) glob match.",
  ];
  return Array.from({ length: n }, (_, i) => {
    const t = Math.floor(rand() * tiers.length);
    const tier = tiers[t] ?? tiers[0];
    const x = (rand() - 0.5) * 4 + (t - 2.5);
    const y = (rand() - 0.5) * 4 + (i % 4) - 1.5;
    return {
      id: `mem-${1_000 + i}`,
      tier,
      content: snippets[i % snippets.length] ?? `Memory record ${i}`,
      score: rand() * 2 - 1,
      embedding_2d: [Number(x.toFixed(3)), Number(y.toFixed(3))],
      tags: sample(tagPool, 2 + Math.floor(rand() * 2)),
      created_at: Date.now() / 1000 - rand() * 60 * 60 * 24 * 30,
      chunk_id: rand() > 0.5 ? `chunk-${5_000 + i}` : undefined,
    };
  });
}

export function buildMockConversations(seed = 2024): Conversation[] {
  const rand = mulberry32(seed);
  const sample = <T,>(arr: readonly T[], k: number): T[] => {
    const out = new Set<number>();
    const result: T[] = [];
    while (result.length < k && out.size < arr.length) {
      const idx = Math.floor(rand() * arr.length);
      if (!out.has(idx)) {
        out.add(idx);
        const val = arr[idx];
        if (val !== undefined) result.push(val);
      }
    }
    return result;
  };
  const titles = [
    "Quarterly OKR planning and roadmap",
    "Implement S3 avatar upload pipeline",
    "Vector DB comparison: pgvector vs Qdrant",
    "Habit tracker mobile UI build",
    "Security audit of auth module",
    "API rate limiter design review",
    "Database migration strategy for v2",
  ];
  const previews = [
    "Breaking down Q2 objectives into measurable key results with owners and timelines…",
    "Working through pre-signed URL flow, bucket policies, and image validation middleware…",
    "Comparing ingestion throughput, HNSW tuning, and hybrid search benchmarks…",
    "Weekly heatmap component, streak counter, and local-first persistence layer…",
    "Reviewing JWT rotation, session fixation, and rate-limit bypass vulnerabilities…",
    "Token bucket vs sliding window, distributed counter with Redis, and fair sharing…",
    "Online schema migrations, rollback playbooks, and zero-downtime cutover…",
  ];
  const agents = ["Planner", "Coding", "Research", "Reflection", "RAG", "Tool"] as const;
  const statuses: Conversation["status"][] = ["active", "completed", "paused", "failed", "completed", "active", "paused"];
  const tagPool = ["okr", "code", "research", "security", "infra", "design", "review"];
  return titles.map((title, i) => {
    const agent = agents[i] ?? agents[0];
    const status = statuses[i] ?? "completed";
    const preview = previews[i] ?? `Conversation ${i} preview…`;
    return {
      id: `conv-${100 + i}`,
      title,
      preview,
      agent,
      status,
      messages: 12 + Math.floor(rand() * 48),
      tokens: 4_000 + Math.floor(rand() * 30_000),
      updated_at: Date.now() / 1000 - i * 60 * (20 + rand() * 180),
      tags: sample(tagPool, 1 + Math.floor(rand() * 3)),
    };
  });
}

export function buildMockDocuments(seed = 3003): Document[] {
  const rand = mulberry32(seed);
  const names = [
    "Q2-OKRs-2026.pdf",
    "architecture-spec.md",
    "employee-handbook.docx",
    "sales-q1.csv",
    "security-audit-report.html",
    "api-design-review.txt",
    "migration-playbook.pdf",
    "vector-db-benchmarks.md",
    "brand-guidelines.docx",
    "customer-feedback.csv",
    "incident-postmortem.html",
    "release-notes-v2.1.txt",
  ];
  const types: Document["type"][] = ["pdf", "md", "docx", "csv", "html", "txt", "pdf", "md", "docx", "csv", "html", "txt"];
  const statuses: Document["status"][] = [
    "indexed", "indexed", "indexed", "processing", "indexed", "failed",
    "indexed", "indexed", "queued", "indexed", "indexed", "processing",
  ];
  const owners = ["alex", "sam", "jordan", "taylor", "casey", "morgan", "alex", "sam", "jordan", "taylor", "casey", "morgan"];
  return names.map((name, i) => ({
    id: `doc-${2000 + i}`,
    name,
    type: types[i] ?? "pdf",
    size_kb: 24 + Math.floor(rand() * 4000),
    status: statuses[i] ?? "indexed",
    chunks: statuses[i] === "indexed" ? 12 + Math.floor(rand() * 180) : 0,
    owner: owners[i] ?? "alex",
    uploaded_at: Date.now() / 1000 - i * 60 * 60 * (2 + rand() * 36),
  }));
}

export function buildMockAgents(seed = 77): Agent[] {
  const rand = mulberry32(seed);
  const defs: readonly Omit<Agent, "invocations_24h" | "avg_latency_ms">[] = [
    {
      id: "agent-planner",
      name: "Orchestrator",
      description: "Goal decomposition, dependency graphing, and plan-step sequencing with confidence scoring.",
      type: "planner",
      status: "online",
      version: "2.4.1",
      capabilities: ["plan", "decompose", "prioritize", "route"],
    },
    {
      id: "agent-research",
      name: "Researcher",
      description: "Web fetch, citation synthesis, and structured note-taking across sources.",
      type: "research",
      status: "online",
      version: "1.9.0",
      capabilities: ["web_fetch", "search", "summarize", "cite"],
    },
    {
      id: "agent-coding",
      name: "Engineer",
      description: "File edits, shell runs, patch generation, and test-first implementation.",
      type: "coding",
      status: "busy",
      version: "3.1.2",
      capabilities: ["files", "shell", "git", "test", "patch"],
    },
    {
      id: "agent-rag",
      name: "Librarian",
      description: "Hybrid BM25 + dense retrieval across memory tiers and document chunks.",
      type: "rag",
      status: "online",
      version: "1.5.3",
      capabilities: ["search", "retrieve", "rerank", "context_pack"],
    },
    {
      id: "agent-tool",
      name: "Executor",
      description: "Capability-gated tool registry invocation with sandboxing and audit logs.",
      type: "tool",
      status: "online",
      version: "2.0.0",
      capabilities: ["tool_invoke", "sandbox", "audit", "retry"],
    },
    {
      id: "agent-reflection",
      name: "Verifier",
      description: "Chain-of-thought mistake detection, acceptance check, and self-critique loop.",
      type: "reflection",
      status: "error",
      version: "0.8.7",
      capabilities: ["verify", "critique", "diff", "replan"],
    },
  ];
  return defs.map((d) => ({
    ...d,
    invocations_24h: 120 + Math.floor(rand() * 2400),
    avg_latency_ms: 180 + Math.floor(rand() * 1400),
  }));
}

// ===========================================================================
// Benchmark results mock (MS8 Studio benchmarks hub)
// ===========================================================================

export function buildMockBenchResults(seed = 42): BenchmarkResults {
  const rand = mulberry32(seed);

  const se50Categories = [
    "code_gen", "refactor", "testing", "debug", "api_design",
    "perf", "docs", "data_pipeline", "config", "security",
  ] as const;
  const se50Difficulties: BenchmarkRow["difficulty"][] = [
    "trivial", "easy", "medium", "hard", "expert",
  ];
  const se50Rows: BenchmarkRow[] = [];

  for (let i = 0; i < 50; i++) {
    const cat = se50Categories[i % se50Categories.length] ?? "UNCATEGORIZED";
    const diffIdx = Math.min(
      se50Difficulties.length - 1,
      Math.floor(rand() * se50Difficulties.length),
    );
    const difficulty = se50Difficulties[diffIdx] ?? "medium";
    const bias = (4 - diffIdx) / 6;
    const successProb = 0.38 + bias * 0.55 + (rand() - 0.5) * 0.15;
    const r = rand();
    const tristate: BenchmarkRow["tristate"] =
      r < successProb ? "signoff" : r < successProb + 0.18 ? "reject" : "replan";
    se50Rows.push({
      task_id: `SE50-${String(i + 1).padStart(3, "0")}`,
      category: cat,
      difficulty,
      tristate,
      duration_ms: 4000 + Math.floor(rand() * 52000),
      plan_sha: `${Math.floor(rand() * 0xFFFFFFFF).toString(16).padStart(8, "0")}${Math.floor(rand() * 0xFFFFFFFF).toString(16).padStart(8, "0")}`,
      kriyakari_conf: tristate === "signoff" ? 0.72 + rand() * 0.27 : 0.22 + rand() * 0.45,
      samples: 1,
    });
  }

  const nCorrect = se50Rows.filter((r) => r.tristate === "signoff").length;
  const signoffAvgConf =
    se50Rows
      .filter((r) => r.tristate === "signoff")
      .reduce((a, r) => a + r.kriyakari_conf, 0) / Math.max(1, nCorrect);

  const byCat = new Map<string, { n: number; c: number }>();
  for (const row of se50Rows) {
    const prev = byCat.get(row.category) ?? { n: 0, c: 0 };
    byCat.set(row.category, { n: prev.n + 1, c: prev.c + (row.tristate === "signoff" ? 1 : 0) });
  }
  const per_category = [...byCat.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([category, v]) => {
      const p1 = v.n > 0 ? v.c / v.n : 0;
      const w = 0.04 + rand() * 0.08;
      return {
        category,
        n_total: v.n,
        n_correct: v.c,
        pass_at_1: p1,
        ci_low: Math.max(0, p1 - w),
        ci_high: Math.min(1, p1 + w),
      };
    });

  const byDiff = new Map<string, { n: number; c: number }>();
  for (const row of se50Rows) {
    const prev = byDiff.get(row.difficulty) ?? { n: 0, c: 0 };
    byDiff.set(row.difficulty, { n: prev.n + 1, c: prev.c + (row.tristate === "signoff" ? 1 : 0) });
  }
  const diffOrder: Record<BenchmarkRow["difficulty"], number> = {
    trivial: 0, easy: 1, medium: 2, hard: 3, expert: 4,
  };
  const per_difficulty = [...byDiff.entries()]
    .sort((a, b) => diffOrder[a[0] as BenchmarkRow["difficulty"]] - diffOrder[b[0] as BenchmarkRow["difficulty"]])
    .map(([difficulty, v]) => ({
      difficulty,
      n_total: v.n,
      n_correct: v.c,
      pass_at_1: v.n > 0 ? v.c / v.n : 0,
    }));

  const se50: BenchmarkSummary = {
    overall_pass_at_1: nCorrect / se50Rows.length,
    overall_ci_low: Math.max(0, nCorrect / se50Rows.length - 0.11),
    overall_ci_high: Math.min(1, nCorrect / se50Rows.length + 0.11),
    n_total: se50Rows.length,
    n_correct: nCorrect,
    per_category,
    per_difficulty,
  };

  const humaneval_pass_at_1 = 0.762;
  const heCodenames = [
    "has_close_elements", "separate_paren_groups", "truncate_number",
    "mean_absolute_deviation", "intersperse", "parse_music",
    "largest_prime_factor", "find_closest_elements", "median",
    "unique_digits", "fizz_buzz", "count_distinct_characters",
    "string_sequence", "filter_by_prefix", "get_odd_collatz",
    "sort_numbers", "add_binary", "correct_bracketing",
    "x_or_y", "special_factorial", "polyglos", "cycpattern",
    "digits_multiplication", "triangle_area", "starts_one_ends",
    "match_parens", "flip_case", "product_signs", "above_bound",
    "is_palindrome", "search", "common_prefix", "monotonic",
    "row_sum_weights", "double_the_difference", "prime_length",
  ];
  const humaneval_buckets = heCodenames.map((codename, i) => {
    const base = 0.35 + rand() * 0.65;
    const pass_rate = Math.max(0, Math.min(1, base - (i % 7) * 0.03));
    return {
      task_id: `HumanEval/${String(1 + i).padStart(3, "0")}`,
      codename,
      pass_rate,
      n_samples: 20,
      rank: i + 1,
    };
  }).sort((a, b) => b.pass_rate - a.pass_rate);

  const mbpp_pass_at_1 = 0.614;
  const mbppLabels = ["Very Easy", "Easy", "Medium", "Hard", "Very Hard"];
  const mbppTaskCounts = [97, 122, 105, 118, 58] as const;
  const mbpp_buckets = mbppLabels.map((label, i) => ({
    bucket: label,
    difficulty: i + 1,
    pass_at_1: Math.max(0.05, 0.88 - i * (0.14 + rand() * 0.04)),
    n_tasks: mbppTaskCounts[i] ?? 0,
  }));

  const variantKeys = ["baseline_nomem", "baseline_nomac", "full_noesis"] as const;
  const ablation_rows: Record<string, unknown>[] = [];
  const overallRow: Record<string, unknown> = { metric: "OVERALL pass@1" };
  overallRow[variantKeys[0]] = se50.overall_pass_at_1 - 0.18;
  overallRow[variantKeys[1]] = se50.overall_pass_at_1 - 0.09;
  overallRow[variantKeys[2]] = se50.overall_pass_at_1;
  ablation_rows.push(overallRow);
  for (const pc of per_category) {
    const row: Record<string, unknown> = { metric: pc.category };
    row[variantKeys[0]] = Math.max(0, pc.pass_at_1 - 0.18 - 0.02 + rand() * 0.04);
    row[variantKeys[1]] = Math.max(0, pc.pass_at_1 - 0.09 - 0.01 + rand() * 0.02);
    row[variantKeys[2]] = pc.pass_at_1;
    ablation_rows.push(row);
  }

  return {
    se50,
    se50_rows: se50Rows,
    humaneval_pass_at_1,
    humaneval_buckets,
    mbpp_pass_at_1,
    mbpp_buckets,
    ablation_table: {
      variant_keys: [...variantKeys] as [string, string, string],
      rows: ablation_rows,
      notes: {
        c1_gain_full_vs_nomem_pp: Number(((se50.overall_pass_at_1 - (se50.overall_pass_at_1 - 0.18)) * 100).toFixed(1)),
        c2_gain_full_vs_nomac_pp: Number(((se50.overall_pass_at_1 - (se50.overall_pass_at_1 - 0.09)) * 100).toFixed(1)),
        c3_mcnemar_note: "Paired per-task McNemar mid-p χ² via noesis.benchmarks.stats.mcnemar_pvalue",
      },
    },
    signoff_avg_conf: Number(signoffAvgConf.toFixed(3)),
  };
}
