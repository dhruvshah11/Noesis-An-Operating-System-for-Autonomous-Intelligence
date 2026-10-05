import { describe, expect, it } from "vitest";

import { buildMockConversations } from "@/testing/mocks";
import { buildMockDocuments } from "@/testing/mocks";
import { buildMockMemory } from "@/testing/mocks";
import { buildMockObservability } from "@/testing/mocks";
import { buildMockTraces } from "@/testing/mocks";
import type { ExecutionTrace, ObservabilitySummary } from "@/lib/schemas";

describe("Seeded mock builders (mulberry32 deterministic)", () => {
  it("buildMockObservability(seed) is deterministic across two calls", () => {
    const a = buildMockObservability(3);
    const b = buildMockObservability(3);
    expect(a).toEqual(b);
    expect(a.total_cost_usd).toBeGreaterThanOrEqual(0);
    expect(a.latency_ms.avg).toBeGreaterThanOrEqual(0);
    expect(a.latency_ms.p50).toBeGreaterThanOrEqual(0);
    expect(a.latency_ms.p95).toBeGreaterThanOrEqual(0);
    expect(a.latency_ms.p99).toBeGreaterThanOrEqual(0);
  });

  it("buildMockObservability returns ObservabilitySummary-compatible shape", () => {
    const out: ObservabilitySummary = buildMockObservability(7);
    expect(out.window_s).toBeGreaterThan(0);
    expect(out.total_prompt_tokens + out.total_completion_tokens).toBe(out.total_tokens);
  });

  it("buildMockTraces(7) produces 4 traces (one per query)", () => {
    const traces = buildMockTraces(7);
    expect(traces).toHaveLength(4);
  });

  it("buildMockTraces is deterministic", () => {
    const a = buildMockTraces(7);
    const b = buildMockTraces(7);
    expect(a.map((t) => t.trace_id)).toEqual(b.map((t) => t.trace_id));
  });

  it("buildMockTraces every trace_id is prefixed with trace- and step.statuses are valid enum", () => {
    const valid = new Set(["success", "skipped", "running", "failed", "pending"]);
    const traces: ExecutionTrace[] = buildMockTraces(2);
    for (const t of traces) {
      expect(t.trace_id.startsWith("trace-")).toBe(true);
      for (const s of t.plan_steps) {
        expect(valid.has(s.status)).toBe(true);
      }
    }
  });

  it("buildMockMemory default n=48, each record has valid tier and score in [-1,1]", () => {
    const mem = buildMockMemory(1337, 30);
    expect(mem).toHaveLength(30);
    const validTiers = new Set([
      "conversation",
      "user",
      "project",
      "episodic",
      "semantic",
      "working",
    ]);
    for (const m of mem) {
      expect(validTiers.has(m.tier)).toBe(true);
      expect(m.score).toBeGreaterThanOrEqual(-1);
      expect(m.score).toBeLessThanOrEqual(1);
    }
  });

  it("buildMockMemory(seed) determinism", () => {
    const a = buildMockMemory(42, 10);
    const b = buildMockMemory(42, 10);
    expect(a.map((m) => m.id)).toEqual(b.map((m) => m.id));
  });

  it("buildMockConversations default produces 7 rows (one title per entry)", () => {
    const convs = buildMockConversations(5);
    expect(convs).toHaveLength(7);
    const c0 = convs[0];
    if (!c0) throw new Error("empty convs");
    expect(c0.messages).toBeGreaterThan(0);
    expect(c0.tokens).toBeGreaterThan(0);
  });

  it("buildMockConversations determinism", () => {
    const a = buildMockConversations(5);
    const b = buildMockConversations(5);
    expect(a.map((c) => c.id)).toEqual(b.map((c) => c.id));
  });

  it("buildMockDocuments(seed, n) default n=12 with valid statuses", () => {
    const docs = buildMockDocuments(8);
    expect(docs).toHaveLength(12);
    const valid = new Set(["queued", "processing", "indexed", "failed"]);
    for (const d of docs) {
      expect(valid.has(d.status)).toBe(true);
      expect(d.chunks).toBeGreaterThanOrEqual(0);
    }
  });

  it("buildMockDocuments determinism", () => {
    const a = buildMockDocuments(8);
    const b = buildMockDocuments(8);
    expect(a.map((d) => d.id)).toEqual(b.map((d) => d.id));
  });
});
