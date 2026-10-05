import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ExecutionTimeline, MiniTimeline } from "@/components/timeline/ExecutionTimeline";
import { buildMockTraces } from "@/testing/mocks";

describe("<ExecutionTimeline /> widget", () => {
  it("renders 4 trace selector chips (trace ids 1000..1003)", () => {
    render(<ExecutionTimeline traces={buildMockTraces(1)} />);
    // 4 chips exist: "#1000 · Summarise Q2 OKRs", "#1001 · avatar upload", etc.
    expect(screen.getAllByRole("button", { name: /#100[0-3]/ }).length).toBeGreaterThanOrEqual(4);
    // Chip + sidebar both show Q2 text
    expect(screen.getAllByText(/Summarise Q2 OKRs/).length).toBeGreaterThanOrEqual(1);
  });

  it("MiniTimeline uses the 'Latest agent runs' custom title (compact variant)", () => {
    render(<MiniTimeline traces={buildMockTraces(1)} />);
    expect(screen.getByRole("heading", { level: 2, name: "Latest agent runs" })).toBeTruthy();
  });

  it("step with tool_calls renders shell.exec chip when expanded by default", async () => {
    const traces = buildMockTraces(1);
    // By default StepRow opens when status === "failed" && tool_calls > 0
    expect(traces.length).toBeGreaterThan(0);
    const t0 = traces[0];
    if (!t0) throw new Error("missing first trace");
    expect(t0.plan_steps.length).toBeGreaterThan(0);
    const s0 = t0.plan_steps[0];
    if (!s0) throw new Error("missing first step");
    s0.status = "failed";
    s0.tool_calls = [
      {
        id: "tc-1",
        name: "shell.exec",
        args: { cmd: "git status" },
        started_at: 1700000000,
        ended_at: 1700000001,
        success: false,
        exit_code: 1,
      },
    ];
    render(<ExecutionTimeline traces={traces} />);
    await waitFor(() => screen.getAllByText("shell.exec"));
    expect(screen.getAllByText("shell.exec").length).toBeGreaterThan(0);
  });
});
