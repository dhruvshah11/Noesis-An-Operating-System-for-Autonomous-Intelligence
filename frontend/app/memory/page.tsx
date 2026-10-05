"use client";

import { Suspense, useMemo } from "react";
import { ArrowRight, BrainCircuit, Database, HardDrive, Layers, MessageSquare, Sparkles, Users } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import type { ComponentType, SVGProps } from "react";
import type React from "react";

import { DashboardShell } from "@/components/layout/DashboardShell";
import { buildMockMemory } from "@/testing/mocks";
import { listMemory } from "@/lib/api/endpoints";
import { cn, formatNumber } from "@/lib/format";
import type { MemoryRecord, MemoryTier } from "@/lib/schemas";
import { useDemoMode } from "@/lib/demo";

interface Tier {
  readonly key: MemoryTier;
  readonly label: string;
  readonly description: string;
  readonly Icon: ComponentType<SVGProps<SVGSVGElement>>;
  readonly tone: "brand" | "emerald" | "amber" | "rose" | "violet" | "ink";
  readonly retention: string;
}

const TOP_TIERS: readonly Tier[] = [
  {
    key: "working",
    label: "Working Memory",
    description: "Scratchpad for in-flight execution context — prompt windows and tool outputs.",
    Icon: Layers,
    tone: "brand",
    retention: "Session / 24h TTL",
  },
  {
    key: "conversation",
    label: "Conversation Memory",
    description: "Turn-by-turn dialogue history and per-message metadata with agent attribution.",
    Icon: MessageSquare,
    tone: "emerald",
    retention: "30d \u2192 semantic roll-up",
  },
  {
    key: "semantic",
    label: "Semantic Memory",
    description: "Dense vector index of chunked documents, knowledge graphs and BM25 terms.",
    Icon: Database,
    tone: "amber",
    retention: "Persistent",
  },
  {
    key: "episodic",
    label: "Episodic Memory",
    description: "Timeline of completed tasks, traces, and reflection-delivered lessons learned.",
    Icon: Sparkles,
    tone: "violet",
    retention: "Persistent",
  },
  {
    key: "project",
    label: "Project Memory",
    description: "Workspace-scoped context: file trees, repos, conventions, docs, OKRs.",
    Icon: HardDrive,
    tone: "ink",
    retention: "Per workspace",
  },
  {
    key: "user",
    label: "User Memory",
    description: "Per-user preferences, identity, roles, and long-term learned behaviour cues.",
    Icon: Users,
    tone: "rose",
    retention: "Per user",
  },
] as const;

const toneBg: Record<Tier["tone"], string> = {
  brand: "from-brand-500/12 to-brand-700/0 text-brand-700 dark:text-brand-200",
  emerald: "from-emerald-500/12 to-emerald-700/0 text-emerald-700 dark:text-emerald-200",
  amber: "from-amber-500/12 to-amber-700/0 text-amber-700 dark:text-amber-200",
  rose: "from-rose-500/12 to-rose-700/0 text-rose-700 dark:text-rose-200",
  violet: "from-violet-500/12 to-violet-700/0 text-violet-700 dark:text-violet-200",
  ink: "from-ink-500/12 to-ink-700/0 text-ink-700 dark:text-ink-200",
};

const toneBorder: Record<Tier["tone"], string> = {
  brand: "hover:border-brand-400/60 dark:hover:border-brand-600/40",
  emerald: "hover:border-emerald-400/60 dark:hover:border-emerald-600/40",
  amber: "hover:border-amber-400/60 dark:hover:border-amber-600/40",
  rose: "hover:border-rose-400/60 dark:hover:border-rose-600/40",
  violet: "hover:border-violet-400/60 dark:hover:border-violet-600/40",
  ink: "hover:border-ink-400/60 dark:hover:border-ink-600/40",
};

async function queryMemoryRecords(): Promise<MemoryRecord[]> {
  const live = await listMemory();
  if (live.length > 0) return live;
  await new Promise((r) => setTimeout(r, 1000));
  return buildMockMemory(42, 48);
}

function MemoryInner(): React.JSX.Element {
  const demo = useDemoMode();
  const { data: records = demo.isDemoMode ? demo.memoryItems.length > 0 ? demo.memoryItems : buildMockMemory(demo.seed, 48) : buildMockMemory(42, 48), isFetching, isError } = useQuery({
    queryKey: ["memory", "items"] as const,
    queryFn: queryMemoryRecords,
    placeholderData: demo.isDemoMode ? buildMockMemory(demo.seed, 48) : buildMockMemory(42, 48),
    retry: 1,
    enabled: !demo.isDemoMode,
  });

  const perTier = useMemo(() => TOP_TIERS.map((t) => ({
    tier: t,
    count: records.filter((r) => r.tier === t.key).length,
  })), [records]);

  const top4 = perTier.slice(0, 4);

  return (
    <DashboardShell>
      <header className="flex flex-col gap-1">
        <p className="text-xs uppercase tracking-[0.18em] text-brand-600 dark:text-brand-300 font-semibold">
          Memory Explorer
          {isFetching && (
            <span className="ml-2 inline-flex items-center gap-1 text-brand-500 dark:text-brand-400">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500 dark:bg-brand-400" />
              syncing
            </span>
          )}
        </p>
        <h1 className="text-2xl font-bold tracking-tight text-ink-950 dark:text-ink-50">
          Multi-tier memory \u2014 from working scratchpad to persistent episodic recall.
        </h1>
        {isError && (
          <p className="mt-1 text-sm text-amber-700 dark:text-amber-300">
            Backend unreachable \u2014 falling back to local mock data.
          </p>
        )}
      </header>

      <section className="card p-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-dashed animate-fade-in">
        <div className="flex items-start gap-4">
          <div className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500/15 to-transparent text-brand-700 dark:text-brand-200">
            <BrainCircuit className="h-5 w-5" aria-hidden />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-ink-950 dark:text-ink-50">
              Use the MemoryExplorer visualizer
            </h2>
            <p className="mt-1 text-sm text-ink-600 dark:text-ink-300 max-w-xl">
              The full explorer combines UMAP embedding plots, tier-filtered search, and chunk-by-chunk provenance for every record. Jump to the dedicated view to inspect clusters and replay memory provenance.
            </p>
          </div>
        </div>
        <Link
          href="/memory/explorer"
          className="btn-primary shrink-0 self-start sm:self-auto"
        >
          Open MemoryExplorer
          <ArrowRight className="h-4 w-4" />
        </Link>
      </section>

      <section aria-label="Memory tiers">
        <div className="flex items-end justify-between mb-3">
          <h2 className="text-sm font-semibold text-ink-950 dark:text-ink-50">Tier overview</h2>
          <span className="text-xs text-ink-500 dark:text-ink-400">
            {formatNumber(records.length, 0)} records loaded
          </span>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {top4.map(({ tier, count }) => (
            <article
              key={tier.key}
              className={cn(
                "card p-5 flex flex-col gap-3 hover:shadow-card transition animate-fade-in",
                toneBorder[tier.tone],
              )}
            >
              <div className="flex items-center justify-between">
                <div
                  className={cn(
                    "inline-flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br",
                    toneBg[tier.tone],
                  )}
                >
                  <tier.Icon className="h-[18px] w-[18px]" aria-hidden />
                </div>
                <span className="chip">{tier.retention}</span>
              </div>
              <div>
                <div className="flex items-baseline justify-between gap-2">
                  <h3 className="text-sm font-semibold text-ink-950 dark:text-ink-50">{tier.label}</h3>
                  <span className="text-xs tabular-nums text-ink-500 dark:text-ink-400">
                    {formatNumber(count, 0)} records
                  </span>
                </div>
                <p className="mt-1.5 text-xs text-ink-600 dark:text-ink-300 leading-relaxed">
                  {tier.description}
                </p>
              </div>
            </article>
          ))}
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          {perTier.slice(4, 6).map(({ tier, count }) => (
            <article
              key={tier.key}
              className={cn(
                "card p-5 flex flex-col gap-3 hover:shadow-card transition animate-fade-in",
                toneBorder[tier.tone],
              )}
            >
              <div className="flex items-center justify-between">
                <div
                  className={cn(
                    "inline-flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br",
                    toneBg[tier.tone],
                  )}
                >
                  <tier.Icon className="h-[18px] w-[18px]" aria-hidden />
                </div>
                <span className="chip">{tier.retention}</span>
              </div>
              <div>
                <div className="flex items-baseline justify-between gap-2">
                  <h3 className="text-sm font-semibold text-ink-950 dark:text-ink-50">{tier.label}</h3>
                  <span className="text-xs tabular-nums text-ink-500 dark:text-ink-400">
                    {formatNumber(count, 0)} records
                  </span>
                </div>
                <p className="mt-1.5 text-xs text-ink-600 dark:text-ink-300 leading-relaxed">
                  {tier.description}
                </p>
              </div>
            </article>
          ))}
        </div>
      </section>
    </DashboardShell>
  );
}

function MemorySuspenseFallback(): React.JSX.Element {
  const records = buildMockMemory(42, 48);
  const perTier = TOP_TIERS.slice(0, 4).map((t) => ({
    tier: t,
    count: records.filter((r) => r.tier === t.key).length,
  }));
  return (
    <DashboardShell>
      <header className="flex flex-col gap-1">
        <p className="text-xs uppercase tracking-[0.18em] text-brand-600 dark:text-brand-300 font-semibold">
          Memory Explorer
          <span className="ml-2 inline-flex items-center gap-1 text-brand-500 dark:text-brand-400">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500 dark:bg-brand-400" />
            loading
          </span>
        </p>
        <h1 className="text-2xl font-bold tracking-tight text-ink-950 dark:text-ink-50">
          Multi-tier memory \u2014 from working scratchpad to persistent episodic recall.
        </h1>
      </header>
      <section className="card p-6 h-24 animate-pulse opacity-60 rounded-xl mb-4" />
      <section aria-label="Memory tiers skeleton">
        <div className="flex items-end justify-between mb-3">
          <h2 className="text-sm font-semibold text-ink-950 dark:text-ink-50">Tier overview</h2>
          <span className="text-xs text-ink-500 dark:text-ink-400 opacity-60">loading\u2026</span>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {perTier.map(({ tier }) => (
            <div
              key={tier.key}
              className="card p-5 animate-pulse opacity-60"
            >
              <div className="h-10 w-10 rounded-xl bg-ink-200 dark:bg-ink-800 mb-3" />
              <div className="h-4 w-2/3 rounded bg-ink-200 dark:bg-ink-800 mb-2" />
              <div className="h-3 w-full rounded bg-ink-200 dark:bg-ink-800" />
            </div>
          ))}
        </div>
      </section>
    </DashboardShell>
  );
}

export default function MemoryPage(): React.JSX.Element {
  return (
    <Suspense fallback={<MemorySuspenseFallback />}>
      <MemoryInner />
    </Suspense>
  );
}
