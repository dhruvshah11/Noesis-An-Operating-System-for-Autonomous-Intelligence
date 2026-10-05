import { describe, expect, it } from "vitest";

import {
  JwtClaimsSchema,
  MemoryTierZ,
  ObservabilitySummarySchema,
  PlanStepStatusZ,
  TokenPairSchema,
  ToolCallSchema,
  ToolMetricSchema,
} from "@/lib/schemas";

describe("Zod schemas (contract parity with backend Pydantic)", () => {
  it("TokenPairSchema accepts valid access/refresh pair and defaults token_type to Bearer", () => {
    const parsed = TokenPairSchema.parse({
      access_token: "a".repeat(32),
      refresh_token: "b".repeat(32),
    });
    expect(parsed.token_type).toBe("Bearer");
    expect(parsed.access_token).toHaveLength(32);
    expect(parsed.refresh_token).toHaveLength(32);
  });

  it("TokenPairSchema rejects short tokens", () => {
    expect(() =>
      TokenPairSchema.parse({ access_token: "short", refresh_token: "b".repeat(32) }),
    ).toThrow();
  });

  it("JwtClaimsSchema defaults roles and scopes to empty arrays", () => {
    const parsed = JwtClaimsSchema.parse({
      sub: "u-1",
      iat: 1700000000,
      exp: 1700003600,
      iss: "astraos.local",
    });
    expect(parsed.roles).toEqual([]);
    expect(parsed.scopes).toEqual([]);
    expect(parsed.kind).toBe("access");
  });

  it("ToolMetricSchema requires nonnegative numerics", () => {
    expect(() =>
      ToolMetricSchema.parse({
        tool_name: "git.status",
        invocations: -1,
        errors: 0,
        total_ms: 0,
        avg_ms: 0,
        p50_ms: 0,
        p95_ms: 0,
        p99_ms: 0,
      }),
    ).toThrow();
  });

  it("ObservabilitySummarySchema defaults tools to []", () => {
    const parsed = ObservabilitySummarySchema.parse({
      window_s: 60,
      total_requests: 100,
      total_prompt_tokens: 1000,
      total_completion_tokens: 500,
      total_tokens: 1500,
      total_cost_usd: 0.002,
      latency_ms: { avg: 100, p50: 80, p95: 220, p99: 310 },
    });
    expect(parsed.tools).toEqual([]);
    expect(parsed.latency_ms.p99).toBe(310);
  });

  it("ObservabilitySummarySchema rejects non-object latency_ms", () => {
    expect(() =>
      ObservabilitySummarySchema.parse({
        window_s: 60,
        total_requests: 0,
        total_prompt_tokens: 0,
        total_completion_tokens: 0,
        total_tokens: 0,
        total_cost_usd: 0,
        latency_ms: { avg: 0, p50: 0, p95: 0 } as unknown as {
          avg: number;
          p50: number;
          p95: number;
          p99: number;
        },
      }),
    ).toThrow();
  });

  it("PlanStepStatusZ enum matches the 5 published values", () => {
    expect(PlanStepStatusZ.options).toEqual(["pending", "running", "success", "failed", "skipped"]);
  });

  it("MemoryTierZ enum contains exactly the 6 published tiers (any order)", () => {
    expect(new Set(MemoryTierZ.options as readonly string[])).toEqual(
      new Set(["conversation", "user", "project", "episodic", "semantic", "working"]),
    );
  });

  it("ToolCallSchema accepts partial optional fields", () => {
    const parsed = ToolCallSchema.parse({
      id: "tc-1",
      name: "shell.exec",
      args: { cmd: "ls" },
      started_at: 1700000000,
    });
    expect(parsed.ended_at).toBeUndefined();
    expect(parsed.success).toBeUndefined();
    expect(parsed.exit_code).toBeUndefined();
    expect(parsed.stdout_snippet).toBeUndefined();
  });

  it("ToolCallSchema rejects non-record args", () => {
    expect(() =>
      ToolCallSchema.parse({
        id: "tc-1",
        name: "shell.exec",
        args: ["not", "a", "record"],
        started_at: 1700000000,
      }),
    ).toThrow();
  });
});
