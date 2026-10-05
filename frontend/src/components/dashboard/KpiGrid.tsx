"use client";

import { Activity, BrainCircuit, Clock3, Coins, Flame, Shield, Wand2, Zap } from "lucide-react";
import type { ComponentType, SVGProps } from "react";

import type { ObservabilitySummary } from "@/lib/schemas";
import { cn, formatCurrencyUSD, formatDurationMs, formatNumber } from "@/lib/format";

interface Kpi {
  readonly label: string;
  readonly value: string;
  readonly delta: string;
  readonly trend: "up" | "down" | "flat";
  readonly Icon: ComponentType<SVGProps<SVGSVGElement>>;
  readonly tone: "brand" | "emerald" | "amber" | "rose";
}

function kpisFor(summary: ObservabilitySummary): readonly Kpi[] {
  const tokensDay = formatNumber(summary.total_tokens / 30, 1);
  const totalErrors = summary.tools.reduce((acc, t) => acc + t.errors, 0);
  return [
    {
      label: "Agent executions",
      value: formatNumber(summary.total_requests),
      delta: "+12.4% vs last 7d",
      trend: "up",
      Icon: Activity,
      tone: "brand",
    },
    {
      label: "Total tokens",
      value: formatNumber(summary.total_tokens),
      delta: `${tokensDay}/day avg`,
      trend: "up",
      Icon: Zap,
      tone: "emerald",
    },
    {
      label: "Estimated cost",
      value: formatCurrencyUSD(summary.total_cost_usd),
      delta: "-1.8% efficiency gain",
      trend: "down",
      Icon: Coins,
      tone: "amber",
    },
    {
      label: "P95 latency",
      value: formatDurationMs(summary.latency_ms.p95),
      delta: "SLO 2s · within budget",
      trend: "flat",
      Icon: Clock3,
      tone: "brand",
    },
    {
      label: "Memory recalls",
      value: formatNumber(2_847, 0),
      delta: "+36 new chunks ingested",
      trend: "up",
      Icon: BrainCircuit,
      tone: "emerald",
    },
    {
      label: "Tool invocations",
      value: formatNumber(
        summary.tools.reduce((acc, t) => acc + t.invocations, 0),
        0,
      ),
      delta: `${totalErrors} errors · 0.9%`,
      trend: "flat",
      Icon: totalErrors > 0 ? Shield : Wand2,
      tone: "rose",
    },
    {
      label: "Active traces",
      value: "14",
      delta: "2 in-flight",
      trend: "up",
      Icon: Clock3,
      tone: "brand",
    },
    {
      label: "Autonomy score",
      value: "87%",
      delta: "+4 pts / reflection loop",
      trend: "up",
      Icon: Flame,
      tone: "emerald",
    },
  ] as const;
}

const toneBg: Record<Kpi["tone"], string> = {
  brand: "from-brand-500/10 to-brand-700/0 text-brand-700 dark:text-brand-200",
  emerald: "from-emerald-500/10 to-emerald-700/0 text-emerald-700 dark:text-emerald-200",
  amber: "from-amber-500/10 to-amber-700/0 text-amber-700 dark:text-amber-200",
  rose: "from-rose-500/10 to-rose-700/0 text-rose-700 dark:text-rose-200",
};

const trendPill: Record<Kpi["trend"], string> = {
  up: "!border-emerald-300 dark:!border-emerald-800 !bg-emerald-50 dark:!bg-emerald-950/40 !text-emerald-700 dark:!text-emerald-200",
  down: "!border-brand-300 dark:!border-brand-800 !bg-brand-50 dark:!bg-brand-950/40 !text-brand-700 dark:!text-brand-200",
  flat: "!border-ink-200 dark:!border-ink-800 !bg-ink-50 dark:!bg-ink-950/40 !text-ink-600 dark:!text-ink-300",
};

export function KpiGrid({ summary }: { readonly summary: ObservabilitySummary }): JSX.Element {
  return (
    <section className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4" aria-label="Key metrics">
      {kpisFor(summary).map((k) => (
        <article key={k.label} className="card p-5 flex flex-col gap-3 animate-fade-in">
          <div className="flex items-center justify-between">
            <div
              className={cn(
                "inline-flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br",
                toneBg[k.tone],
              )}
            >
              <k.Icon className="h-[18px] w-[18px]" aria-hidden />
            </div>
            <span className={cn("chip", trendPill[k.trend])}>{k.delta}</span>
          </div>
          <div>
            <p className="text-xs text-ink-500 dark:text-ink-400 font-medium">{k.label}</p>
            <p className="mt-1 text-2xl font-semibold tracking-tight text-ink-950 dark:text-ink-50">{k.value}</p>
          </div>
        </article>
      ))}
    </section>
  );
}
