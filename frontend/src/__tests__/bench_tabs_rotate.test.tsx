import type { ReactElement } from "react";
import { act, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

class ResizeObserverMock {
  observe() {
    void 0;
  }
  unobserve() {
    void 0;
  }
  disconnect() {
    void 0;
  }
}
vi.stubGlobal("ResizeObserver", ResizeObserverMock);

vi.mock("@/lib/demo", () => ({
  useDemoMode: () => ({
    isDemoMode: false,
    seed: 42,
    conversations: [],
    memoryItems: [],
    agents: [],
    workflowNodes: [],
  }),
  DemoPipelineSankey: () => null,
}));

import BenchmarksPage from "../../app/benchmarks/page";

function renderWithQueryClient(ui: ReactElement): ReturnType<typeof render> {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: 0 },
      mutations: { retry: 0 },
    },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function getActiveTabLabel(): string {
  const tabs = screen.getAllByRole("tab");
  for (const t of tabs) {
    if (t.getAttribute("aria-selected") === "true") {
      return t.textContent || "";
    }
  }
  return "";
}

describe("Benchmarks Hub tab auto-rotation", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("initial tab on mount is SE50 Corpus", () => {
    renderWithQueryClient(<BenchmarksPage />);
    expect(getActiveTabLabel()).toBe("SE50 Corpus");
  });

  it("after 35s rotates to HumanEval; after 95s total reaches Ablations (3 cycles of 30s)", () => {
    renderWithQueryClient(<BenchmarksPage />);
    expect(getActiveTabLabel()).toBe("SE50 Corpus");

    act(() => {
      vi.advanceTimersByTime(35_000);
    });
    expect(getActiveTabLabel()).toBe("HumanEval");

    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(getActiveTabLabel()).toBe("Ablations");
  });
});
