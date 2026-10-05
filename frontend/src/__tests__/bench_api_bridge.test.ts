import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fetchBenchResults, getBenchBackendBase } from "@/lib/api/bench";
import { DEMO_BENCH_RESULTS } from "@/lib/mock/bench_results_demo";
import { BenchmarkResultsSchema } from "@/lib/schemas";
import { buildMockBenchResults } from "@/testing/mocks";

function validLivePayload() {
  return buildMockBenchResults(99);
}

describe("Bench API bridge (fetchBenchResults + getBenchBackendBase)", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    // Ensure we don't leak process.env modifications across tests
    if (typeof globalThis.process !== "undefined") {
      const env = globalThis.process.env as Record<string, string | undefined>;
      delete env.NEXT_PUBLIC_API_URL;
      delete env.NEXT_PUBLIC_API_BASE_URL;
    }
  });

  describe("getBenchBackendBase", () => {
    it("defaults to http://localhost:8000 when both env vars are unset", () => {
      const env = (globalThis.process as { env: Record<string, string | undefined> }).env;
      delete env.NEXT_PUBLIC_API_URL;
      delete env.NEXT_PUBLIC_API_BASE_URL;
      expect(getBenchBackendBase()).toBe("http://localhost:8000");
    });

    it("picks NEXT_PUBLIC_API_URL over NEXT_PUBLIC_API_BASE_URL", () => {
      const env = (globalThis.process as { env: Record<string, string | undefined> }).env;
      env.NEXT_PUBLIC_API_URL = "https://api.example.com";
      env.NEXT_PUBLIC_API_BASE_URL = "https://ignored.example.com";
      expect(getBenchBackendBase()).toBe("https://api.example.com");
    });

    it("falls back to NEXT_PUBLIC_API_BASE_URL when NEXT_PUBLIC_API_URL is absent", () => {
      const env = (globalThis.process as { env: Record<string, string | undefined> }).env;
      delete env.NEXT_PUBLIC_API_URL;
      env.NEXT_PUBLIC_API_BASE_URL = "http://10.0.0.1:9000/";
      expect(getBenchBackendBase()).toBe("http://10.0.0.1:9000");
    });
  });

  describe("fetchBenchResults", () => {
    it("resolves demo=false when fetch returns 200 with valid BenchmarkResults (direct body)", async () => {
      const payload = validLivePayload();
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({
          ok: true,
          json: () => Promise.resolve(payload),
        }),
      );

      const env = (globalThis.process as { env: Record<string, string | undefined> }).env;
      env.NEXT_PUBLIC_API_URL = "http://localhost:8000";

      const result = await fetchBenchResults();
      expect(result.demo).toBe(false);
      expect(result.source).toContain("backend /api/bench/results");
      expect(result.source).toContain("http://localhost:8000");
      expect(() => BenchmarkResultsSchema.parse(result.data)).not.toThrow();
      expect(result.data.se50.overall_pass_at_1).toBe(payload.se50.overall_pass_at_1);
    });

    it("extracts data from envelope { ok, data } and validates", async () => {
      const payload = validLivePayload();
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({
          ok: true,
          json: () => Promise.resolve({ ok: true, data: payload }),
        }),
      );

      const result = await fetchBenchResults();
      expect(result.demo).toBe(false);
      expect(result.data.se50.n_total).toBe(payload.se50.n_total);
    });

    it("reads backend demo flag from envelope { demo: true } and propagates demo=true", async () => {
      const payload = validLivePayload();
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({
          ok: true,
          json: () => Promise.resolve({ data: payload, demo: true }),
        }),
      );

      const result = await fetchBenchResults();
      expect(result.demo).toBe(true);
      expect(result.source).toContain("backend demo flag");
    });

    it("reads backend demo flag from nested meta.demo", async () => {
      const payload = validLivePayload();
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({
          ok: true,
          json: () => Promise.resolve({ data: payload, meta: { demo: true } }),
        }),
      );

      const result = await fetchBenchResults();
      expect(result.demo).toBe(true);
    });

    it("falls back to demo=true + DEMO_BENCH_RESULTS shape when network throws", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
      );

      const result = await fetchBenchResults();
      expect(result.demo).toBe(true);
      expect(result.source).toContain("demo (fallback:");
      expect(result.source).toContain("Failed to fetch");
      expect(result.data).toStrictEqual(DEMO_BENCH_RESULTS);
      expect(result.data.se50.overall_pass_at_1).toBe(0.4);
      expect(result.data.humaneval_pass_at_1).toBe(0);
      expect(result.data.mbpp_pass_at_1).toBe(0);
      expect(result.data.se50_rows).toHaveLength(0);
    });

    it("falls back to demo when response is non-2xx", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({
          ok: false,
          status: 503,
          json: () => Promise.resolve({ detail: "Unavailable" }),
        }),
      );

      const result = await fetchBenchResults();
      expect(result.demo).toBe(true);
      expect(result.source).toContain("demo (fallback:");
      expect(result.source).toContain("HTTP 503");
      expect(result.data).toStrictEqual(DEMO_BENCH_RESULTS);
    });

    it("falls back to demo when JSON body fails schema validation", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({
          ok: true,
          json: () => Promise.resolve({ se50: "garbage", not_valid: true }),
        }),
      );

      const result = await fetchBenchResults();
      expect(result.demo).toBe(true);
      expect(result.source).toContain("demo (fallback:");
      expect(result.data).toStrictEqual(DEMO_BENCH_RESULTS);
    });

    it("falls back to demo when response body is not valid JSON", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({
          ok: true,
          json: () => Promise.reject(new SyntaxError("Unexpected token")),
        }),
      );

      const result = await fetchBenchResults();
      expect(result.demo).toBe(true);
      expect(result.source).toContain("demo (fallback:");
      expect(result.source).toContain("Invalid JSON");
      expect(result.data).toStrictEqual(DEMO_BENCH_RESULTS);
    });

    it("DEMO_BENCH_RESULTS itself passes BenchmarkResultsSchema", () => {
      expect(() => BenchmarkResultsSchema.parse(DEMO_BENCH_RESULTS)).not.toThrow();
    });

    it("buildMockBenchResults(42) passes BenchmarkResultsSchema (layout mock)", () => {
      expect(() => BenchmarkResultsSchema.parse(buildMockBenchResults(42))).not.toThrow();
    });
  });
});
