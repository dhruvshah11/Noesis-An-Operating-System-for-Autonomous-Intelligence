import {
  BenchmarkResultsSchema,
  ExecutionTraceSchema,
  MemoryRecordSchema,
  ObservabilitySummarySchema,
  TokenPairSchema,
} from "@/lib/schemas";
import type {
  BenchmarkResults,
  ExecutionTrace,
  MemoryRecord,
  ObservabilitySummary,
  TokenPair,
} from "@/lib/schemas";
import { requestJson } from "@/lib/api/http";
import type { Agent, Conversation, Document } from "@/testing/mocks";
import { buildMockBenchResults } from "@/testing/mocks";

// ===========================================================================
// High-level API facade (backend endpoints).
// Each endpoint takes explicit params, returns a parsed-and-validated Zod
// schema (runtime type safety + TypeScript inference from one source).
// ===========================================================================

export async function login(user_id: string, password: string): Promise<TokenPair> {
  const raw = await requestJson("/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ user_id, password }),
  });
  return TokenPairSchema.parse(raw);
}

export async function fetchObservability(
  window_s = 3600,
  token?: string | null,
): Promise<ObservabilitySummary> {
  const q = new URLSearchParams({ window_s: String(window_s) });
  const init: { token?: string | null } = {};
  if (typeof token !== "undefined") init.token = token;
  const raw = await requestJson(`/observability/summary?${q.toString()}`, init);
  return ObservabilitySummarySchema.parse(raw);
}

export async function fetchMe<T = { sub: string; roles: string[] }>(
  token: string,
): Promise<T> {
  return await requestJson<T>("/v1/auth/me", { token });
}

// ---- Agent execution (future backend routes; offline mock below) ---------
// These will become real endpoints once M4/M5 kernel-execution HTTP API
// lands.  For now, they gracefully throw HttpError(404) so UI can still
// exercise the offline mock path without crashing.

export async function listTraces(): Promise<ExecutionTrace[]> {
  try {
    const raw = await requestJson("/agents/traces");
    if (Array.isArray(raw)) return raw.map((r) => ExecutionTraceSchema.parse(r));
    return [];
  } catch (e) {
    if (e instanceof Error && "status" in e && (e as { status?: number }).status === 404) {
      return [];
    }
    throw e;
  }
}

export async function listMemory(): Promise<MemoryRecord[]> {
  try {
    const raw = await requestJson("/v1/memory");
    if (Array.isArray(raw)) return raw.map((r) => MemoryRecordSchema.parse(r));
    return [];
  } catch (e) {
    if (e instanceof Error && "status" in e && (e as { status?: number }).status === 404) {
      return [];
    }
    throw e;
  }
}

export async function listConversations(): Promise<Conversation[]> {
  try {
    const raw = await requestJson("/v1/conversations");
    if (Array.isArray(raw)) return raw as Conversation[];
    return [];
  } catch (e) {
    if (e instanceof Error && "status" in e && (e as { status?: number }).status === 404) {
      return [];
    }
    throw e;
  }
}

export async function createConversation(payload: { title: string; agent?: string }): Promise<Conversation> {
  const raw = await requestJson("/v1/conversations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return raw as Conversation;
}

export async function listDocuments(): Promise<Document[]> {
  try {
    const raw = await requestJson("/v1/documents");
    if (Array.isArray(raw)) return raw as Document[];
    return [];
  } catch (e) {
    if (e instanceof Error && "status" in e && (e as { status?: number }).status === 404) {
      return [];
    }
    throw e;
  }
}

export async function uploadDocument(formData: FormData): Promise<Document> {
  const raw = await requestJson("/v1/documents/upload", {
    method: "POST",
    body: formData as unknown as BodyInit,
  });
  return raw as Document;
}

export async function listAgents(): Promise<Agent[]> {
  try {
    const raw = await requestJson("/v1/agents");
    if (Array.isArray(raw)) return raw as Agent[];
    return [];
  } catch (e) {
    if (e instanceof Error && "status" in e && (e as { status?: number }).status === 404) {
      return [];
    }
    throw e;
  }
}

export interface ExecuteRunRequest {
  readonly agent_id?: string;
  readonly prompt: string;
}

export interface ExecuteRunResponse {
  readonly run_id: string;
  readonly status: "pending" | "running" | "success" | "failed";
  readonly nodes: readonly {
    readonly id: string;
    readonly name: string;
    readonly status: "pending" | "running" | "success" | "failed";
    readonly progress: number;
    readonly started_at?: number;
    readonly ended_at?: number;
  }[];
}

export async function executeRun(req: ExecuteRunRequest): Promise<ExecuteRunResponse> {
  const raw = await requestJson("/v1/runs/execute", {
    method: "POST",
    body: JSON.stringify(req),
  });
  return raw as ExecuteRunResponse;
}

// ---- Benchmark results (MS8 Studio benchmarks hub) -----------------------
// Real endpoint: GET /api/bench/results — currently returns 404; falls back
// to buildMockBenchResults(seed=42) after a short sleep so the UI can still
// demonstrate the full layout even without the backend live.

const BENCH_SLEEP_MS = 600;

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

export async function fetchBenchResults(seed = 42): Promise<BenchmarkResults> {
  try {
    const raw = await requestJson("/api/bench/results");
    if (raw && typeof raw === "object") {
      try {
        return BenchmarkResultsSchema.parse(raw);
      } catch {
        // fall through to mock
      }
    }
  } catch (e) {
    if (!(e instanceof Error && "status" in e && (e as { status?: number }).status === 404)) {
      // non-404: still fall back to mock so the UI doesn't crash
    }
  }
  await sleep(BENCH_SLEEP_MS);
  return buildMockBenchResults(seed);
}
