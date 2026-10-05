/**
 * Backend API base URL resolution — used by `src/lib/api/client.ts`.
 * Order: (1) window injected at runtime, (2) NEXT_PUBLIC_API_BASE (default:
 * /api/backend/v1 which is rewritten to BACKEND_BASE_URL via next.config).
 */
import { toast } from "sonner";

export const API_BASE: string = (() => {
  if (typeof globalThis.process !== "undefined") {
    const val = globalThis.process.env.NEXT_PUBLIC_API_BASE;
    if (val) return val;
  }
  return "/api/backend/v1";
})();

export interface ApiError {
  readonly status: number;
  readonly detail?: unknown;
}

export class HttpError extends Error implements ApiError {
  public readonly status: number;
  public readonly detail: unknown;
  constructor(status: number, detail?: unknown, message?: string) {
    super(message ?? `HTTP ${status}`);
    this.name = "HttpError";
    this.status = status;
    this.detail = detail;
  }
}

export async function requestJson<T = unknown>(
  path: string,
  init?: RequestInit & { token?: string | null; silent?: boolean },
): Promise<T> {
  const url = path.startsWith("http:") || path.startsWith("https:") ? path : `${API_BASE}${path}`;
  const headers = new Headers(init?.headers ?? {});
  headers.set("Accept", "application/json");
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (init?.token) headers.set("Authorization", `Bearer ${init.token}`);

  const res = await fetch(url, { ...init, headers });
  const text = await res.text();
  const body: unknown = text.length ? (safeJsonParse(text) ?? text) : undefined;

  if (!res.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? (body as { detail?: unknown }).detail
        : body;
    const detailText = typeof detail === "string" ? detail : typeof detail === "number" ? String(detail) : undefined;
    if (!init?.silent) {
      emitHttpToast(res.status, detailText);
    }
    throw new HttpError(res.status, detail, detailText);
  }

  return body as T;
}

// ---------------------------------------------------------------------------
// Private helpers
// ---------------------------------------------------------------------------

function emitHttpToast(status: number, detail?: string): void {
  switch (true) {
    case status === 401:
      toast.error("Session expired", {
        description: detail ?? "Please sign in again to continue.",
        action: {
          label: "Sign in",
          onClick: () => {
            if (typeof window !== "undefined") {
              window.location.href = "/sign-in";
            }
          },
        },
      });
      break;
    case status === 403:
      toast.error("Permission denied", {
        description: detail ?? "Your account is not allowed to perform this action.",
      });
      break;
    case status === 429:
      toast.warning("Slow down", {
        description: detail ?? "Too many requests — retry in a few moments.",
        duration: 6000,
      });
      break;
    case status >= 500 && status < 600:
      toast.error("Backend error", {
        description: detail ?? `Noesis kernel returned HTTP ${status}. Check ` + `\`docker compose -f docker-compose.laptop.yml ps\` for service health.`,
        duration: 8000,
      });
      break;
    default:
      // 400 / 404 / 409 / 422 are user-facing or handled inline (404 is used
      // for graceful "not-yet-implemented endpoint" fallbacks inside
      // endpoints.ts listTraces / listMemory, etc.) — skip global toast.
      break;
  }
}

function safeJsonParse(text: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return undefined;
  }
}
