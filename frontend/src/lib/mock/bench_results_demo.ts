import type { BenchmarkResults } from "@/lib/schemas";

/**
 * Minimal fallback demo placeholder for benchmark results.
 * Matches schema defaults: SE50 overall pass@1 = 0.40, HumanEval = 0,
 * MBPP = 0, empty rows. Used when the backend endpoint is unreachable
 * or returns invalid / empty data so the page layout does not collapse.
 */
export const DEMO_BENCH_RESULTS: BenchmarkResults = {
  se50: {
    overall_pass_at_1: 0.4,
    overall_ci_low: 0.27,
    overall_ci_high: 0.53,
    n_total: 0,
    n_correct: 0,
    per_category: [],
    per_difficulty: [],
  },
  se50_rows: [],
  humaneval_pass_at_1: 0,
  humaneval_buckets: [],
  mbpp_pass_at_1: 0,
  mbpp_buckets: [],
  ablation_table: {
    variant_keys: ["baseline_nomem", "baseline_nomac", "full_noesis"],
    rows: [],
    notes: {},
  },
  signoff_avg_conf: 0,
};
