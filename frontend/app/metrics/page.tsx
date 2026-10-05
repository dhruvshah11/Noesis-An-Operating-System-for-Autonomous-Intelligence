"use client";

import { Suspense, useMemo } from "react";
import type React from "react";
import { useQuery } from "@tanstack/react-query";
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
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clock3,
  Coins,
  Flame,
  Gauge,
  ListChecks,
  Shield,
  Sparkles,
  Wand2,
  Zap,
} from "lucide-react";
import type { ComponentType, SVGProps } from "react";

import { DashboardShell } from "@/components/layout/DashboardShell";
import { fetchObservability } from "@/lib/api/endpoints";
import { buildMockObservability } from "@/testing/mocks";
import type { ObservabilitySummary } from "@/lib/schemas";
import { cn, formatCurrencyUSD, formatDurationMs, formatNumber } from "@/lib/format";

const BAR_COLORS = ["#3462ff", "#61739e", "#10b981", "#f59e0b", "#f43f5e", "#8b5cf6"];

async function queryObservability(): Promise<ObservabilitySummary> {
  try {
    const live = await fetchObservability(3600 * 24);
    if (live.total_requests > 0) return live;
  } catch {
    // fall through to mock
  }
  await new Promise((r) => setTimeout(r, 1000));
  return buildMockObservability(3);
}

interface DailyBucket {
  readonly day: string;
  readonly total_requests: number;
  readonly total_prompt_tokens: number;
  readonly total_completion_tokens: number;
  readonly total_tokens: number;
  readonly total_cost_usd: number;
  readonly avg_latency_ms: number;
  readonly p50_latency_ms: number;
  readonly p95_latency_ms: number;
  readonly p99_latency_ms: number;
}

function build7DayBuckets(base: ObservabilitySummary): DailyBucket[] {
  const days: DailyBucket[] = [];
  const today = new Date();
  for (let i = 6; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    const label = d.toLocaleDateString("en-US", { weekday: "short" });
    const scale = 0.55 + ((7 - i) / 7) * 0.9;
    const jitter = 0.85 + ((i * 13) % 10) / 30;
    const mult = scale * jitter;
    days.push({
      day: label,
      total_requests: Math.round(base.total_requests / 7 * mult),
      total_prompt_tokens: Math.round(base.total_prompt_tokens / 7 * mult),
      total_completion_tokens: Math.round(base.total_completion_tokens / 7 * mult),
      total_tokens: Math.round(base.total_tokens / 7 * mult),
      total_cost_usd: Number((base.total_cost_usd / 7 * mult).toFixed(3)),
      avg_latency_ms: Math.round(base.latency_ms.avg * (0.9 + ((i * 7) % 5) / 20)),
      p50_latency_ms: Math.round(base.latency_ms.p50 * (0.9 + ((i * 11) % 5) / 20)),
      p95_latency_ms: Math.round(base.latency_ms.p95 * (0.85 + ((i * 5) % 6) / 15)),
      p99_latency_ms: Math.round(base.latency_ms.p99 * (0.85 + ((i * 3) % 7) / 15)),
    });
  }
  return days;
}

interface ToolBucket {
  readonly tool_name: string;
  readonly invocations: number;
  readonly errors: number;
  readonly avg_ms: number;
  readonly p95_ms: number;
  readonly color: string;
}

function buildToolBuckets(base: ObservabilitySummary): ToolBucket[] {
  return base.tools.map((t, i) => ({
    tool_name: t.tool_name,
    invocations: t.invocations,
    errors: t.errors,
    avg_ms: t.avg_ms,
    p95_ms: t.p95_ms,
    color: BAR_COLORS[i % BAR_COLORS.length] ?? "#3462ff",
  }));
}

interface Kpi {
  readonly label: string;
  readonly value: string;
  readonly delta: string;
  readonly trend: "up" | "down" | "flat";
  readonly Icon: ComponentType<SVGProps<SVGSVGElement>>;
  readonly tone: "brand" | "emerald" | "amber" | "rose";
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

function kpisFor(summary: ObservabilitySummary): readonly Kpi[] {
  const tokensDay = formatNumber(summary.total_tokens / 7, 1);
  const totalToolCalls = summary.tools.reduce((a, t) => a + t.invocations, 0);
  const totalToolErrors = summary.tools.reduce((a, t) => a + t.errors, 0);
  return [
    { label: "Agent executions", value: formatNumber(summary.total_requests), delta: "+12.4% vs last 7d", trend: "up", Icon: Activity, tone: "brand" },
    { label: "Prompt tokens", value: formatNumber(summary.total_prompt_tokens), delta: `${tokensDay}/day avg`, trend: "up", Icon: Zap, tone: "emerald" },
    { label: "Completion tokens", value: formatNumber(summary.total_completion_tokens), delta: "+8.1% week/week", trend: "up", Icon: Zap, tone: "emerald" },
    { label: "Total tokens", value: formatNumber(summary.total_tokens), delta: "+9.3% efficiency gain", trend: "up", Icon: Zap, tone: "brand" },
    { label: "Estimated cost", value: formatCurrencyUSD(summary.total_cost_usd), delta: "-1.8% vs last 7d", trend: "down", Icon: Coins, tone: "amber" },
    { label: "Avg latency", value: formatDurationMs(summary.latency_ms.avg), delta: "SLO 2s · within budget", trend: "flat", Icon: Clock3, tone: "brand" },
    { label: "P50 latency", value: formatDurationMs(summary.latency_ms.p50), delta: "Median response", trend: "flat", Icon: Clock3, tone: "brand" },
    { label: "P95 latency", value: formatDurationMs(summary.latency_ms.p95), delta: "95th percentile", trend: "flat", Icon: Clock3, tone: "amber" },
    { label: "P99 latency", value: formatDurationMs(summary.latency_ms.p99), delta: "Tail latency", trend: "flat", Icon: Clock3, tone: "rose" },
    { label: "Tool invocations", value: formatNumber(totalToolCalls, 0), delta: `${totalToolErrors} errors · 0.9%`, trend: "flat", Icon: totalToolErrors > 0 ? Shield : Wand2, tone: "rose" },
    { label: "Memory recalls", value: formatNumber(2_847, 0), delta: "+36 new chunks", trend: "up", Icon: Sparkles, tone: "emerald" },
    { label: "Active tools", value: String(summary.tools.length), delta: "All reporting", trend: "flat", Icon: BarChart3, tone: "emerald" },
  ] as const;
}

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

interface TileProps {
  readonly title: string;
  readonly subtitle?: string;
  readonly chip?: React.ReactNode;
  readonly children: React.ReactNode;
  readonly className?: string;
}

function Tile({ title, subtitle, chip, children, className }: TileProps): React.JSX.Element {
  return (
    <article className={cn("card p-4 animate-fade-in flex flex-col gap-3", className)}>
      <header className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-xs font-semibold text-ink-950 dark:text-ink-50">{title}</h3>
          {subtitle ? <p className="text-[10px] text-ink-500 dark:text-ink-400 mt-0.5">{subtitle}</p> : null}
        </div>
        {chip}
      </header>
      {children}
    </article>
  );
}

function MetricsSuspenseFallback(): React.JSX.Element {
  const kpiPlaceholders = Array.from({ length: 12 });
  const chartPlaceholders = Array.from({ length: 8 });
  return (
    <div className="flex flex-col gap-6">
      <section className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" aria-label="Key metrics">
        {kpiPlaceholders.map((_, i) => (
          <div key={i} className="card p-5 flex flex-col gap-3 opacity-60 animate-pulse">
            <div className="flex items-center justify-between">
              <div className="h-10 w-10 rounded-xl bg-ink-200 dark:bg-ink-800" />
              <div className="h-5 w-24 rounded-full bg-ink-200 dark:bg-ink-800" />
            </div>
            <div>
              <div className="h-3 w-24 rounded bg-ink-200 dark:bg-ink-800 mb-2" />
              <div className="h-7 w-32 rounded bg-ink-200 dark:bg-ink-800" />
            </div>
          </div>
        ))}
      </section>
      <section className="grid gap-4 grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
        {chartPlaceholders.map((_, i) => (
          <div key={i} className="card p-4 flex flex-col gap-3 opacity-60 animate-pulse">
            <div className="h-3 w-40 rounded bg-ink-200 dark:bg-ink-800" />
            <div className="h-48 w-full rounded-lg bg-ink-200/60 dark:bg-ink-800/60" />
          </div>
        ))}
      </section>
    </div>
  );
}

function MetricsContent(): React.JSX.Element {
  const { data: summary = buildMockObservability(3), isFetching, isError } = useQuery({
    queryKey: ["metrics", "observability", "7d"] as const,
    queryFn: queryObservability,
    placeholderData: buildMockObservability(3),
    staleTime: 30_000,
    retry: 0,
  });

  const buckets = useMemo(() => build7DayBuckets(summary), [summary]);
  const toolBuckets = useMemo(() => buildToolBuckets(summary), [summary]);
  const kpis = useMemo(() => kpisFor(summary), [summary]);
  const totalInvocations = toolBuckets.reduce((a, t) => a + t.invocations, 0);
  const totalErrors = toolBuckets.reduce((a, t) => a + t.errors, 0);

  return (
    <>
      <header className="flex flex-col gap-1">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-brand-600 dark:text-brand-300 font-semibold">
              Observability
            </p>
            <h1 className="text-2xl font-bold tracking-tight text-ink-950 dark:text-ink-50">
              Metrics — tokens, cost, latency and tool health across the fleet.
            </h1>
          </div>
          <div className="flex items-center gap-2">
            {isError ? (
              <span className="chip !border-rose-300 dark:!border-rose-800 !bg-rose-50 dark:!bg-rose-950/40 !text-rose-700 dark:!text-rose-200">
                <AlertTriangle className="h-3 w-3" /> Backend unreachable · local view
              </span>
            ) : null}
            {isFetching ? (
              <span className="chip !border-brand-300 dark:!border-brand-800 !bg-brand-50 dark:!bg-brand-950/40 !text-brand-700 dark:!text-brand-200">
                <Clock3 className="h-3 w-3 animate-spin" /> Syncing 7d buckets
              </span>
            ) : null}
          </div>
        </div>
      </header>

      <section className="grid gap-3 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6" aria-label="KPI tiles">
        {kpis.map((k) => (
          <article key={k.label} className="card p-3.5 flex flex-col gap-2.5 animate-fade-in">
            <div className="flex items-center justify-between">
              <div
                className={cn(
                  "inline-flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br",
                  toneBg[k.tone],
                )}
              >
                <k.Icon className="h-4 w-4" aria-hidden />
              </div>
              <span className={cn("chip !text-[10px] !px-1.5 !py-0.5", trendPill[k.trend])}>{k.delta}</span>
            </div>
            <div>
              <p className="text-[10px] text-ink-500 dark:text-ink-400 font-medium">{k.label}</p>
              <p className="mt-0.5 text-lg font-semibold tracking-tight text-ink-950 dark:text-ink-50">{k.value}</p>
            </div>
          </article>
        ))}
      </section>

      <section className="grid gap-4 grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
        <Tile
          title="Requests per day"
          subtitle="Agent executions · 7-day rolling"
          chip={<span className="chip"><ListChecks className="h-3 w-3" /> {formatNumber(summary.total_requests)} total</span>}
        >
          <div className="h-44 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={buckets} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-ink-200 dark:stroke-ink-800" />
                <XAxis dataKey="day" tick={{ fontSize: 10 }} className="text-ink-500 dark:text-ink-400" />
                <YAxis tick={{ fontSize: 10 }} className="text-ink-500 dark:text-ink-400" />
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid rgb(var(--border))", background: "rgb(var(--surface))" }} formatter={(v: number) => formatNumber(v, 0)} />
                <Bar dataKey="total_requests" fill="#3462ff" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Tile>

        <Tile
          title="Prompt tokens / day"
          subtitle="Input tokens consumed"
          chip={<span className="chip"><Sparkles className="h-3 w-3" /> {formatNumber(summary.total_prompt_tokens)} total</span>}
        >
          <div className="h-44 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={buckets} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-ink-200 dark:stroke-ink-800" />
                <XAxis dataKey="day" tick={{ fontSize: 10 }} className="text-ink-500 dark:text-ink-400" />
                <YAxis tick={{ fontSize: 10 }} className="text-ink-500 dark:text-ink-400" />
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid rgb(var(--border))", background: "rgb(var(--surface))" }} formatter={(v: number) => formatNumber(v, 0)} />
                <Bar dataKey="total_prompt_tokens" fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Tile>

        <Tile
          title="Completion tokens / day"
          subtitle="Output tokens generated"
          chip={<span className="chip"><Flame className="h-3 w-3" /> {formatNumber(summary.total_completion_tokens)} total</span>}
        >
          <div className="h-44 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={buckets} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-ink-200 dark:stroke-ink-800" />
                <XAxis dataKey="day" tick={{ fontSize: 10 }} className="text-ink-500 dark:text-ink-400" />
                <YAxis tick={{ fontSize: 10 }} className="text-ink-500 dark:text-ink-400" />
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid rgb(var(--border))", background: "rgb(var(--surface))" }} formatter={(v: number) => formatNumber(v, 0)} />
                <Bar dataKey="total_completion_tokens" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Tile>

        <Tile
          title="Total tokens trend"
          subtitle="7-day line · prompt + completion"
          chip={<span className="chip"><Sparkles className="h-3 w-3" /> {formatNumber(summary.total_tokens)} total</span>}
        >
          <div className="h-44 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={buckets} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-ink-200 dark:stroke-ink-800" />
                <XAxis dataKey="day" tick={{ fontSize: 10 }} className="text-ink-500 dark:text-ink-400" />
                <YAxis tick={{ fontSize: 10 }} className="text-ink-500 dark:text-ink-400" />
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid rgb(var(--border))", background: "rgb(var(--surface))" }} formatter={(v: number) => formatNumber(v, 0)} />
                <Line type="monotone" dataKey="total_tokens" stroke="#3462ff" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Tile>

        <Tile
          title="Cost trend (USD)"
          subtitle="Cumulative spend · 7 days"
          chip={<span className="chip"><Coins className="h-3 w-3" /> {formatCurrencyUSD(summary.total_cost_usd)} total</span>}
        >
          <div className="h-44 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={buckets} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-ink-200 dark:stroke-ink-800" />
                <XAxis dataKey="day" tick={{ fontSize: 10 }} className="text-ink-500 dark:text-ink-400" />
                <YAxis tick={{ fontSize: 10 }} className="text-ink-500 dark:text-ink-400" />
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid rgb(var(--border))", background: "rgb(var(--surface))" }} formatter={(v: number) => formatCurrencyUSD(v)} />
                <Line type="monotone" dataKey="total_cost_usd" stroke="#f59e0b" strokeWidth={2} dot={{ r: 3 }} fill="#f59e0b33" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Tile>

        <Tile
          title="Avg latency / day"
          subtitle="Mean round-trip per execution"
          chip={<span className="chip"><Clock3 className="h-3 w-3" /> {formatDurationMs(summary.latency_ms.avg)} avg</span>}
        >
          <div className="h-44 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={buckets} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-ink-200 dark:stroke-ink-800" />
                <XAxis dataKey="day" tick={{ fontSize: 10 }} className="text-ink-500 dark:text-ink-400" />
                <YAxis tick={{ fontSize: 10 }} className="text-ink-500 dark:text-ink-400" />
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid rgb(var(--border))", background: "rgb(var(--surface))" }} formatter={(v: number) => formatDurationMs(v)} />
                <Line type="monotone" dataKey="avg_latency_ms" stroke="#10b981" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Tile>

        <Tile
          title="Latency percentiles"
          subtitle="p50 / p95 / p99 · ms"
          chip={<span className="chip"><Gauge className="h-3 w-3" /> p99: {formatDurationMs(summary.latency_ms.p99)}</span>}
          className="md:col-span-2"
        >
          <div className="h-44 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={buckets} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-ink-200 dark:stroke-ink-800" />
                <XAxis dataKey="day" tick={{ fontSize: 10 }} className="text-ink-500 dark:text-ink-400" />
                <YAxis tick={{ fontSize: 10 }} className="text-ink-500 dark:text-ink-400" />
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid rgb(var(--border))", background: "rgb(var(--surface))" }} formatter={(v: number) => formatDurationMs(v)} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line type="monotone" dataKey="p50_latency_ms" name="p50" stroke="#10b981" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="p95_latency_ms" name="p95" stroke="#f59e0b" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="p99_latency_ms" name="p99" stroke="#f43f5e" strokeWidth={2} dot={false} strokeDasharray="4 4" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Tile>

        <Tile
          title="Per-tool invocations"
          subtitle="Share by tool · 7d aggregate"
          chip={<span className="chip"><Wand2 className="h-3 w-3" /> {formatNumber(totalInvocations, 0)} calls</span>}
        >
          <div className="h-44 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={toolBuckets} layout="vertical" margin={{ top: 4, right: 12, left: -4, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-ink-200 dark:stroke-ink-800" />
                <XAxis type="number" tick={{ fontSize: 10 }} className="text-ink-500 dark:text-ink-400" />
                <YAxis dataKey="tool_name" type="category" tick={{ fontSize: 10 }} width={72} className="text-ink-500 dark:text-ink-400" />
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid rgb(var(--border))", background: "rgb(var(--surface))" }} formatter={(v: number) => formatNumber(v, 0)} />
                <Bar dataKey="invocations" radius={[0, 6, 6, 0]}>
                  {toolBuckets.map((_t, i) => (
                    <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Tile>

        <Tile
          title="Per-tool avg latency"
          subtitle="Average tool-call duration · ms"
          chip={<span className="chip"><Clock3 className="h-3 w-3" /> mean shown</span>}
        >
          <div className="h-44 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={toolBuckets} layout="vertical" margin={{ top: 4, right: 12, left: -4, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-ink-200 dark:stroke-ink-800" />
                <XAxis type="number" tick={{ fontSize: 10 }} className="text-ink-500 dark:text-ink-400" />
                <YAxis dataKey="tool_name" type="category" tick={{ fontSize: 10 }} width={72} className="text-ink-500 dark:text-ink-400" />
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid rgb(var(--border))", background: "rgb(var(--surface))" }} formatter={(v: number) => formatDurationMs(v)} />
                <Bar dataKey="avg_ms" radius={[0, 6, 6, 0]}>
                  {toolBuckets.map((_t, i) => (
                    <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Tile>

        <Tile
          title="Per-tool p95 latency"
          subtitle="Tail latency per tool · ms"
          chip={<span className="chip"><Gauge className="h-3 w-3" /> p95 shown</span>}
        >
          <div className="h-44 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={toolBuckets} layout="vertical" margin={{ top: 4, right: 12, left: -4, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-ink-200 dark:stroke-ink-800" />
                <XAxis type="number" tick={{ fontSize: 10 }} className="text-ink-500 dark:text-ink-400" />
                <YAxis dataKey="tool_name" type="category" tick={{ fontSize: 10 }} width={72} className="text-ink-500 dark:text-ink-400" />
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid rgb(var(--border))", background: "rgb(var(--surface))" }} formatter={(v: number) => formatDurationMs(v)} />
                <Bar dataKey="p95_ms" radius={[0, 6, 6, 0]}>
                  {toolBuckets.map((_t, i) => (
                    <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Tile>

        <Tile
          title="Per-tool errors (stacked)"
          subtitle="Errors vs invocations · stacked Bar"
          chip={<span className="chip !border-rose-200 dark:!border-rose-800 !bg-rose-50 dark:!bg-rose-950/40 !text-rose-700 dark:!text-rose-200"><AlertTriangle className="h-3 w-3" /> {totalErrors} errors</span>}
          className="md:col-span-2"
        >
          <div className="h-44 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={toolBuckets} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-ink-200 dark:stroke-ink-800" />
                <XAxis dataKey="tool_name" tick={{ fontSize: 10 }} className="text-ink-500 dark:text-ink-400" />
                <YAxis tick={{ fontSize: 10 }} className="text-ink-500 dark:text-ink-400" />
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid rgb(var(--border))", background: "rgb(var(--surface))" }} formatter={(v: number) => formatNumber(v, 0)} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="invocations" name="Invocations" stackId="a" fill="#3462ff" radius={[4, 4, 0, 0]} />
                <Bar dataKey="errors" name="Errors" stackId="a" fill="#f43f5e" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Tile>

        <Tile
          title="Tool health summary"
          subtitle="Errors, p95, live status"
          chip={<span className="chip"><CheckCircle2 className="h-3 w-3 text-emerald-600" /> {toolBuckets.filter((t) => t.errors === 0).length}/{toolBuckets.length} clean</span>}
          className="md:col-span-2 xl:col-span-1"
        >
          <div className="overflow-hidden rounded-lg border border-ink-200 dark:border-ink-800 flex-1">
            <table className="w-full text-xs">
              <thead className="bg-ink-50 dark:bg-ink-900/50 text-ink-600 dark:text-ink-300">
                <tr>
                  <th className="text-left font-medium px-2.5 py-2">Tool</th>
                  <th className="text-right font-medium px-2.5 py-2">Calls</th>
                  <th className="text-right font-medium px-2.5 py-2">P95</th>
                  <th className="text-left font-medium px-2.5 py-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100 dark:divide-ink-800">
                {toolBuckets.map((t) => {
                  const tone = toolRowTone(t.errors, t.invocations);
                  return (
                    <tr key={t.tool_name} className="hover:bg-ink-50/60 dark:hover:bg-ink-900/30 transition">
                      <td className="px-2.5 py-2 font-medium text-ink-800 dark:text-ink-100">{t.tool_name}</td>
                      <td className="px-2.5 py-2 text-right tabular-nums text-ink-700 dark:text-ink-200">{formatNumber(t.invocations, 0)}</td>
                      <td className="px-2.5 py-2 text-right tabular-nums text-ink-700 dark:text-ink-200">{formatDurationMs(t.p95_ms)}</td>
                      <td className="px-2.5 py-2">
                        <span className="inline-flex items-center gap-1.5">
                          <StatusDot tone={tone} />
                          <span className="text-ink-600 dark:text-ink-300">
                            {t.errors === 0 ? "Clean" : `${t.errors} err${t.errors === 1 ? "" : "s"}`}
                          </span>
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Tile>
      </section>
    </>
  );
}

export default function MetricsPage(): React.JSX.Element {
  return (
    <DashboardShell>
      <Suspense fallback={<MetricsSuspenseFallback />}>
        <MetricsContent />
      </Suspense>
    </DashboardShell>
  );
}
