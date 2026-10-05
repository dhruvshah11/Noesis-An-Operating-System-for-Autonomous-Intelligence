import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { HttpError, requestJson } from "@/lib/api/http";

describe("HTTP wrapper (requestJson + HttpError)", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("API_BASE defaults to /api/backend/v1 when NEXT_PUBLIC_API_BASE unset", async () => {
    const { API_BASE } = await import("@/lib/api/http");
    expect(API_BASE).toBe("/api/backend/v1");
  });

  it("requestJson prepends API_BASE to relative paths", async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve(JSON.stringify({ ok: true })),
    });
    vi.stubGlobal("fetch", fetch);
    await requestJson("/traces");
    expect(fetch).toHaveBeenCalledTimes(1);
    const lastCall = fetch.mock.lastCall;
    if (!lastCall) throw new Error("no last call");
    const calledUrl: string = lastCall[0] as string;
    expect(calledUrl).toContain("/api/backend/v1/traces");
  });

  it("requestJson keeps absolute http/https URLs untouched", async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve(JSON.stringify({ hello: "world" })),
    });
    vi.stubGlobal("fetch", fetch);
    await requestJson("https://example.com/x");
    expect(fetch).toHaveBeenCalledTimes(1);
    const lastCall = fetch.mock.lastCall;
    if (!lastCall) throw new Error("no last call");
    expect(lastCall[0]).toBe("https://example.com/x");
  });

  it("requestJson sets Accept: application/json", async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve("[]"),
    });
    vi.stubGlobal("fetch", fetch);
    await requestJson("/traces");
    expect(fetch).toHaveBeenCalledTimes(1);
    const lastCall = fetch.mock.lastCall;
    if (!lastCall) throw new Error("no last call");
    const init = lastCall[1] as RequestInit;
    expect((init.headers as Headers).get("Accept")).toBe("application/json");
  });

  it("requestJson sets Authorization: Bearer <token> when token provided", async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve("{}"),
    });
    vi.stubGlobal("fetch", fetch);
    await requestJson("/me", { token: "tk-abc" });
    expect(fetch).toHaveBeenCalledTimes(1);
    const lastCall = fetch.mock.lastCall;
    if (!lastCall) throw new Error("no last call");
    const init = lastCall[1] as RequestInit;
    expect((init.headers as Headers).get("Authorization")).toBe("Bearer tk-abc");
  });

  it("requestJson parses JSON response into typed value", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        text: () => Promise.resolve(JSON.stringify({ a: 1, b: "c" })),
      }),
    );
    const out = await requestJson<{ a: number; b: string }>("/x");
    expect(out.a).toBe(1);
    expect(out.b).toBe("c");
  });

  it("requestJson falls back to raw text when JSON parse fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        text: () => Promise.resolve("not valid json"),
      }),
    );
    const out = await requestJson("/x");
    expect(out).toBe("not valid json");
  });

  it("requestJson returns undefined for empty body on success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        text: () => Promise.resolve(""),
      }),
    );
    const out = await requestJson("/x");
    expect(out).toBeUndefined();
  });

  it("requestJson throws HttpError with status on 5xx", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        text: () => Promise.resolve(JSON.stringify({ detail: "Unavailable" })),
      }),
    );
    await expect(requestJson("/x")).rejects.toBeInstanceOf(HttpError);
    try {
      await requestJson("/x");
    } catch (err) {
      expect((err as HttpError).status).toBe(503);
      expect((err as HttpError).detail).toBe("Unavailable");
    }
  });

  it("requestJson extracts detail property from 4xx error body", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        text: () =>
          Promise.resolve(JSON.stringify({ detail: { code: "bad_token" }, extra: "x" })),
      }),
    );
    try {
      await requestJson("/x");
    } catch (err) {
      expect((err as HttpError).status).toBe(401);
      expect((err as HttpError).detail).toEqual({ code: "bad_token" });
    }
  });

  it("HttpError.message respects custom override", () => {
    const e = new HttpError(400, "boo", "custom message");
    expect(e.status).toBe(400);
    expect(e.detail).toBe("boo");
    expect(e.message).toBe("custom message");
    expect(e.name).toBe("HttpError");
  });
});
