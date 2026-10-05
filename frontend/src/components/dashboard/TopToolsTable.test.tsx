import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TopToolsTable } from "@/components/dashboard/TopToolsTable";
import { buildMockObservability } from "@/testing/mocks";
import type { ToolMetric } from "@/lib/schemas";

describe("<TopToolsTable /> dashboard widget", () => {
  it("renders header + rows sorted by invocations desc", () => {
    const summary = buildMockObservability(4);
    const fakeTools: ToolMetric[] = [
      {
        tool_name: "low",
        invocations: 10,
        errors: 0,
        total_ms: 100,
        avg_ms: 10,
        p50_ms: 9,
        p95_ms: 20,
        p99_ms: 30,
      },
      {
        tool_name: "high",
        invocations: 100,
        errors: 0,
        total_ms: 1000,
        avg_ms: 10,
        p50_ms: 9,
        p95_ms: 20,
        p99_ms: 30,
      },
      {
        tool_name: "mid",
        invocations: 50,
        errors: 1,
        total_ms: 500,
        avg_ms: 10,
        p50_ms: 9,
        p95_ms: 20,
        p99_ms: 30,
      },
    ];
    summary.tools = fakeTools;
    render(<TopToolsTable summary={summary} />);
    const cells = screen.getAllByRole("cell");
    expect(cells.length).toBeGreaterThanOrEqual(2);
    const first = cells[0];
    const second = cells[1];
    if (!first || !second) throw new Error("not enough cells");
    // Expect the leftmost tool cell to be "high" because it's sorted desc
    expect(first.textContent).toBe("high");
    expect(second.textContent).toBe("100");
  });

  it("shows error rate percentage when a tool has errors > 0", () => {
    const summary = buildMockObservability(4);
    summary.tools = [
      {
        tool_name: "flaky",
        invocations: 100,
        errors: 5,
        total_ms: 500,
        avg_ms: 5,
        p50_ms: 4,
        p95_ms: 10,
        p99_ms: 15,
      },
    ];
    render(<TopToolsTable summary={summary} />);
    expect(screen.getByText("(5.0%)")).toBeTruthy();
  });

  it("shows empty state when tools array is empty", () => {
    const summary = buildMockObservability(4);
    summary.tools = [];
    render(<TopToolsTable summary={summary} />);
    expect(screen.getByText(/No tool invocations yet\. Try running an agent/i)).toBeTruthy();
  });
});
