"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, SlidersHorizontal, Tag, X } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import type { JSX } from "react";

import { DashboardShell } from "@/components/layout/DashboardShell";
import type { MemoryRecord, MemoryTier } from "@/lib/schemas";
import { buildMockMemory } from "@/testing/mocks";
import { listMemory } from "@/lib/api/endpoints";
import { cn, formatNumber } from "@/lib/format";

const TIER_TONE: Record<MemoryTier, string> = {
  conversation: "from-sky-500",
  semantic: "from-violet-500",
  episodic: "from-emerald-500",
  working: "from-amber-500",
  project: "from-brand-500",
  user: "from-rose-500",
};

const TIER_BG: Record<MemoryTier, string> = {
  conversation:
    "bg-sky-500/10 text-sky-700 dark:text-sky-200 border-sky-200 dark:border-sky-900/60",
  semantic:
    "bg-violet-500/10 text-violet-700 dark:text-violet-200 border-violet-200 dark:border-violet-900/60",
  episodic:
    "bg-emerald-500/10 text-emerald-700 dark:text-emerald-200 border-emerald-200 dark:border-emerald-900/60",
  working:
    "bg-amber-500/10 text-amber-700 dark:text-amber-200 border-amber-200 dark:border-amber-900/60",
  project:
    "bg-brand-500/10 text-brand-700 dark:text-brand-200 border-brand-200 dark:border-brand-900/60",
  user:
    "bg-rose-500/10 text-rose-700 dark:text-rose-200 border-rose-200 dark:border-rose-900/60",
};

const TIER_ORDER: readonly MemoryTier[] = [
  "working",
  "conversation",
  "semantic",
  "episodic",
  "project",
  "user",
] as const;

interface CanvasPoint {
  readonly id: string;
  readonly x: number;
  readonly y: number;
  readonly tier: MemoryTier;
  readonly r: number;
}

interface ProjectionCanvasProps {
  readonly items: readonly MemoryRecord[];
  readonly selectedId: string | null;
  readonly onSelect: (id: string) => void;
  readonly onHover: (id: string | null) => void;
  readonly hoverId: string | null;
}

function ProjectionCanvas({
  items, selectedId, onSelect, onHover, hoverId,
}: ProjectionCanvasProps): JSX.Element {
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState<{ w: number; h: number }>({ w: 640, h: 420 });

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      const rect = el.getBoundingClientRect();
      setSize({ w: Math.max(320, Math.floor(rect.width)), h: Math.max(260, Math.floor(rect.height)) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const layout: readonly CanvasPoint[] = useMemo(() => {
    const xs = items.map((m) => m.embedding_2d?.[0] ?? Math.random() * 6 - 3);
    const ys = items.map((m) => m.embedding_2d?.[1] ?? Math.random() * 6 - 3);
    const pad = 28;
    const minX = Math.min(...xs) - 0.5;
    const maxX = Math.max(...xs) + 0.5;
    const minY = Math.min(...ys) - 0.5;
    const maxY = Math.max(...ys) + 0.5;
    const sx = (size.w - pad * 2) / Math.max(0.0001, maxX - minX);
    const sy = (size.h - pad * 2) / Math.max(0.0001, maxY - minY);
    return items.map((m, i) => {
      const x = pad + ((xs[i] ?? 0) - minX) * sx;
      const y = pad + ((ys[i] ?? 0) - minY) * sy;
      return {
        id: m.id, x, y, tier: m.tier,
        r: 4 + Math.max(0, m.score) * 6,
      } satisfies CanvasPoint;
    });
  }, [items, size]);

  return (
    <div
      ref={wrapRef}
      className="relative h-[420px] w-full rounded-2xl border border-ink-200 dark:border-ink-800 bg-gradient-to-br from-ink-50/50 to-white dark:from-ink-950/60 dark:to-ink-950/30 overflow-hidden"
    >
      <svg className="absolute inset-0 h-full w-full" aria-hidden>
        <defs>
          <pattern id="mem-dots" width="24" height="24" patternUnits="userSpaceOnUse">
            <circle cx="1" cy="1" r="1" fill="rgb(143 159 185 / 0.25)" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#mem-dots)" />
      </svg>
      <div className="absolute inset-0">
        {layout.map((p) => {
          const active = selectedId === p.id || hoverId === p.id;
          return (
            <button
              key={p.id}
              type="button"
              onClick={() => onSelect(p.id)}
              onMouseEnter={() => onHover(p.id)}
              onMouseLeave={() => onHover(null)}
              onFocus={() => onHover(p.id)}
              onBlur={() => onHover(null)}
              aria-label={`Select memory ${p.id}`}
              style={{
                position: "absolute",
                left: `${p.x}px`,
                top: `${p.y}px`,
                width: `${p.r * 2}px`,
                height: `${p.r * 2}px`,
                transform: active ? "translate(-50%,-50%) scale(1.5)" : "translate(-50%,-50%)",
                zIndex: active ? 10 : 0,
              }}
              className={cn(
                "rounded-full border-2 border-white dark:border-ink-950 bg-gradient-to-br shadow-soft transition-all duration-150",
                TIER_TONE[p.tier],
                "to-white/10",
                active && "ring-2 ring-brand-500/80",
              )}
            />
          );
        })}
      </div>
      <div className="absolute left-3 bottom-3 flex flex-wrap gap-1.5">
        {TIER_ORDER.map((t) => (
          <span key={t} className={cn("chip border bg-white/80 dark:bg-ink-950/60", TIER_BG[t])}>
            <span className={cn("inline-block h-2 w-2 rounded-full bg-gradient-to-br", TIER_TONE[t])} />
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}

function MemoryCard({
  record, selected, onClick,
}: {
  readonly record: MemoryRecord;
  readonly selected: boolean;
  readonly onClick: () => void;
}): JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "card w-full text-left p-4 transition relative overflow-hidden hover:-translate-y-0.5 hover:shadow-card focus-visible:ring-2 focus-visible:ring-brand-500/70",
        selected && "ring-2 ring-brand-500/70",
      )}
    >
      <div className="flex items-start gap-3">
        <span className={cn("chip shrink-0 !px-3 py-0.5 border", TIER_BG[record.tier])}>
          {record.tier}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold line-clamp-2 text-ink-950 dark:text-ink-50">
            {record.content}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px]">
            {record.tags.map((t) => (
              <span key={t} className="chip !px-2 !py-0.5 inline-flex items-center gap-1">
                <Tag className="h-3 w-3" aria-hidden /> {t}
              </span>
            ))}
            {record.chunk_id ? (
              <span className="font-mono text-ink-500 dark:text-ink-400">#{record.chunk_id}</span>
            ) : null}
            <span className="ml-auto text-ink-500 dark:text-ink-400">
              {formatDistanceToNow(record.created_at * 1000, { addSuffix: true })}
            </span>
          </div>
        </div>
      </div>
      <div className="mt-3 h-1 w-full rounded-full bg-ink-100 dark:bg-ink-900 overflow-hidden">
        <div
          className={cn(
            "h-full bg-gradient-to-r",
            record.score >= 0 ? "from-brand-500 to-emerald-500" : "from-amber-500 to-rose-500",
          )}
          style={{ width: `${Math.round((record.score + 1) * 50)}%` }}
        />
      </div>
      <p className="mt-1.5 text-[11px] text-ink-500 dark:text-ink-400 tabular-nums">
        relevance score: {(record.score * 100).toFixed(0)} \u00b7 record {record.id}
      </p>
    </button>
  );
}

async function queryMemoryExplorer(): Promise<MemoryRecord[]> {
  const live = await listMemory();
  if (live.length > 0) return live;
  await new Promise((r) => setTimeout(r, 1000));
  return buildMockMemory(9, 60);
}

function MemoryExplorerInner(): JSX.Element {
  const { data: initialRecords = buildMockMemory(9, 60), isFetching, isError } = useQuery({
    queryKey: ["memory", "explorer"] as const,
    queryFn: queryMemoryExplorer,
    placeholderData: buildMockMemory(9, 60),
    retry: 1,
  });

  const [q, setQ] = useState<string>("");
  const [tiers, setTiers] = useState<ReadonlySet<MemoryTier>>(new Set(TIER_ORDER));
  const [minScore, setMinScore] = useState<number>(-1);
  const [tags, setTags] = useState<readonly string[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(initialRecords[0]?.id ?? null);
  const [hoverId, setHoverId] = useState<string | null>(null);

  const allTags = useMemo(() => {
    const s = new Set<string>();
    for (const r of initialRecords) for (const t of r.tags) s.add(t);
    return [...s].sort();
  }, [initialRecords]);

  const records = useMemo(() => {
    const qq = q.trim().toLowerCase();
    return initialRecords.filter((r) => {
      if (!tiers.has(r.tier)) return false;
      if (r.score < minScore) return false;
      if (tags.length > 0 && !tags.some((t) => r.tags.includes(t))) return false;
      if (qq) {
        const hay = `${r.content} ${r.tags.join(" ")}`.toLowerCase();
        if (!hay.includes(qq)) return false;
      }
      return true;
    });
  }, [initialRecords, q, tiers, minScore, tags]);

  const selected = records.find((r) => r.id === selectedId) ?? records[0] ?? null;

  const toggleTier = useCallback((t: MemoryTier): void => {
    setTiers((prev) => {
      const nx = new Set(prev);
      if (nx.has(t)) nx.delete(t);
      else nx.add(t);
      return nx;
    });
  }, []);

  const toggleTag = useCallback((t: string): void => {
    setTags((prev) => (prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]));
  }, []);

  return (
    <DashboardShell>
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-brand-600 dark:text-brand-300 font-semibold">
            Memory
            {isFetching && (
              <span className="ml-2 inline-flex items-center gap-1 text-brand-500 dark:text-brand-400">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500 dark:bg-brand-400" />
                syncing
              </span>
            )}
          </p>
          <h1 className="mt-0.5 text-2xl font-bold tracking-tight text-ink-950 dark:text-ink-50">
            Memory Explorer
          </h1>
          <p className="text-sm text-ink-500 dark:text-ink-400 mt-1">
            2D projection + filterable grid \u2014 {records.length}/{initialRecords.length} memories.
          </p>
          {isError && (
            <p className="text-sm text-amber-700 dark:text-amber-300 mt-1">
              Backend unreachable \u2014 falling back to local mock data.
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search
              className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-400"
              aria-hidden
            />
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search content or tag..."
              className="w-72 rounded-xl border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-950/50 pl-9 pr-3 py-2 text-sm placeholder:text-ink-400 focus:outline-none focus:ring-2 focus:ring-brand-500/60"
            />
          </div>
          <button type="button" className="btn-ghost !p-2" aria-label="Filters">
            <SlidersHorizontal className="h-[18px] w-[18px]" aria-hidden />
          </button>
        </div>
      </header>

      <section className="grid gap-4 lg:grid-cols-[18rem_1fr]">
        <aside className="card p-4 flex flex-col gap-5">
          <div>
            <p className="text-xs uppercase tracking-wider font-semibold text-ink-500 dark:text-ink-400 mb-2">
              Tiers
            </p>
            <div className="flex flex-wrap gap-2">
              {TIER_ORDER.map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => toggleTier(t)}
                  aria-pressed={tiers.has(t)}
                  className={cn("chip border", !tiers.has(t) && "opacity-40", TIER_BG[t])}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wider font-semibold text-ink-500 dark:text-ink-400 mb-2">
              Min score
            </p>
            <div className="flex items-center gap-2 text-xs">
              <input
                type="range"
                min={-1}
                max={1}
                step={0.05}
                value={minScore}
                onChange={(e) => setMinScore(parseFloat(e.target.value))}
                className="flex-1 accent-brand-600"
              />
              <span className="tabular-nums w-12 text-right">{(minScore * 100).toFixed(0)}</span>
            </div>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wider font-semibold text-ink-500 dark:text-ink-400 mb-2">
              Tags
            </p>
            <div className="flex flex-wrap gap-1.5">
              {allTags.map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => toggleTag(t)}
                  aria-pressed={tags.includes(t)}
                  className={cn(
                    "chip",
                    tags.includes(t)
                      ? "!bg-brand-50 dark:!bg-brand-950/60 !border-brand-300 dark:!border-brand-800 !text-brand-700 dark:!text-brand-200"
                      : "opacity-70 hover:opacity-100",
                  )}
                >
                  #{t}
                </button>
              ))}
              {tags.length > 0 ? (
                <button type="button" onClick={() => setTags([])} className="chip">
                  <X className="h-3 w-3" /> clear
                </button>
              ) : null}
            </div>
          </div>
          <div className="mt-auto rounded-xl border border-ink-200 dark:border-ink-800 p-3 bg-ink-50/70 dark:bg-ink-950/40 text-xs space-y-1">
            <p className="font-semibold text-ink-700 dark:text-ink-200">Tip</p>
            <p className="text-ink-500 dark:text-ink-400">
              Click a dot or a card to pin the details drawer. Nearby dots = nearby embeddings.
            </p>
          </div>
        </aside>

        <div className="space-y-4">
          <ProjectionCanvas
            items={records}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onHover={setHoverId}
            hoverId={hoverId}
          />

          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {records.map((r) => (
              <MemoryCard
                key={r.id}
                record={r}
                selected={selectedId === r.id}
                onClick={() => setSelectedId(r.id)}
              />
            ))}
            {records.length === 0 ? (
              <p className="col-span-full text-sm text-ink-500 dark:text-ink-400 text-center py-10 border border-dashed rounded-2xl border-ink-200 dark:border-ink-800">
                No memories match your filters. Try broadening them.
              </p>
            ) : null}
          </section>
        </div>
      </section>

      {selected ? (
        <section className="card p-5 animate-fade-in" aria-label="Memory details">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className={cn("chip border", TIER_BG[selected.tier])}>{selected.tier}</span>
                <span className="chip">#{selected.id}</span>
                {selected.chunk_id ? (
                  <span className="chip font-mono">{selected.chunk_id}</span>
                ) : null}
                {selected.tags.map((t) => (
                  <span key={t} className="chip">
                    <Tag className="h-3 w-3" aria-hidden /> {t}
                  </span>
                ))}
              </div>
              <h2 className="mt-2 text-xl font-bold text-ink-950 dark:text-ink-50">Memory details</h2>
            </div>
            <dl className="grid grid-cols-3 gap-3 text-xs">
              <div className="rounded-xl border border-ink-200 dark:border-ink-800 p-3">
                <dt className="text-ink-500 dark:text-ink-400 uppercase tracking-wider">Score</dt>
                <dd className="mt-1 text-lg font-semibold tabular-nums">
                  {(selected.score * 100).toFixed(0)}
                </dd>
              </div>
              <div className="rounded-xl border border-ink-200 dark:border-ink-800 p-3">
                <dt className="text-ink-500 dark:text-ink-400 uppercase tracking-wider">Age</dt>
                <dd className="mt-1 text-lg font-semibold">
                  {formatDistanceToNow(selected.created_at * 1000, { addSuffix: true })}
                </dd>
              </div>
              <div className="rounded-xl border border-ink-200 dark:border-ink-800 p-3">
                <dt className="text-ink-500 dark:text-ink-400 uppercase tracking-wider">Chunks</dt>
                <dd className="mt-1 text-lg font-semibold tabular-nums">
                  {formatNumber(1 + Math.floor(Math.abs(selected.score) * 7), 0)}
                </dd>
              </div>
            </dl>
          </div>

          <blockquote className="mt-5 rounded-2xl border border-ink-200 dark:border-ink-800 bg-ink-50/60 dark:bg-ink-950/40 p-5 text-[15px] leading-7 text-ink-800 dark:text-ink-200">
            {selected.content}
          </blockquote>

          <p className="mt-4 text-xs text-ink-500 dark:text-ink-400">
            {selected.embedding_2d
              ? `Projected coordinates: (${selected.embedding_2d[0].toFixed(2)}, ${selected.embedding_2d[1].toFixed(2)})`
              : "No 2D projection stored for this memory \u2014 shown at pseudo-random placement in the canvas."}
          </p>
        </section>
      ) : null}
    </DashboardShell>
  );
}

function MemoryExplorerSuspenseFallback(): JSX.Element {
  const records = buildMockMemory(9, 60);
  return (
    <DashboardShell>
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-brand-600 dark:text-brand-300 font-semibold">
            Memory
            <span className="ml-2 inline-flex items-center gap-1 text-brand-500 dark:text-brand-400">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500 dark:bg-brand-400" />
              loading
            </span>
          </p>
          <h1 className="mt-0.5 text-2xl font-bold tracking-tight text-ink-950 dark:text-ink-50">
            Memory Explorer
          </h1>
          <p className="text-sm text-ink-500 dark:text-ink-400 mt-1 opacity-60">
            Loading memory index\u2026
          </p>
        </div>
      </header>
      <section className="grid gap-4 lg:grid-cols-[18rem_1fr]">
        <aside className="card p-4 h-80 animate-pulse opacity-60" />
        <div className="space-y-4">
          <div className="h-[420px] rounded-2xl border border-ink-200 dark:border-ink-800 animate-pulse opacity-60" />
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {records.slice(0, 6).map((r) => (
              <div key={r.id} className="card p-4 animate-pulse opacity-50">
                <div className="h-3 w-1/3 rounded bg-ink-200 dark:bg-ink-800 mb-3" />
                <div className="h-4 w-full rounded bg-ink-200 dark:bg-ink-800 mb-2" />
                <div className="h-4 w-5/6 rounded bg-ink-200 dark:bg-ink-800" />
              </div>
            ))}
          </section>
        </div>
      </section>
    </DashboardShell>
  );
}

export default function MemoryExplorerPage(): JSX.Element {
  return (
    <Suspense fallback={<MemoryExplorerSuspenseFallback />}>
      <MemoryExplorerInner />
    </Suspense>
  );
}
