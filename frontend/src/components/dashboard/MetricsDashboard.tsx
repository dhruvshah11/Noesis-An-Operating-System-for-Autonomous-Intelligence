"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AlertTriangle, CheckCircle2, Clock3, Coins, Flame, Gauge, ListChecks, Sparkles, Wand2 } from "lucide-react";
import type { ComponentType, SVGProps } from "react";
import type React from "react";

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
  return [
    {
      label: "Agent executions",
      value: formatNumber(summary.total_requests),
      delta: "+12.4% vs last 7d",
      trend: "up",
      Icon: ListChecks,
      tone: "brand",
    },
    {
      label: "Total tokens",
      value: formatNumber(summary.total_tokens),
      delta: `${tokensDay}/day avg`,
      trend: "up",
      Icon: Sparkles,
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
      delta: "SLO 2s \u00b7 within budget",
      trend: "flat",
      Icon: Gauge,
      tone: "brand",
    },
    {
      label: "Memory recalls",
      value: formatNumber(2_847, 0),
      delta: "+36 new chunks ingested",
      trend: "up",
      Icon: Flame,
      tone: "emerald",
    },
    {
      label: "Tool invocations",
      value: formatNumber(
        summary.tools.reduce((acc, t) => acc + t.invocations, 0),
        0,
      ),
      delta: `${summary.tools.reduce((acc, t) => acc + t.errors, 0)} errors \u00b7 0.9%`,
      trend: "flat",
      Icon: Wand2,
      tone: "rose",
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

const latencySeries = Array.from({ length: 12 }, (_, i) => ({
  name: `${i * 5}m`,
  avg: 420 + Math.round(Math.sin(i) * 180 + (i % 3) * 60),
  p50: 360 + Math.round(Math.cos(i) * 120 + (i % 2) * 40),
  p95: 1_100 + Math.round(Math.sin(i * 0.8) * 500 + i * 40),
  p99: 2_200 + Math.round(Math.cos(i * 0.6) * 800 + i * 90),
}));

const hourlyRequests = Array.from({ length: 24 }, (_, i) => ({
  name: `${String(i).padStart(2, "0")}:00`,
  requests: 18 + Math.round(40 * Math.sin((i - 6) / 24 * Math.PI * 2) + 20 + (i % 4) * 8),
  errors: Math.max(0, Math.round(1 + Math.sin(i) * 1.2 + (i % 7 === 0 ? 3 : 0))),
}));

function StatusDot({ tone }: { readonly tone: "emerald" | "amber" | "rose" | "ink" }): React.JSX.Element {
  const colors: Record<typeof tone, string> = {
    emerald: "bg-emerald-500",
    amber: "bg-amber-500",
    rose: "bg-rose-500",
    ink: "bg-ink-400",
  };
  return <span className={cn("inline-block h-2 w-2 rounded-full", colors[tone])} />;
}

function toolRowTone(errors: number, invocations: number): "emerald" | "amber" | "rose" | "ink" {
  if (invocations === 0) return "ink";
  const rate = errors / invocations;
  if (rate === 0) return "emerald";
  if (rate < 0.05) return "amber";
  return "rose";
}

const BAR_COLORS = ["#3462ff", "#61739e", "#10b981", "#f59e0b", "#f43f5e"];

export function MetricsDashboard({ summary }: { readonly summary: ObservabilitySummary }): React.JSX.Element {
  const toolRows = summary.tools.map((t, i) => ({ ...t, color: BAR_COLORS[i % BAR_COLORS.length] }));
  const totalInvocations = toolRows.reduce((acc, t) => acc + t.invocations, 0);

  return (
    <div className="flex flex-col gap-6">
      <section className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3" aria-label="Key metrics">
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

      <section className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <article className="card p-5 animate-fade-in">
          <header className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-ink-950 dark:text-ink-50">Latency distribution</h3>
              <p className="text-xs text-ink-500 dark:text-ink-400 mt-0.5">avg / p50 / p95 / p99 across 60m window</p>
            </div>
            <span className="chip">
              <Clock3 className="h-3 w-3" /> {formatDurationMs(summary.latency_ms.avg)} avg
            </span>
          </header>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={latencySeries} margin={{ top: 4, right: 16, left: -8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-ink-200 dark:stroke-ink-800" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} className="text-ink-500 dark:text-ink-400" />
                <YAxis tick={{ fontSize: 11 }} className="text-ink-500 dark:text-ink-400" />
                <Tooltip
                  contentStyle={{ borderRadius: 12, border: "1px solid rgb(var(--border))", background: "rgb(var(--surface))" }}
                  formatter={(value: number) => formatDurationMs(value)}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line type="monotone" dataKey="avg" stroke="#3462ff" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="p50" stroke="#10b981" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="p95" stroke="#f59e0b" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="p99" stroke="#f43f5e" strokeWidth={2} dot={false} strokeDasharray="4 4" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="card p-5 animate-fade-in">
          <header className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-ink-950 dark:text-ink-50">Requests per hour</h3>
              <p className="text-xs text-ink-500 dark:text-ink-400 mt-0.5">Executions vs error rate, last 24h</p>
            </div>
            <span className="chip">
              <CheckCircle2 className="h-3 w-3 text-emerald-600" /> {formatNumber(summary.total_requests)} total
            </span>
          </header>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={hourlyRequests} margin={{ top: 4, right: 16, left: -8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-ink-200 dark:stroke-ink-800" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={3} className="text-ink-500 dark:text-ink-400" />
                <YAxis tick={{ fontSize: 11 }} className="text-ink-500 dark:text-ink-400" />
                <Tooltip
                  contentStyle={{ borderRadius: 12, border: "1px solid rgb(var(--border))", background: "rgb(var(--surface))" }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="requests" stackId="a" fill="#3462ff" radius={[4, 4, 0, 0]} />
                <Bar dataKey="errors" stackId="a" fill="#f43f5e" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </article>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.2fr_1fr]">
        <article className="card p-5 animate-fade-in">
          <header className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-ink-950 dark:text-ink-50">Tool invocation mix</h3>
              <p className="text-xs text-ink-500 dark:text-ink-400 mt-0.5">Share of total invocations per tool</p>
            </div>
            <span className="chip">
              <Wand2 className="h-3 w-3" /> {formatNumber(totalInvocations, 0)} calls
            </span>
          </header>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={toolRows} layout="vertical" margin={{ top: 4, right: 16, left: -8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-ink-200 dark:stroke-ink-800" />
                <XAxis type="number" tick={{ fontSize: 11 }} className="text-ink-500 dark:text-ink-400" />
                <YAxis dataKey="tool_name" type="category" tick={{ fontSize: 11 }} width={80} className="text-ink-500 dark:text-ink-400" />
                <Tooltip
                  contentStyle={{ borderRadius: 12, border: "1px solid rgb(var(--border))", background: "rgb(var(--surface))" }}
                  formatter={(value: number) => formatNumber(value, 0)}
                />
                <Bar dataKey="invocations" radius={[0, 6, 6, 0]}>
                  {toolRows.map((t, i) => (
                    <Cell key={i} fill={t.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="card p-5 animate-fade-in">
          <header className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-ink-950 dark:text-ink-50">Tool health</h3>
              <p className="text-xs text-ink-500 dark:text-ink-400 mt-0.5">Errors, latency and error rate</p>
            </div>
            <span className="chip">
              <AlertTriangle className="h-3 w-3 text-amber-600" />
              {summary.tools.reduce((acc, t) => acc + t.errors, 0)} errors
            </span>
          </header>
          <div className="overflow-hidden rounded-xl border border-ink-200 dark:border-ink-800">
            <table className="w-full text-sm">
              <thead className="bg-ink-50 dark:bg-ink-900/50 text-ink-600 dark:text-ink-300">
                <tr>
                  <th className="text-left font-medium px-3 py-2 text-xs">Tool</th>
                  <th className="text-right font-medium px-3 py-2 text-xs">Calls</th>
                  <th className="text-right font-medium px-3 py-2 text-xs">P95</th>
                  <th className="text-left font-medium px-3 py-2 text-xs">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100 dark:divide-ink-800">
                {summary.tools.map((t) => {
                  const tone = toolRowTone(t.errors, t.invocations);
                  return (
                    <tr key={t.tool_name} className="hover:bg-ink-50/60 dark:hover:bg-ink-900/30 transition">
                      <td className="px-3 py-2.5 font-medium text-ink-800 dark:text-ink-100">{t.tool_name}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-ink-700 dark:text-ink-200">{formatNumber(t.invocations, 0)}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-ink-700 dark:text-ink-200">{formatDurationMs(t.p95_ms)}</td>
                      <td className="px-3 py-2.5">
                        <span className="inline-flex items-center gap-1.5 text-xs">
                          <StatusDot tone={tone} />
                          <span className="text-ink-600 dark:text-ink-300">
                            {t.errors === 0 ? "Clean" : `${t.errors} error${t.errors === 1 ? "" : "s"}`}
                          </span>
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </article>
      </section>
    </div>
  );
}
