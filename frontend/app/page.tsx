"use client";

import { Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { KpiGrid } from "@/components/dashboard/KpiGrid";
import { MiniTimeline } from "@/components/dashboard/MiniTimeline";
import { TopToolsTable } from "@/components/dashboard/TopToolsTable";
import { QuickActionsStrip } from "@/components/dashboard/QuickActionsStrip";
import { MetricsDashboard } from "@/components/dashboard/MetricsDashboard";
import { buildMockObservability, buildMockTraces } from "@/testing/mocks";
import { fetchObservability, listTraces } from "@/lib/api/endpoints";
import { NOESIS_BRAND } from "@/lib/brand";
import { DemoPipelineSankey, useDemoMode } from "@/lib/demo";
import { PALETTE } from "@/lib/agents_codenames";

const AGENT_PALETTE_LEGEND = [
  {
    label: "Planning / Analysis / Research / Supervisory / Memory",
    agents: "Manan · Darshak · Anveshak · Nirikshak · Paalak",
    hex: PALETTE.purple500,
    key: "purple500",
  },
  {
    label: "Coding / Testing",
    agents: "Vidya · Parikshak",
    hex: PALETTE.green500,
    key: "green500",
  },
  {
    label: "Tooling / Execution",
    agents: "Karmakarta · Kriyakārī",
    hex: PALETTE.amber500,
    key: "amber500",
  },
  {
    label: "Security Audit",
    agents: "Rakshak",
    hex: PALETTE.red500,
    key: "red500",
  },
  {
    label: "Critique / Synthesis",
    agents: "Vivechak · Samanyakā",
    hex: PALETTE.cyan500,
    key: "cyan500",
  },
  {
    label: "Memory (fallback emphasis)",
    agents: "Paalak alt",
    hex: PALETTE.purple700,
    key: "purple700",
  },
] as const;

function DashboardInner(): JSX.Element {
  const demo = useDemoMode();

  const obsQuery = useQuery({
    queryKey: ["observability", "summary", 3600] as const,
    queryFn: async () => await fetchObservability(3600),
    placeholderData: demo.isDemoMode ? buildMockObservability(demo.seed) : buildMockObservability(1),
    retry: 1,
    enabled: !demo.isDemoMode,
  });

  const tracesQuery = useQuery({
    queryKey: ["traces", "list"] as const,
    queryFn: async () => await listTraces(),
    placeholderData: demo.isDemoMode ? buildMockTraces(demo.seed) : buildMockTraces(2),
    retry: 1,
    enabled: !demo.isDemoMode,
  });

  const summary = obsQuery.data ?? (demo.isDemoMode ? buildMockObservability(demo.seed) : buildMockObservability(1));
  const traces = (tracesQuery.data ?? (demo.isDemoMode ? buildMockTraces(demo.seed) : buildMockTraces(2))).slice(0, 4);

  const hasQueryError = !demo.isDemoMode && (obsQuery.isError || tracesQuery.isError);
  const isRefetching = !demo.isDemoMode && (obsQuery.isFetching || tracesQuery.isFetching);

  return (
    <DashboardShell>
      <header className="flex flex-col gap-1">
        <p className="text-xs uppercase tracking-[0.18em] text-brand-600 dark:text-brand-300 font-semibold">
          {NOESIS_BRAND.milestone} · Dashboard
          {demo.isDemoMode && (
            <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-gradient-to-r from-[#6E56CF]/80 via-[#22c55e]/70 to-[#06b6d4]/60 px-2 py-0.5 text-[10px] font-bold text-white">
              DEMO MODE · seed=42
            </span>
          )}
          {isRefetching && (
            <span className="ml-2 inline-flex items-center gap-1 text-brand-500 dark:text-brand-400">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500 dark:bg-brand-400" />
              syncing
            </span>
          )}
        </p>
        <h1 className="text-2xl font-bold tracking-tight text-ink-950 dark:text-ink-50">
          Welcome back — here&apos;s the state of your autonomous workspace.
        </h1>
        {hasQueryError && (
          <p className="mt-1 text-sm text-amber-700 dark:text-amber-300">
            Backend unreachable — falling back to local mock data. Start the kernel on :8000 for live observability.
          </p>
        )}
        {demo.isDemoMode && (
          <p className="mt-1 text-sm text-brand-purple dark:text-brand-purple">
            Viva demo mode active: 12-node Sanskrit codename workflow pre-loaded. Navigate to Agents tab for full workbench view.
          </p>
        )}
      </header>

      <QuickActionsStrip />

      {demo.isDemoMode && demo.workflowNodes.length > 0 && (
        <DemoPipelineSankey nodes={demo.workflowNodes} />
      )}

      <KpiGrid summary={summary} />

      <section className="grid gap-6 xl:grid-cols-[1.3fr_1fr]">
        <MiniTimeline traces={traces} />
        <TopToolsTable summary={summary} />
      </section>

      <MetricsDashboard summary={summary} />

      <section
        className="card p-5 animate-fade-in"
        aria-label="Agent palette legend"
        data-testid="palette-legend-strip"
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-brand-600 dark:text-brand-300 font-semibold">
              Palette · 6-color brand system
            </p>
            <h2 className="text-sm font-semibold text-ink-950 dark:text-ink-50 mt-0.5">
              Sanskrit agent codenames → brand palette mapping
            </h2>
          </div>
          <span className="chip !border-ink-300 dark:!border-ink-700 !bg-ink-50 dark:!bg-ink-900/60 !text-ink-600 dark:!text-ink-300">
            12 agents · 6 colors
          </span>
        </div>

        <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {AGENT_PALETTE_LEGEND.map((entry) => (
            <div
              key={entry.key}
              data-testid={`palette-swatch-${entry.key}`}
              data-palette-hex={entry.hex}
              className="flex items-start gap-3 rounded-xl border border-ink-200 dark:border-ink-800 p-3 transition hover:border-ink-300 dark:hover:border-ink-700"
            >
              <div
                className="h-10 w-10 rounded-lg shrink-0 ring-2 ring-white/50 dark:ring-ink-900/50 shadow-sm"
                style={{ backgroundColor: entry.hex }}
                data-testid={`palette-swatch-color-${entry.key}`}
              />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-ink-950 dark:text-ink-50 truncate">
                  {entry.label}
                </p>
                <p
                  className="text-xs mt-0.5 font-medium truncate"
                  style={{ color: entry.hex }}
                  data-testid={`palette-swatch-agents-${entry.key}`}
                >
                  {entry.agents}
                </p>
                <p className="text-[10px] mt-1 text-ink-500 dark:text-ink-400 font-mono tabular-nums">
                  {entry.hex.toUpperCase()}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </DashboardShell>
  );
}

export default function DashboardPage(): JSX.Element {
  return (
    <Suspense fallback={<div className="p-10 text-center text-ink-500 dark:text-ink-400">Loading dashboard\u2026</div>}>
      <DashboardInner />
    </Suspense>
  );
}
