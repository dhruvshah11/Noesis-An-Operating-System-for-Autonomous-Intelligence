"use client";

import { Suspense, useMemo, useState } from "react";
import type { JSX } from "react";
import { useQuery } from "@tanstack/react-query";

import { DashboardShell } from "@/components/layout/DashboardShell";
import { ExecutionTimeline, STATUS_PILL } from "@/components/timeline/ExecutionTimeline";
import { buildMockTraces } from "@/testing/mocks";
import { listTraces } from "@/lib/api/endpoints";
import type { ExecutionTrace, PlanStep } from "@/lib/schemas";
import { cn, formatDurationMs } from "@/lib/format";
import { Badge } from "@/components/ui/Badge";
import { getBadgeColorForCodename, getCodenameForRole } from "@/lib/agents_codenames";
import { useDemoMode } from "@/lib/demo";

async function queryTraces(): Promise<ExecutionTrace[]> {
  const live = await listTraces();
  if (live.length > 0) return live;
  await new Promise((r) => setTimeout(r, 1000));
  return buildMockTraces(11);
}

const stepBarTone: Record<PlanStep["status"], string> = {
  pending: "bg-ink-300/70 dark:bg-ink-700/70",
  running: "bg-gradient-to-r from-brand-500 to-brand-400 animate-pulse",
  success: "bg-gradient-to-r from-emerald-500 to-emerald-400",
  failed: "bg-gradient-to-r from-rose-500 to-rose-400",
  skipped: "bg-ink-200/60 dark:bg-ink-800/60",
};

function WaterfallDiagram({ trace }: { readonly trace: ExecutionTrace }): JSX.Element {
  const steps = trace.plan_steps;

  const layout = useMemo(() => {
    if (steps.length === 0) return { bars: [], width: 100 };
    const starts = steps.map((s) => s.started_at ?? trace.created_at);
    const ends = steps.map((s) =>
      s.ended_at ?? s.started_at ?? trace.created_at + 60,
    );
    const minT = Math.min(...starts);
    const maxT = Math.max(...ends, minT + 1);
    const span = Math.max(1, maxT - minT);
    const bars = steps.map((s, i) => {
      const s0 = s.started_at ?? trace.created_at + i * 30;
      const s1 = s.ended_at ?? (s.status === "pending" || s.status === "running" ? s0 + 40 : s0 + 50);
      const left = ((s0 - minT) / span) * 100;
      const width = Math.max(1.5, ((s1 - s0) / span) * 100);
      return { left, width, step: s, index: i, durMs: (s1 - s0) * 1000 };
    });
    return { bars, width: 100, minT, maxT, span };
  }, [steps, trace.created_at]);

  return (
    <div className="rounded-2xl border border-ink-200 dark:border-ink-800 bg-ink-50/50 dark:bg-ink-950/40 p-5">
      <div className="flex items-end justify-between mb-4">
        <div>
          <p className="text-xs uppercase tracking-wider font-semibold text-ink-500 dark:text-ink-400">
            Execution plan \u2014 waterfall
          </p>
          <p className="text-sm font-semibold text-ink-950 dark:text-ink-50 mt-0.5 truncate max-w-2xl">
            {trace.user_query}
          </p>
        </div>
        <span className={cn("chip", STATUS_PILL[trace.status])}>{trace.status}</span>
      </div>

      <div className="space-y-2">
        {layout.bars.map((bar) => {
          const agentRole = bar.step.assigned_agent;
          const codename = getCodenameForRole(agentRole);
          const badgeColor = codename ? getBadgeColorForCodename(codename) : "text-brand-purple";
          return (
          <div key={bar.step.index} className="grid grid-cols-[12rem_1fr] items-center gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-1 flex-wrap min-w-0">
                <p className="text-xs font-medium text-ink-900 dark:text-ink-100 truncate">
                  S{bar.index} · {agentRole}
                </p>
                {codename && (
                  <Badge variant="default" className={cn("mr-1", badgeColor)}>
                    {codename}
                  </Badge>
                )}
              </div>
              <p className="text-[11px] text-ink-500 dark:text-ink-400 truncate tabular-nums mt-0.5">
                {formatDurationMs(bar.durMs)}
              </p>
            </div>
            <div
              className="relative h-8 rounded-xl bg-ink-100 dark:bg-ink-900/80 overflow-hidden border border-ink-200 dark:border-ink-800"
              style={{ width: `${layout.width}%` }}
            >
              <div
                className={cn(
                  "absolute top-1/2 -translate-y-1/2 h-5 rounded-lg shadow-sm",
                  stepBarTone[bar.step.status],
                )}
                style={{
                  left: `${bar.left}%`,
                  width: `${bar.width}%`,
                }}
                title={`${bar.step.description} \u2014 ${bar.step.status}`}
              />
            </div>
          </div>
          );
        })}
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-ink-200/60 dark:border-ink-800/60 pt-3">
        <div className="flex flex-wrap items-center gap-2 text-[11px] text-ink-500 dark:text-ink-400">
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-4 rounded-sm bg-gradient-to-r from-emerald-500 to-emerald-400" /> success
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-4 rounded-sm bg-gradient-to-r from-brand-500 to-brand-400" /> running
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-4 rounded-sm bg-gradient-to-r from-rose-500 to-rose-400" /> failed
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-4 rounded-sm bg-ink-300/70 dark:bg-ink-700/70" /> pending
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-4 rounded-sm bg-ink-200/60 dark:bg-ink-800/60" /> skipped
          </span>
        </div>
        <div className="flex flex-wrap gap-2">
          {steps.map((s) => (
            <span
              key={s.index}
              className={cn("chip !py-0.5 !px-2 text-[10px]", STATUS_PILL[s.status])}
            >
              S{s.index} {s.status}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function TimelineInner(): JSX.Element {
  const demo = useDemoMode();
  const { data: traces = demo.isDemoMode ? buildMockTraces(demo.seed) : buildMockTraces(11), isFetching, isError } = useQuery({
    queryKey: ["traces", "drilldown"] as const,
    queryFn: queryTraces,
    placeholderData: demo.isDemoMode ? buildMockTraces(demo.seed) : buildMockTraces(11),
    retry: 1,
    enabled: !demo.isDemoMode,
  });

  const [traceId, setTraceId] = useState<string | undefined>(traces[0]?.trace_id);
  const active = traces.find((t) => t.trace_id === traceId) ?? traces[0];

  return (
    <DashboardShell>
      <header>
        <p className="text-xs uppercase tracking-[0.18em] text-brand-600 dark:text-brand-300 font-semibold">
          Execution
          {isFetching && (
            <span className="ml-2 inline-flex items-center gap-1 text-brand-500 dark:text-brand-400">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500 dark:bg-brand-400" />
              syncing
            </span>
          )}
        </p>
        <h1 className="mt-0.5 text-2xl font-bold tracking-tight text-ink-950 dark:text-ink-50">
          Execution Timeline
        </h1>
        <p className="text-sm text-ink-500 dark:text-ink-400 mt-1">
          Inspect every plan step, agent handoffs, and tool calls for each autonomous run.
        </p>
        {isError && (
          <p className="mt-1 text-sm text-amber-700 dark:text-amber-300">
            Backend unreachable \u2014 falling back to local mock data.
          </p>
        )}
      </header>

      <div className="flex items-center gap-2 overflow-x-auto pb-2 mb-2">
        {traces.map((t, idx) => (
          <button
            key={t.trace_id}
            type="button"
            onClick={() => setTraceId(t.trace_id)}
            className={cn(
              "shrink-0 rounded-xl px-3 py-2 text-left text-xs border transition",
              traceId === t.trace_id
                ? "border-brand-400 bg-brand-50 dark:bg-brand-950/40 text-brand-700 dark:text-brand-200 shadow-sm"
                : "border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-950/50 hover:bg-ink-50 dark:hover:bg-ink-900/50 text-ink-700 dark:text-ink-300",
            )}
          >
            <p className="font-semibold line-clamp-1 max-w-[28ch]">#{1000 + idx} · {t.user_query.slice(0, 46)}{t.user_query.length > 46 ? "\u2026" : ""}</p>
            <div className="flex items-center gap-2 mt-1">
              <span className={cn("chip !py-0 !px-1.5 !text-[10px]", STATUS_PILL[t.status])}>{t.status}</span>
              <span className="text-[10px] text-ink-500 dark:text-ink-400">{t.plan_steps.length} steps</span>
            </div>
          </button>
        ))}
      </div>

      {active ? (
        <>
          <WaterfallDiagram trace={active} />
          <ExecutionTimeline traces={traces} title="Step-by-step execution" />
        </>
      ) : (
        <div className="card p-10 text-center text-ink-500 dark:text-ink-400">
          <p className="font-medium">No execution traces found.</p>
          <p className="text-sm mt-1">Run an agent on the Agents page to see its trace here.</p>
        </div>
      )}
    </DashboardShell>
  );
}

function TimelineSuspenseFallback(): JSX.Element {
  const _traces = buildMockTraces(11);
  void _traces;
  return (
    <DashboardShell>
      <header>
        <p className="text-xs uppercase tracking-[0.18em] text-brand-600 dark:text-brand-300 font-semibold">
          Execution
          <span className="ml-2 inline-flex items-center gap-1 text-brand-500 dark:text-brand-400">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500 dark:bg-brand-400" />
            loading
          </span>
        </p>
        <h1 className="mt-0.5 text-2xl font-bold tracking-tight text-ink-950 dark:text-ink-50">
          Execution Timeline
        </h1>
        <p className="text-sm text-ink-500 dark:text-ink-400 mt-1">
          Loading execution traces\u2026
        </p>
      </header>
      <div className="card p-5 h-56 animate-pulse opacity-60 rounded-2xl mb-4" />
      <div className="card p-5 h-64 animate-pulse opacity-60 rounded-2xl" />
    </DashboardShell>
  );
}

export default function TimelinePage(): JSX.Element {
  return (
    <Suspense fallback={<TimelineSuspenseFallback />}>
      <TimelineInner />
    </Suspense>
  );
}
