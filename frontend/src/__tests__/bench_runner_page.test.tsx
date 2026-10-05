import type { ReactElement } from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import BenchmarkRunnerPage from "../../app/agents/benchmark/page";

function renderWithQueryClient(ui: ReactElement): ReturnType<typeof render> {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: 0 },
      mutations: { retry: 0 },
    },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("Benchmark Runner page (/agents/benchmark)", () => {
  it("form renders all fields + Run button", () => {
    renderWithQueryClient(<BenchmarkRunnerPage />);
    expect(screen.getByTestId("bench-runner-form")).toBeTruthy();
    expect(screen.getByTestId("task-id-input")).toBeTruthy();
    expect(screen.getByTestId("mode-select")).toBeTruthy();
    expect(screen.getByTestId("model-select")).toBeTruthy();
    expect(screen.getByTestId("run-button")).toBeTruthy();
    expect(screen.getByTestId("run-button").textContent).toContain("Run");
  });

  it("mode dropdown has seeded and adaptive options", () => {
    renderWithQueryClient(<BenchmarkRunnerPage />);
    const modeSelect = screen.getByTestId("mode-select");
    const optionElements = within(modeSelect).getAllByRole("option");
    const values: string[] = [];
    for (const o of optionElements) {
      if (o instanceof HTMLOptionElement) values.push(o.value);
    }
    expect(values).toContain("seeded");
    expect(values).toContain("adaptive");
    expect(values.length).toBe(2);
  });

  it("submit builds correct GET /llm/benchmark fetch shape with query params", async () => {
    const user = userEvent.setup();
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(
      (_input: RequestInfo | URL, _init?: RequestInit) =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              ok: true,
              data: {
                task_id: "SE50-042",
                mode: "adaptive",
                model: "deepseek-coder-v2:16b",
                tristate: "signoff",
                duration_ms: 4200,
                kriyakari_conf: 0.91,
                plan_sha: "sha256:abcdef1234567890",
                signoff_reason: "test ok",
              },
              demo: false,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        ),
    );

    renderWithQueryClient(<BenchmarkRunnerPage />);

    await user.type(screen.getByTestId("task-id-input"), "SE50-042");
    await user.selectOptions(screen.getByTestId("mode-select"), "adaptive");
    await user.selectOptions(screen.getByTestId("model-select"), "deepseek-coder-v2:16b");
    await user.click(screen.getByTestId("run-button"));

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const call = fetchSpy.mock.calls.at(0);
    expect(call).toBeDefined();
    const firstArg = call?.[0];
    const init = call?.[1];
    const url = typeof firstArg === "string" ? firstArg : firstArg instanceof URL ? firstArg.toString() : "";
    expect(url).toContain("/llm/benchmark");
    expect(url).toContain("task_id=SE50-042");
    expect(url).toContain("mode=adaptive");
    expect(url).toContain("model=deepseek-coder-v2%3A16b");

    const headers = new Headers(init?.headers ?? {});
    expect(headers.get("X-Noesis-Capability-Token")).toBeTruthy();
    expect(headers.get("Accept")).toBe("application/json");

    fetchSpy.mockRestore();
  });
});
