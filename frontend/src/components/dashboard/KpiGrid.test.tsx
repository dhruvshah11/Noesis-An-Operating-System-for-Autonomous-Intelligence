import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { KpiGrid } from "@/components/dashboard/KpiGrid";
import { buildMockObservability } from "@/testing/mocks";

describe("<KpiGrid /> dashboard overview tiles", () => {
  it("renders 8 KPI tile labels with mocked data", () => {
    render(<KpiGrid summary={buildMockObservability(2)} />);
    const labels = [
      "Agent executions",
      "Total tokens",
      "Estimated cost",
      "P95 latency",
      "Memory recalls",
      "Tool invocations",
      "Active traces",
      "Autonomy score",
    ];
    for (const l of labels) {
      expect(screen.getByText(l)).toBeTruthy();
    }
  });

  it("formats p95 latency using the ms suffix", () => {
    const summary = buildMockObservability(2);
    summary.latency_ms.p95 = 425;
    render(<KpiGrid summary={summary} />);
    expect(screen.getByText("425 ms")).toBeTruthy();
  });

  it("formats est cost as USD dollars to 4 decimals", () => {
    const summary = buildMockObservability(2);
    summary.total_cost_usd = 0.1234;
    render(<KpiGrid summary={summary} />);
    expect(screen.getByText("$0.1234")).toBeTruthy();
  });
});
