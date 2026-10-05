import { z } from "zod";

// ===========================================================================
// Domain model — mirrors backend Pydantic schemas declared in:
//   noesis/types.py, noesis/security/__init__.py, noesis/api/routes/v1_m3.py
//
// Zod schemas serve a dual purpose:
//   1. Runtime parse/validation for responses coming over the wire.
//   2. Inferred TypeScript types via `z.infer<>` — single source of truth.
// ===========================================================================

// --- Security / auth -------------------------------------------------------

export const TokenPairSchema = z.object({
  access_token: z.string().min(16),
  refresh_token: z.string().min(16),
  token_type: z.literal("Bearer").default("Bearer"),
  expires_in: z.number().int().positive().optional(),
});
export type TokenPair = z.infer<typeof TokenPairSchema>;

export const JwtClaimsSchema = z.object({
  sub: z.string(),
  iat: z.number().int().positive(),
  exp: z.number().int().positive(),
  iss: z.string(),
  roles: z.array(z.string()).default([]),
  scopes: z.array(z.string()).default([]),
  kind: z.enum(["access", "refresh"]).default("access"),
});
export type JwtClaims = z.infer<typeof JwtClaimsSchema>;

// --- Observability (v1_m3 /observability/summary) -------------------------

export const ToolMetricSchema = z.object({
  tool_name: z.string().min(1),
  invocations: z.number().int().nonnegative(),
  errors: z.number().int().nonnegative(),
  total_ms: z.number().nonnegative(),
  avg_ms: z.number().nonnegative(),
  p50_ms: z.number().nonnegative(),
  p95_ms: z.number().nonnegative(),
  p99_ms: z.number().nonnegative(),
});
export type ToolMetric = z.infer<typeof ToolMetricSchema>;

export const ObservabilitySummarySchema = z.object({
  window_s: z.number().int().positive(),
  total_requests: z.number().int().nonnegative(),
  total_prompt_tokens: z.number().int().nonnegative(),
  total_completion_tokens: z.number().int().nonnegative(),
  total_tokens: z.number().int().nonnegative(),
  total_cost_usd: z.number().nonnegative(),
  latency_ms: z.object({
    avg: z.number().nonnegative(),
    p50: z.number().nonnegative(),
    p95: z.number().nonnegative(),
    p99: z.number().nonnegative(),
  }),
  tools: z.array(ToolMetricSchema).default([]),
});
export type ObservabilitySummary = z.infer<typeof ObservabilitySummarySchema>;

// --- Agent execution timeline ---------------------------------------------

export const AgentTypeZ = z.enum([
  "planner",
  "research",
  "coding",
  "memory",
  "rag",
  "tool",
  "reflection",
]);
export type AgentType = z.infer<typeof AgentTypeZ>;

export const PlanStepStatusZ = z.enum(["pending", "running", "success", "failed", "skipped"]);
export type PlanStepStatus = z.infer<typeof PlanStepStatusZ>;

export const ToolCallSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  args: z.record(z.unknown()),
  started_at: z.number().nonnegative(),
  ended_at: z.number().nonnegative().optional(),
  success: z.boolean().optional(),
  exit_code: z.number().int().optional(),
  stdout_snippet: z.string().optional(),
  stderr_snippet: z.string().optional(),
});
export type ToolCall = z.infer<typeof ToolCallSchema>;

export const PlanStepSchema = z.object({
  index: z.number().int().nonnegative(),
  description: z.string().min(3),
  assigned_agent: AgentTypeZ,
  status: PlanStepStatusZ.default("pending"),
  confidence: z.number().min(0).max(1).optional(),
  depends_on: z.array(z.number().int().nonnegative()).default([]),
  tool_calls: z.array(ToolCallSchema).default([]),
  started_at: z.number().nonnegative().optional(),
  ended_at: z.number().nonnegative().optional(),
});
export type PlanStep = z.infer<typeof PlanStepSchema>;

export const ExecutionTraceSchema = z.object({
  trace_id: z.string().min(8),
  user_query: z.string(),
  plan_steps: z.array(PlanStepSchema).default([]),
  status: PlanStepStatusZ.default("running"),
  created_at: z.number().nonnegative(),
});
export type ExecutionTrace = z.infer<typeof ExecutionTraceSchema>;

// --- Memory tier -----------------------------------------------------------

export const MemoryTierZ = z.enum([
  "conversation",
  "user",
  "project",
  "semantic",
  "episodic",
  "working",
]);
export type MemoryTier = z.infer<typeof MemoryTierZ>;

export const MemoryRecordSchema = z.object({
  id: z.string().min(1),
  tier: MemoryTierZ,
  content: z.string().min(1),
  score: z.number().min(-1).max(1).default(0),
  embedding_2d: z.tuple([z.number(), z.number()]).optional(),
  tags: z.array(z.string()).default([]),
  created_at: z.number().nonnegative(),
  chunk_id: z.string().optional(),
});
export type MemoryRecord = z.infer<typeof MemoryRecordSchema>;

// ===========================================================================
// Benchmark results hub (MS8 — Studio benchmarks page)
// Mirrors: backend/noesis/benchmarks/stats.py Pydantic models
// ===========================================================================

export const BenchmarkRowSchema = z.object({
  task_id: z.string().min(1),
  category: z.string().default("UNCATEGORIZED"),
  difficulty: z.enum(["trivial", "easy", "medium", "hard", "expert"]).default("medium"),
  tristate: z.enum(["signoff", "reject", "replan"]).default("replan"),
  duration_ms: z.number().int().nonnegative().default(0),
  plan_sha: z.string().min(1).default("sha-placeholder"),
  kriyakari_conf: z.number().min(0).max(1).default(0.5),
  samples: z.number().int().nonnegative().optional(),
});
export type BenchmarkRow = z.infer<typeof BenchmarkRowSchema>;

export const CategoryPass1Schema = z.object({
  category: z.string(),
  n_total: z.number().int().nonnegative(),
  n_correct: z.number().int().nonnegative(),
  pass_at_1: z.number().min(0).max(1),
  ci_low: z.number().min(0).max(1),
  ci_high: z.number().min(0).max(1),
});
export type CategoryPass1 = z.infer<typeof CategoryPass1Schema>;

export const DifficultyRowSchema = z.object({
  difficulty: z.string(),
  n_total: z.number().int().nonnegative(),
  n_correct: z.number().int().nonnegative(),
  pass_at_1: z.number().min(0).max(1),
});
export type DifficultyRow = z.infer<typeof DifficultyRowSchema>;

export const BenchmarkSummarySchema = z.object({
  overall_pass_at_1: z.number().min(0).max(1),
  overall_ci_low: z.number().min(0).max(1),
  overall_ci_high: z.number().min(0).max(1),
  n_total: z.number().int().nonnegative(),
  n_correct: z.number().int().nonnegative(),
  per_category: z.array(CategoryPass1Schema).default([]),
  per_difficulty: z.array(DifficultyRowSchema).default([]),
});
export type BenchmarkSummary = z.infer<typeof BenchmarkSummarySchema>;

export const AblationTableSchema = z.object({
  variant_keys: z.tuple([z.string(), z.string(), z.string()]),
  rows: z.array(z.record(z.unknown())).default([]),
  notes: z.record(z.unknown()).default({}),
});
export type AblationTable = z.infer<typeof AblationTableSchema>;

export const HumanEvalBucketSchema = z.object({
  task_id: z.string().min(1),
  codename: z.string().min(1),
  pass_rate: z.number().min(0).max(1),
  n_samples: z.number().int().nonnegative(),
  rank: z.number().int().nonnegative().optional(),
});
export type HumanEvalBucket = z.infer<typeof HumanEvalBucketSchema>;

export const MBPPBucketSchema = z.object({
  bucket: z.string().min(1),
  difficulty: z.number().int().min(1).max(5),
  pass_at_1: z.number().min(0).max(1),
  n_tasks: z.number().int().nonnegative(),
});
export type MBPPBucket = z.infer<typeof MBPPBucketSchema>;

export const BenchmarkResultsSchema = z.object({
  se50: BenchmarkSummarySchema,
  se50_rows: z.array(BenchmarkRowSchema).default([]),
  humaneval_pass_at_1: z.number().min(0).max(1).default(0),
  humaneval_buckets: z.array(HumanEvalBucketSchema).default([]),
  mbpp_pass_at_1: z.number().min(0).max(1).default(0),
  mbpp_buckets: z.array(MBPPBucketSchema).default([]),
  ablation_table: AblationTableSchema,
  signoff_avg_conf: z.number().min(0).max(1).default(0),
});
export type BenchmarkResults = z.infer<typeof BenchmarkResultsSchema>;
