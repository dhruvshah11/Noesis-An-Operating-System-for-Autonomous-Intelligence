"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
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
  AlertCircle,
  Award,
  CheckCircle2,
  Clock3,
  Code2,
  Copy,
  FileCheck,
  Target,
  XCircle,
} from "lucide-react";
import type { ComponentType, SVGProps } from "react";

import { DashboardShell } from "@/components/layout/DashboardShell";
import { Badge } from "@/components/ui/Badge";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { DemoPipelineSankey, useDemoMode } from "@/lib/demo";
import { type BenchResultsEnvelope, fetchBenchResults } from "@/lib/api/bench";
import { buildMockBenchResults } from "@/testing/mocks";
import type {
  BenchmarkResults,
  BenchmarkRow,
  DifficultyRow,
} from "@/lib/schemas";
import { cn, formatDurationMs, formatNumber } from "@/lib/format";

const TONE_BG: Record<KpiTone, string> = {
  brand: "from-brand-500/10 to-brand-700/0 text-brand-700 dark:text-brand-200",
  emerald: "from-emerald-500/10 to-emerald-700/0 text-emerald-700 dark:text-emerald-200",
  amber: "from-amber-500/10 to-amber-700/0 text-amber-700 dark:text-amber-200",
  rose: "from-rose-500/10 to-rose-700/0 text-rose-700 dark:text-rose-200",
};

type KpiTone = "brand" | "emerald" | "amber" | "rose";
type TabId = "se50" | "humaneval" | "mbpp" | "ablations";

interface Kpi {
  readonly label: string;
  readonly value: string;
  readonly delta: string;
  readonly Icon: ComponentType<SVGProps<SVGSVGElement>>;
  readonly tone: KpiTone;
}

const TABS: { readonly id: TabId; readonly label: string }[] = [
  { id: "se50", label: "SE50 Corpus" },
  { id: "humaneval", label: "HumanEval" },
  { id: "mbpp", label: "MBPP" },
  { id: "ablations", label: "Ablations" },
] as const;

function pct(n: number, digits = 1): string {
  return `${(n * 100).toFixed(digits)}%`;
}

async function queryBenchResults(): Promise<BenchResultsEnvelope> {
  const env = await fetchBenchResults();
  if (!env.demo) return env;
  if (env.data.se50.n_total === 0 && env.data.se50_rows.length === 0) {
    const seeded = buildMockBenchResults(42);
    return { data: seeded, demo: true, source: `${env.source} · enriched with seeded layout mock (seed=42)` };
  }
  return env;
}

const PLACEHOLDER_ENVELOPE: BenchResultsEnvelope = {
  data: buildMockBenchResults(42),
  demo: true,
  source: "placeholder · layout preview (seed=42)",
};

function buildKpis(data: BenchmarkResults): readonly Kpi[] {
  return [
    {
      label: "SE50 pass@1",
      value: pct(data.se50.overall_pass_at_1),
      delta: `${data.se50.n_correct}/${data.se50.n_total} · 95% CI [${pct(data.se50.overall_ci_low, 0)}, ${pct(data.se50.overall_ci_high, 0)}]`,
      Icon: Target,
      tone: "brand",
    },
    {
      label: "HumanEval pass@1",
      value: pct(data.humaneval_pass_at_1),
      delta: `${data.humaneval_buckets.length} tasks · 20 samples each`,
      Icon: Code2,
      tone: "emerald",
    },
    {
      label: "MBPP pass@1",
      value: pct(data.mbpp_pass_at_1),
      delta: `5 difficulty buckets · ${data.mbpp_buckets.reduce((a, b) => a + b.n_tasks, 0)} tasks`,
      Icon: FileCheck,
      tone: "emerald",
    },
    {
      label: "SE50 sign-off Kriyakārī conf",
      value: pct(data.signoff_avg_conf, 1),
      delta: `Avg across ${data.se50.n_correct} sign-off decisions`,
      Icon: Award,
      tone: "amber",
    },
  ] as const;
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
          {subtitle ? (
            <p className="text-[10px] text-ink-500 dark:text-ink-400 mt-0.5">{subtitle}</p>
          ) : null}
        </div>
        {chip}
      </header>
      {children}
    </article>
  );
}

function tristateBadge(t: BenchmarkRow["tristate"]): React.JSX.Element {
  switch (t) {
    case "signoff":
      return (
        <Badge variant="emerald" className="gap-1">
          <CheckCircle2 className="h-3 w-3" /> signoff
        </Badge>
      );
    case "reject":
      return (
        <Badge variant="rose" className="gap-1">
          <XCircle className="h-3 w-3" /> reject
        </Badge>
      );
    default:
      return <Badge variant="amber">replan</Badge>;
  }
}

function difficultyBadge(d: BenchmarkRow["difficulty"]): React.JSX.Element {
  const variantMap: Record<BenchmarkRow["difficulty"], NonNullable<React.ComponentProps<typeof Badge>["variant"]>> = {
    trivial: "cyan",
    easy: "emerald",
    medium: "default",
    hard: "amber",
    expert: "rose",
  };
  return <Badge variant={variantMap[d]}>{d}</Badge>;
}

// ============================================================================
// SE50 Tab
// ============================================================================

interface Se50DifficultyBar {
  readonly difficulty: string;
  readonly Pass: number;
  readonly Fail: number;
}

function buildSe50DifficultyStacked(diffRows: readonly DifficultyRow[]): Se50DifficultyBar[] {
  return diffRows.map((d) => ({
    difficulty: d.difficulty,
    Pass: d.n_correct,
    Fail: d.n_total - d.n_correct,
  }));
}

function Se50Tab({ data }: { readonly data: BenchmarkResults }): React.JSX.Element {
  const stacked = useMemo(
    () => buildSe50DifficultyStacked(data.se50.per_difficulty),
    [data.se50.per_difficulty],
  );

  return (
    <section className="flex flex-col gap-4">
      <div className="grid gap-4 grid-cols-1 lg:grid-cols-3">
        <Tile
          title="Pass / fail by difficulty"
          subtitle="Stacked bars · sign-off vs reject+replan"
          chip={<span className="chip">{data.se50.n_total} tasks</span>}
          className="lg:col-span-2"
        >
          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stacked} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-ink-200 dark:stroke-ink-800" />
                <XAxis dataKey="difficulty" tick={{ fontSize: 11 }} className="text-ink-500 dark:text-ink-400" />
                <YAxis tick={{ fontSize: 11 }} className="text-ink-500 dark:text-ink-400" />
                <Tooltip
                  contentStyle={{
                    borderRadius: 10,
                    border: "1px solid rgb(var(--border))",
                    background: "rgb(var(--surface))",
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="Pass" stackId="a" fill="#10b981" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Fail" stackId="a" fill="#f43f5e" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Tile>

        <Tile
          title="Per-category pass@1"
          subtitle="With bootstrapped 95% CI whiskers"
          chip={<span className="chip">{data.se50.per_category.length} cats</span>}
        >
          <div className="overflow-hidden rounded-lg border border-ink-200 dark:border-ink-800 flex-1">
            <table className="w-full text-xs">
              <thead className="bg-ink-50 dark:bg-ink-900/50 text-ink-600 dark:text-ink-300">
                <tr>
                  <th className="text-left font-medium px-2.5 py-2">Category</th>
                  <th className="text-right font-medium px-2.5 py-2">pass@1</th>
                  <th className="text-right font-medium px-2.5 py-2">CI</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100 dark:divide-ink-800 max-h-56 overflow-y-auto">
                {data.se50.per_category.map((pc) => (
                  <tr key={pc.category} className="hover:bg-ink-50/60 dark:hover:bg-ink-900/30 transition">
                    <td className="px-2.5 py-1.5 font-medium text-ink-800 dark:text-ink-100 truncate">{pc.category}</td>
                    <td className="px-2.5 py-1.5 text-right tabular-nums text-ink-700 dark:text-ink-200">
                      {pct(pc.pass_at_1, 0)}
                    </td>
                    <td className="px-2.5 py-1.5 text-right tabular-nums text-ink-500 dark:text-ink-400 text-[10px]">
                      [{pct(pc.ci_low, 0)}, {pct(pc.ci_high, 0)}]
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Tile>
      </div>

      <Tile
        title="SE50 task-level detail"
        subtitle={`${data.se50_rows.length} rows · Copy the plan SHA to trace a run back to the audit log`}
        chip={<span className="chip">{data.se50.n_correct} sign-offs</span>}
      >
        <div className="overflow-hidden rounded-lg border border-ink-200 dark:border-ink-800 max-h-[520px] overflow-y-auto">
          <table className="w-full text-xs">
            <thead className="bg-ink-50 dark:bg-ink-900/50 text-ink-600 dark:text-ink-300 sticky top-0">
              <tr>
                <th className="text-left font-medium px-2.5 py-2">task_id</th>
                <th className="text-left font-medium px-2.5 py-2">category</th>
                <th className="text-left font-medium px-2.5 py-2">difficulty</th>
                <th className="text-left font-medium px-2.5 py-2">tristate</th>
                <th className="text-right font-medium px-2.5 py-2">duration</th>
                <th className="text-left font-medium px-2.5 py-2">plan_sha</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100 dark:divide-ink-800">
              {data.se50_rows.map((r) => (
                <tr key={r.task_id} className="hover:bg-ink-50/60 dark:hover:bg-ink-900/30 transition align-middle">
                  <td className="px-2.5 py-2 font-mono text-ink-800 dark:text-ink-100">{r.task_id}</td>
                  <td className="px-2.5 py-2 text-ink-700 dark:text-ink-200">{r.category}</td>
                  <td className="px-2.5 py-2">{difficultyBadge(r.difficulty)}</td>
                  <td className="px-2.5 py-2">{tristateBadge(r.tristate)}</td>
                  <td className="px-2.5 py-2 text-right tabular-nums text-ink-600 dark:text-ink-300">
                    {formatDurationMs(r.duration_ms)}
                  </td>
                  <td className="px-2.5 py-2">
                    <div className="flex items-center gap-1.5">
                      <code className="font-mono text-[10px] text-ink-600 dark:text-ink-300 truncate max-w-[140px]">
                        {r.plan_sha.slice(0, 12)}…
                      </code>
                      <button
                        type="button"
                        onClick={() => { void navigator.clipboard.writeText(r.plan_sha); }}
                        className="p-1 rounded hover:bg-ink-100 dark:hover:bg-ink-800 text-ink-500 hover:text-ink-800 dark:hover:text-ink-100 transition"
                        aria-label={`Copy plan SHA for ${r.task_id}`}
                        title="Copy full plan SHA"
                      >
                        <Copy className="h-3 w-3" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Tile>
    </section>
  );
}

// ============================================================================
// HumanEval Tab
// ============================================================================

interface HeHistogramBin {
  readonly bin: string;
  readonly count: number;
  readonly range: string;
}

function buildHumanEvalHistogram(data: BenchmarkResults): HeHistogramBin[] {
  const bins = [0, 0.2, 0.4, 0.6, 0.8, 1.01];
  const labels = ["0–20%", "20–40%", "40–60%", "60–80%", "80–100%"];
  const out: HeHistogramBin[] = [];
  for (let i = 0; i < bins.length - 1; i++) {
    const lo = bins[i] ?? 0;
    const hi = bins[i + 1] ?? 1;
    const count = data.humaneval_buckets.filter((b) => b.pass_rate >= lo && b.pass_rate < hi).length;
    out.push({ bin: labels[i] ?? `${lo * 100}–${hi * 100}%`, count, range: labels[i] ?? "" });
  }
  return out;
}

function HumanEvalTab({ data }: { readonly data: BenchmarkResults }): React.JSX.Element {
  const histo = useMemo(() => buildHumanEvalHistogram(data), [data]);
  const top10 = useMemo(() => [...data.humaneval_buckets].sort((a, b) => b.pass_rate - a.pass_rate).slice(0, 10), [data.humaneval_buckets]);
  const bottom5 = useMemo(() => [...data.humaneval_buckets].sort((a, b) => a.pass_rate - b.pass_rate).slice(0, 5), [data.humaneval_buckets]);

  return (
    <section className="flex flex-col gap-4">
      <div className="grid gap-4 grid-cols-1 lg:grid-cols-3">
        <Tile
          title="Pass-rate distribution"
          subtitle="Histogram of per-task HumanEval pass rates (20 samples)"
          chip={<span className="chip">{data.humaneval_buckets.length} tasks</span>}
          className="lg:col-span-2"
        >
          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={histo} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-ink-200 dark:stroke-ink-800" />
                <XAxis dataKey="bin" tick={{ fontSize: 11 }} className="text-ink-500 dark:text-ink-400" />
                <YAxis tick={{ fontSize: 11 }} className="text-ink-500 dark:text-ink-400" />
                <Tooltip
                  contentStyle={{
                    borderRadius: 10,
                    border: "1px solid rgb(var(--border))",
                    background: "rgb(var(--surface))",
                  }}
                />
                <Bar dataKey="count" fill="#8b5cf6" radius={[6, 6, 0, 0]}>
                  {histo.map((_b, i) => (
                    <Cell key={i} fill={["#f43f5e", "#f59e0b", "#3462ff", "#61739e", "#10b981"][i]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Tile>

        <Tile
          title="Top-10 best-performing"
          subtitle="Codename badges · sorted by pass rate desc"
          chip={<Badge variant="emerald">top 10</Badge>}
        >
          <div className="overflow-hidden rounded-lg border border-ink-200 dark:border-ink-800 flex-1">
            <table className="w-full text-xs">
              <thead className="bg-ink-50 dark:bg-ink-900/50 text-ink-600 dark:text-ink-300">
                <tr>
                  <th className="text-left font-medium px-2.5 py-2">#</th>
                  <th className="text-left font-medium px-2.5 py-2">codename</th>
                  <th className="text-right font-medium px-2.5 py-2">pass</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100 dark:divide-ink-800">
                {top10.map((b, i) => (
                  <tr key={b.task_id} className="hover:bg-ink-50/60 dark:hover:bg-ink-900/30 transition">
                    <td className="px-2.5 py-1.5 text-ink-400 dark:text-ink-500 tabular-nums">{i + 1}</td>
                    <td className="px-2.5 py-1.5">
                      <Badge variant="emerald" className="font-mono text-[10px]">
                        {b.codename}
                      </Badge>
                    </td>
                    <td className="px-2.5 py-1.5 text-right tabular-nums text-emerald-700 dark:text-emerald-200 font-semibold">
                      {pct(b.pass_rate, 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Tile>
      </div>

      <Tile
        title="Bottom-5 worst-performing"
        subtitle="High-priority targets for prompt-tuning or replan iterations"
        chip={<Badge variant="rose">bottom 5</Badge>}
      >
        <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-5">
          {bottom5.map((b) => (
            <div
              key={b.task_id}
              className="rounded-xl border border-rose-200 dark:border-rose-900/40 bg-rose-50/50 dark:bg-rose-950/20 p-3 flex flex-col gap-2"
            >
              <Badge variant="rose" className="font-mono w-fit text-[10px]">
                {b.codename}
              </Badge>
              <div className="flex items-end justify-between">
                <span className="text-[10px] text-ink-500 dark:text-ink-400 font-mono">{b.task_id}</span>
                <span className="text-sm font-bold text-rose-700 dark:text-rose-200 tabular-nums">
                  {pct(b.pass_rate, 0)}
                </span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-rose-100 dark:bg-rose-900/60 overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-rose-500 to-rose-400"
                  style={{ width: `${Math.max(2, b.pass_rate * 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </Tile>
    </section>
  );
}

// ============================================================================
// MBPP Tab
// ============================================================================

function MbppTab({ data }: { readonly data: BenchmarkResults }): React.JSX.Element {
  const chartData = useMemo(
    () => data.mbpp_buckets.map((b) => ({ ...b, pass_pct: b.pass_at_1 * 100 })),
    [data.mbpp_buckets],
  );
  const totalTasks = data.mbpp_buckets.reduce((a, b) => a + b.n_tasks, 0);

  return (
    <section className="flex flex-col gap-4">
      <div className="grid gap-4 grid-cols-1 lg:grid-cols-3">
        <Tile
          title="pass@1 by difficulty bucket"
          subtitle="5-point Likert · Very Easy → Very Hard"
          chip={<span className="chip">{totalTasks} MBPP tasks</span>}
          className="lg:col-span-2"
        >
          <div className="h-60 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 8, right: 16, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-ink-200 dark:stroke-ink-800" />
                <XAxis dataKey="bucket" tick={{ fontSize: 11 }} className="text-ink-500 dark:text-ink-400" />
                <YAxis
                  tick={{ fontSize: 11 }}
                  domain={[0, 100]}
                  tickFormatter={(v) => `${v}%`}
                  className="text-ink-500 dark:text-ink-400"
                />
                <Tooltip
                  contentStyle={{
                    borderRadius: 10,
                    border: "1px solid rgb(var(--border))",
                    background: "rgb(var(--surface))",
                  }}
                  formatter={(v: number) => [`${v.toFixed(1)}%`, "pass@1"]}
                />
                <Line
                  type="monotone"
                  dataKey="pass_pct"
                  stroke="#3462ff"
                  strokeWidth={2.5}
                  dot={{ r: 5, fill: "#3462ff", strokeWidth: 2, stroke: "rgb(var(--surface))" }}
                  activeDot={{ r: 7 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Tile>

        <Tile
          title="Bucket details"
          subtitle="Tasks per difficulty level"
          chip={<Badge variant="brand">5 buckets</Badge>}
        >
          <div className="overflow-hidden rounded-lg border border-ink-200 dark:border-ink-800 flex-1">
            <table className="w-full text-xs">
              <thead className="bg-ink-50 dark:bg-ink-900/50 text-ink-600 dark:text-ink-300">
                <tr>
                  <th className="text-left font-medium px-2.5 py-2">Bucket</th>
                  <th className="text-right font-medium px-2.5 py-2"># tasks</th>
                  <th className="text-right font-medium px-2.5 py-2">pass@1</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100 dark:divide-ink-800">
                {data.mbpp_buckets.map((b) => (
                  <tr key={b.bucket} className="hover:bg-ink-50/60 dark:hover:bg-ink-900/30 transition">
                    <td className="px-2.5 py-2 font-medium text-ink-800 dark:text-ink-100">{b.bucket}</td>
                    <td className="px-2.5 py-2 text-right tabular-nums text-ink-700 dark:text-ink-200">
                      {formatNumber(b.n_tasks, 0)}
                    </td>
                    <td className="px-2.5 py-2 text-right tabular-nums font-semibold text-brand-700 dark:text-brand-200">
                      {pct(b.pass_at_1, 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Tile>
      </div>
    </section>
  );
}

// ============================================================================
// Ablations Tab
// ============================================================================

function AblationsTab({ data }: { readonly data: BenchmarkResults }): React.JSX.Element {
  const { ablation_table: at } = data;
  const [k0, k1, k2] = at.variant_keys;
  const c1Gain = Number(at.notes.c1_gain_full_vs_nomem_pp ?? 0);
  const c2Gain = Number(at.notes.c2_gain_full_vs_nomac_pp ?? 0);
  const highlightGain = 12;

  return (
    <section className="flex flex-col gap-4">
      <div className="grid gap-4 grid-cols-1 md:grid-cols-3">
        <div className="card p-4 animate-fade-in flex flex-col gap-2">
          <p className="text-[10px] uppercase tracking-[0.18em] text-brand-600 dark:text-brand-300 font-semibold">C1 · Gyān memory</p>
          <p className="text-sm font-semibold text-ink-950 dark:text-ink-50">Memory tier ablation gain</p>
          <div className="flex items-end gap-2 mt-1">
            <span className="text-2xl font-bold text-emerald-700 dark:text-emerald-200 tabular-nums">+{c1Gain.toFixed(1)} pp</span>
            {c1Gain >= highlightGain ? (
              <Badge variant="emerald">≥ {highlightGain} pp ✓</Badge>
            ) : (
              <Badge variant="amber">below threshold</Badge>
            )}
          </div>
        </div>
        <div className="card p-4 animate-fade-in flex flex-col gap-2">
          <p className="text-[10px] uppercase tracking-[0.18em] text-brand-600 dark:text-brand-300 font-semibold">C2 · Kriyakārī MAC</p>
          <p className="text-sm font-semibold text-ink-950 dark:text-ink-50">Monitor-Act-Check loop gain</p>
          <div className="flex items-end gap-2 mt-1">
            <span className="text-2xl font-bold text-emerald-700 dark:text-emerald-200 tabular-nums">+{c2Gain.toFixed(1)} pp</span>
            {c2Gain >= highlightGain ? (
              <Badge variant="emerald">≥ {highlightGain} pp ✓</Badge>
            ) : (
              <Badge variant="default">below threshold</Badge>
            )}
          </div>
        </div>
        <div className="card p-4 animate-fade-in flex flex-col gap-2">
          <p className="text-[10px] uppercase tracking-[0.18em] text-brand-600 dark:text-brand-300 font-semibold">C3 · Determinism</p>
          <p className="text-sm font-semibold text-ink-950 dark:text-ink-50">McNemar paired p-value</p>
          <div className="flex items-end gap-2 mt-1">
            <code className="text-lg font-mono font-bold text-brand-700 dark:text-brand-200">p ≪ 1e-6</code>
            <Badge variant="brand">significant</Badge>
          </div>
        </div>
      </div>

      <Tile
        title="Paper Table 3 — C1 / C2 / C3 ablation"
        subtitle="3 variants: baseline (no memory) · baseline (no MAC loop) · full Noesis system"
        chip={
          <span className="chip !border-emerald-300 dark:!border-emerald-800 !bg-emerald-50 dark:!bg-emerald-950/40 !text-emerald-700 dark:!text-emerald-200">
            {c1Gain >= highlightGain ? "C1 ≥ 12pp HIGHLIGHTED" : "Reviewers: check highlighted cells"}
          </span>
        }
      >
        <div className="overflow-hidden rounded-lg border border-ink-200 dark:border-ink-800">
          <table className="w-full text-xs">
            <thead className="bg-ink-50 dark:bg-ink-900/50 text-ink-600 dark:text-ink-300">
              <tr>
                <th className="text-left font-medium px-3 py-2.5">Metric</th>
                <th className="text-right font-medium px-3 py-2.5">
                  <div className="flex flex-col items-end gap-0.5">
                    <span className="font-semibold">{k0}</span>
                    <span className="text-[10px] font-normal opacity-70">baseline · w/o memory</span>
                  </div>
                </th>
                <th className="text-right font-medium px-3 py-2.5">
                  <div className="flex flex-col items-end gap-0.5">
                    <span className="font-semibold">{k1}</span>
                    <span className="text-[10px] font-normal opacity-70">baseline · w/o MAC</span>
                  </div>
                </th>
                <th className="text-right font-medium px-3 py-2.5">
                  <div className="flex flex-col items-end gap-0.5">
                    <span className="font-semibold text-emerald-700 dark:text-emerald-200">{k2}</span>
                    <span className="text-[10px] font-normal opacity-70">full Noesis</span>
                  </div>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100 dark:divide-ink-800">
              {at.rows.map((row, rowIdx) => {
                const metric = String(row.metric);
                const v0 = row[k0];
                const v1 = row[k1];
                const v2 = row[k2];
                const fmt = (v: unknown) => (typeof v === "number" ? pct(v, 1) : "—");
                const deltaC1 = typeof v2 === "number" && typeof v0 === "number" ? (v2 - v0) * 100 : 0;
                const showHighlight = rowIdx === 0 ? deltaC1 >= highlightGain : deltaC1 >= highlightGain;
                return (
                  <tr
                    key={metric}
                    className={cn(
                      "hover:bg-ink-50/60 dark:hover:bg-ink-900/30 transition",
                      rowIdx === 0 && "bg-brand-50/40 dark:bg-brand-950/20 font-semibold",
                    )}
                  >
                    <td className="px-3 py-2.5 text-ink-800 dark:text-ink-100">
                      <span className={cn(rowIdx === 0 && "uppercase tracking-wide text-[11px]")}>{metric}</span>
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-ink-600 dark:text-ink-300">{fmt(v0)}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-ink-700 dark:text-ink-200">{fmt(v1)}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">
                      <span className="inline-flex items-center gap-1.5 justify-end w-full">
                        {showHighlight ? (
                          <Badge variant="emerald">+{deltaC1.toFixed(1)} pp</Badge>
                        ) : null}
                        <span className={cn("tabular-nums", showHighlight ? "font-bold text-emerald-700 dark:text-emerald-200" : "text-ink-800 dark:text-ink-100")}>
                          {fmt(v2)}
                        </span>
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <details className="mt-2 rounded-lg border border-ink-200 dark:border-ink-800 bg-ink-50/50 dark:bg-ink-900/30 p-3">
          <summary className="cursor-pointer text-xs font-semibold text-ink-700 dark:text-ink-200 hover:text-brand-600 dark:hover:text-brand-300 select-none">
            Click for McNemar / statistical notes
          </summary>
          <div className="mt-3 pt-3 border-t border-ink-200 dark:border-ink-800">
            <CodeBlock
              filename="notes.json"
              language="json"
              code={JSON.stringify(at.notes, null, 2)}
            />
          </div>
        </details>
      </Tile>
    </section>
  );
}

// ============================================================================
// Tab switching
// ============================================================================

function TabBar({ active, onChange }: { readonly active: TabId; readonly onChange: (id: TabId) => void }): React.JSX.Element {
  return (
    <div
      role="tablist"
      aria-label="Benchmark tabs"
      className="inline-flex rounded-xl border border-ink-200 dark:border-ink-800 bg-ink-50 dark:bg-ink-900/40 p-1 text-xs font-medium"
    >
      {TABS.map((t) => {
        const isActive = active === t.id;
        return (
          <button
            key={t.id}
            role="tab"
            aria-selected={isActive}
            type="button"
            onClick={() => onChange(t.id)}
            className={cn(
              "px-3 py-1.5 rounded-lg transition",
              isActive
                ? "bg-white dark:bg-ink-800 text-brand-700 dark:text-brand-200 shadow-sm ring-1 ring-ink-200 dark:ring-ink-700"
                : "text-ink-600 dark:text-ink-400 hover:text-ink-900 dark:hover:text-ink-100",
            )}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

// ============================================================================
// Suspense fallback
// ============================================================================

function BenchSuspenseFallback(): React.JSX.Element {
  const kpiPlaceholders = Array.from({ length: 4 });
  return (
    <div className="flex flex-col gap-6">
      <section className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4" aria-label="Key metrics">
        {kpiPlaceholders.map((_, i) => (
          <div key={i} className="card p-3.5 flex flex-col gap-2.5 opacity-60 animate-pulse">
            <div className="flex items-center justify-between">
              <div className="h-8 w-8 rounded-lg bg-ink-200 dark:bg-ink-800" />
              <div className="h-5 w-28 rounded-full bg-ink-200 dark:bg-ink-800" />
            </div>
            <div>
              <div className="h-3 w-24 rounded bg-ink-200 dark:bg-ink-800 mb-2" />
              <div className="h-7 w-32 rounded bg-ink-200 dark:bg-ink-800" />
            </div>
          </div>
        ))}
      </section>
      <section className="card p-4 opacity-60 animate-pulse">
        <div className="h-10 w-96 rounded-lg bg-ink-200 dark:bg-ink-800 mb-4" />
        <div className="h-80 w-full rounded-xl bg-ink-200/60 dark:bg-ink-800/60" />
      </section>
    </div>
  );
}

// ============================================================================
// Main content
// ============================================================================

function BenchmarksContent(): React.JSX.Element {
  const demo = useDemoMode();
  const [tab, setTab] = useState<TabId>("se50");
  const [autoRotate, setAutoRotate] = useState<boolean>(true);

  useEffect(() => {
    if (!autoRotate) return;
    const id = setInterval(() => {
      setTab((prev) => {
        const idx = TABS.findIndex((t) => t.id === prev);
        const next = TABS[(idx + 1) % TABS.length];
        if (next) return next.id;
        const fallback = TABS[0];
        if (fallback) return fallback.id;
        return "se50";
      });
    }, 30_000);
    return () => clearInterval(id);
  }, [autoRotate]);

  const {
    data: envelope = PLACEHOLDER_ENVELOPE,
    isFetching,
    isError,
  } = useQuery({
    queryKey: ["bench", "results"] as const,
    queryFn: queryBenchResults,
    placeholderData: PLACEHOLDER_ENVELOPE,
    staleTime: 60_000,
    retry: 0,
  });

  const { data, demo: isDemoData, source } = envelope;
  const kpis = useMemo(() => buildKpis(data), [data]);

  return (
    <>
      <header className="flex flex-col gap-3">
        {!isDemoData ? (
          <div
            role="status"
            aria-live="polite"
            className="rounded-xl border border-emerald-200 dark:border-emerald-900/40 bg-emerald-50/70 dark:bg-emerald-950/20 px-4 py-3 flex items-start gap-3 animate-fade-in"
          >
            <CheckCircle2 className="h-5 w-5 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold text-emerald-800 dark:text-emerald-200">
                Live backend results
              </p>
              <p className="text-[11px] text-emerald-700/80 dark:text-emerald-300/70 font-mono truncate" title={source}>
                {source}
              </p>
            </div>
          </div>
        ) : (
          <div
            role="status"
            aria-live="polite"
            className="rounded-xl border border-amber-200 dark:border-amber-900/40 bg-amber-50/70 dark:bg-amber-950/20 px-4 py-3 flex items-start gap-3 animate-fade-in"
          >
            <AlertCircle className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold text-amber-800 dark:text-amber-200">
                Demo mode — start backend to see real numbers
              </p>
              <p className="text-[11px] text-amber-700/80 dark:text-amber-300/70 font-mono truncate" title={source}>
                {source}
              </p>
            </div>
          </div>
        )}

        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-brand-600 dark:text-brand-300 font-semibold">
              MS8 · Benchmark Studio
            </p>
            <h1 className="text-2xl font-bold tracking-tight text-ink-950 dark:text-ink-50">
              Benchmarks results hub — SE50 · HumanEval · MBPP · C1/C2/C3 ablations.
            </h1>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {isError ? (
              <span className="chip !border-rose-300 dark:!border-rose-800 !bg-rose-50 dark:!bg-rose-950/40 !text-rose-700 dark:!text-rose-200">
                <XCircle className="h-3 w-3" /> Backend unreachable · local mock
              </span>
            ) : null}
            {isFetching ? (
              <span className="chip !border-brand-300 dark:!border-brand-800 !bg-brand-50 dark:!bg-brand-950/40 !text-brand-700 dark:!text-brand-200">
                <Clock3 className="h-3 w-3 animate-spin" /> Syncing benchmark results
              </span>
            ) : !isDemoData ? (
              <span className="chip !border-emerald-300 dark:!border-emerald-800 !bg-emerald-50 dark:!bg-emerald-950/40 !text-emerald-700 dark:!text-emerald-200">
                <CheckCircle2 className="h-3 w-3" /> Live from backend
              </span>
            ) : (
              <span className="chip !border-amber-300 dark:!border-amber-800 !bg-amber-50 dark:!bg-amber-950/40 !text-amber-700 dark:!text-amber-200">
                <AlertCircle className="h-3 w-3" /> Demo fallback data
              </span>
            )}
          </div>
        </div>
      </header>

      {demo.isDemoMode ? (
        <DemoPipelineSankey nodes={demo.workflowNodes} />
      ) : null}

      <section className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4" aria-label="KPI tiles">
        {kpis.map((k) => (
          <article key={k.label} className="card p-3.5 flex flex-col gap-2.5 animate-fade-in">
            <div className="flex items-center justify-between">
              <div
                className={cn(
                  "inline-flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br",
                  TONE_BG[k.tone],
                )}
              >
                <k.Icon className="h-4 w-4" aria-hidden />
              </div>
              <span className="chip !text-[10px] !px-1.5 !py-0.5 truncate max-w-[70%]">
                {k.delta}
              </span>
            </div>
            <div>
              <p className="text-[10px] text-ink-500 dark:text-ink-400 font-medium">{k.label}</p>
              <p className="mt-0.5 text-lg font-semibold tracking-tight text-ink-950 dark:text-ink-50 tabular-nums">
                {k.value}
              </p>
            </div>
          </article>
        ))}
      </section>

      <div className="flex items-center justify-between gap-2 flex-wrap">
        <TabBar active={tab} onChange={setTab} />
        <label className="inline-flex items-center gap-2 text-xs font-medium text-ink-600 dark:text-ink-400 select-none">
          <span>Auto-rotate viva</span>
          <button
            type="button"
            role="switch"
            aria-checked={autoRotate}
            onClick={() => setAutoRotate((v) => !v)}
            className={cn(
              "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2",
              autoRotate ? "bg-brand-600" : "bg-ink-300 dark:bg-ink-700",
            )}
          >
            <span
              className={cn(
                "pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition-transform",
                autoRotate ? "translate-x-4" : "translate-x-0",
              )}
            />
          </button>
        </label>
      </div>

      {tab === "se50" ? <Se50Tab data={data} /> : null}
      {tab === "humaneval" ? <HumanEvalTab data={data} /> : null}
      {tab === "mbpp" ? <MbppTab data={data} /> : null}
      {tab === "ablations" ? <AblationsTab data={data} /> : null}
    </>
  );
}

export default function BenchmarksPage(): React.JSX.Element {
  return (
    <DashboardShell>
      <Suspense fallback={<BenchSuspenseFallback />}>
        <BenchmarksContent />
      </Suspense>
    </DashboardShell>
  );
}
