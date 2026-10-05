"use client";

import { Suspense, useState } from "react";
import type React from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  Copy,
  Cpu,
  Play,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

import { DashboardShell } from "@/components/layout/DashboardShell";
import { Badge } from "@/components/ui/Badge";
import { type LlmBenchmarkEnvelope, type LlmBenchmarkTristate, runLlmBenchmark } from "@/lib/api/bench";
import { cn, formatDurationMs } from "@/lib/format";

const MODE_OPTIONS: { readonly value: "seeded" | "adaptive"; readonly label: string }[] = [
  { value: "seeded", label: "Seeded (deterministic)" },
  { value: "adaptive", label: "Adaptive (replan loop)" },
] as const;

const MODEL_OPTIONS: { readonly value: "qwen2.5-coder:7b" | "deepseek-coder-v2:16b"; readonly label: string }[] = [
  { value: "qwen2.5-coder:7b", label: "qwen2.5-coder:7b" },
  { value: "deepseek-coder-v2:16b", label: "deepseek-coder-v2:16b" },
] as const;

function tristateBadge(t: LlmBenchmarkTristate): React.JSX.Element {
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
      return <Badge variant="amber" className="gap-1"><Clock3 className="h-3 w-3" /> replan</Badge>;
  }
}

function tristateTone(t: LlmBenchmarkTristate): "emerald" | "rose" | "amber" {
  switch (t) {
    case "signoff":
      return "emerald";
    case "reject":
      return "rose";
    default:
      return "amber";
  }
}

interface ResultCardProps {
  readonly envelope: LlmBenchmarkEnvelope;
}

function ResultCard({ envelope }: ResultCardProps): React.JSX.Element {
  const { data, demo, source } = envelope;
  const tone = tristateTone(data.tristate);
  const pct = (n: number, digits = 1): string => `${(n * 100).toFixed(digits)}%`;

  return (
    <section
      className={cn(
        "card p-5 animate-fade-in border-2",
        tone === "emerald" && "border-emerald-300/60 dark:border-emerald-800/60 ring-1 ring-emerald-500/15",
        tone === "rose" && "border-rose-300/60 dark:border-rose-800/60 ring-1 ring-rose-500/15",
        tone === "amber" && "border-amber-300/60 dark:border-amber-800/60 ring-1 ring-amber-500/15",
      )}
      aria-label="Benchmark result"
    >
      {demo ? (
        <div
          role="status"
          className="mb-4 rounded-xl border border-amber-200 dark:border-amber-900/40 bg-amber-50/70 dark:bg-amber-950/20 px-3 py-2 flex items-start gap-2"
        >
          <AlertCircle className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-semibold text-amber-800 dark:text-amber-200">
              Mock / offline result
            </p>
            <p className="text-[10px] text-amber-700/80 dark:text-amber-300/70 font-mono truncate" title={source}>
              {source}
            </p>
          </div>
        </div>
      ) : (
        <div className="mb-4 rounded-xl border border-emerald-200 dark:border-emerald-900/40 bg-emerald-50/70 dark:bg-emerald-950/20 px-3 py-2 flex items-start gap-2">
          <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-semibold text-emerald-800 dark:text-emerald-200">
              Live backend run
            </p>
            <p className="text-[10px] text-emerald-700/80 dark:text-emerald-300/70 font-mono truncate" title={source}>
              {source}
            </p>
          </div>
        </div>
      )}

      <header className="flex items-start justify-between gap-3 mb-4 flex-wrap">
        <div>
          <h3 className="text-sm font-semibold text-ink-950 dark:text-ink-50 flex items-center gap-2">
            <Cpu className="h-4 w-4 text-brand-600 dark:text-brand-300" />
            Run outcome for <code className="font-mono text-[12px] bg-ink-100 dark:bg-ink-900/60 px-1.5 py-0.5 rounded-md">{data.task_id}</code>
          </h3>
          <p className="text-xs text-ink-500 dark:text-ink-400 mt-0.5">
            mode={data.mode} · model={data.model}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {tristateBadge(data.tristate)}
        </div>
      </header>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-xl border border-ink-200 dark:border-ink-800 p-3">
          <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500 dark:text-ink-400 font-semibold">
            Duration
          </p>
          <p className="mt-1 text-xl font-bold tabular-nums text-ink-900 dark:text-ink-100">
            {formatDurationMs(data.duration_ms)}
          </p>
          <p className="text-[10px] text-ink-500 dark:text-ink-400 mt-0.5">
            End-to-end wall-clock
          </p>
        </div>

        <div className="rounded-xl border border-ink-200 dark:border-ink-800 p-3">
          <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500 dark:text-ink-400 font-semibold">
            Kriyakārī conf
          </p>
          <p className="mt-1 text-xl font-bold tabular-nums text-brand-700 dark:text-brand-200">
            {pct(data.kriyakari_conf, 1)}
          </p>
          <div className="mt-2 h-1.5 w-full rounded-full bg-ink-100 dark:bg-ink-900 overflow-hidden">
            <div
              className={cn(
                "h-full rounded-full",
                data.kriyakari_conf >= 0.7
                  ? "bg-gradient-to-r from-emerald-500 to-emerald-400"
                  : data.kriyakari_conf >= 0.4
                    ? "bg-gradient-to-r from-amber-500 to-amber-400"
                    : "bg-gradient-to-r from-rose-500 to-rose-400",
              )}
              style={{ width: `${Math.max(2, data.kriyakari_conf * 100)}%` }}
            />
          </div>
          <p className="text-[10px] text-ink-500 dark:text-ink-400 mt-1.5">
            MAC sign-off confidence
          </p>
        </div>

        <div className="rounded-xl border border-ink-200 dark:border-ink-800 p-3 sm:col-span-2 lg:col-span-1">
          <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500 dark:text-ink-400 font-semibold">
            Plan SHA
          </p>
          <div className="mt-1 flex items-center gap-2 min-w-0">
            <code className="font-mono text-[11px] text-ink-700 dark:text-ink-200 truncate bg-ink-100 dark:bg-ink-900/60 px-2 py-1 rounded-md flex-1 min-w-0">
              {data.plan_sha}
            </code>
            <button
              type="button"
              onClick={() => { void navigator.clipboard.writeText(data.plan_sha); }}
              className="p-1.5 rounded-lg hover:bg-ink-100 dark:hover:bg-ink-800 text-ink-500 hover:text-ink-800 dark:hover:text-ink-100 transition shrink-0"
              aria-label="Copy plan SHA"
              title="Copy full plan SHA"
            >
              <Copy className="h-3.5 w-3.5" />
            </button>
          </div>
          <p className="text-[10px] text-ink-500 dark:text-ink-400 mt-2">
            Deterministic execution fingerprint
          </p>
        </div>
      </div>

      <div className="mt-4">
        <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500 dark:text-ink-400 font-semibold mb-1.5">
          Sign-off reason
        </p>
        <p className="text-sm text-ink-700 dark:text-ink-200 leading-relaxed rounded-lg border border-ink-200 dark:border-ink-800 bg-ink-50/60 dark:bg-ink-900/30 px-3 py-2">
          {data.signoff_reason}
        </p>
      </div>
    </section>
  );
}

function BenchmarkRunnerInner(): React.JSX.Element {
  const [taskId, setTaskId] = useState("");
  const [mode, setMode] = useState<"seeded" | "adaptive">("seeded");
  const [model, setModel] = useState<"qwen2.5-coder:7b" | "deepseek-coder-v2:16b">("qwen2.5-coder:7b");
  const [lastResult, setLastResult] = useState<LlmBenchmarkEnvelope | null>(null);
  const [isPending, setIsPending] = useState(false);

  const onSubmit = async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    if (!taskId.trim() || isPending) return;
    setIsPending(true);
    try {
      const res = await runLlmBenchmark({ task_id: taskId.trim(), mode, model });
      setLastResult(res);
      toast.success(`Benchmark done · ${res.data.tristate} · Kriyakārī ${(res.data.kriyakari_conf * 100).toFixed(0)}%`, {
        description: `task_id ${taskId} · ${Math.round(res.data.duration_ms)}ms`,
        position: "top-right",
        duration: 5000,
      });
    } catch (err) {
      toast.error(`Benchmark failed: ${(err as Error).message}`, {
        position: "top-right",
        duration: 7000,
      });
    } finally {
      setIsPending(false);
    }
  };

  return (
    <DashboardShell>
      <header className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-brand-600 dark:text-brand-300 font-semibold">
            P10 · Live Benchmark Runner
          </p>
          <h1 className="text-2xl font-bold tracking-tight text-ink-950 dark:text-ink-50">
            Bench Runner — ad-hoc SE50 task evaluation against live Ollama models.
          </h1>
          <p className="mt-1 text-sm text-ink-500 dark:text-ink-400">
            Pick a task, choose seeded vs adaptive replan mode, select model, fire.  Kriyakārī MAC loop
            reports tristate + confidence + deterministic plan_sha.
          </p>
        </div>
        <div className="mt-4 sm:mt-0 flex items-center gap-2 flex-wrap">
          {isPending ? (
            <span className="chip !border-brand-300 dark:!border-brand-800 !bg-brand-50 dark:!bg-brand-950/40 !text-brand-700 dark:!text-brand-200">
              <Clock3 className="h-3 w-3 animate-spin" /> Running benchmark…
            </span>
          ) : null}
          {lastResult && !isPending ? (
            <span className="chip">{formatDurationMs(lastResult.data.duration_ms)} last run</span>
          ) : null}
        </div>
      </header>

      <section className="card p-5 animate-fade-in" aria-label="Benchmark form">
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <h2 className="text-sm font-semibold text-ink-950 dark:text-ink-50 flex items-center gap-2">
              <Cpu className="h-4 w-4 text-brand-600 dark:text-brand-300" />
              Run configuration
            </h2>
            <p className="text-xs text-ink-500 dark:text-ink-400 mt-0.5">
              Form submits GET /llm/benchmark with capability token on localhost origins.
            </p>
          </div>
        </div>

        <form
          onSubmit={(e) => { void onSubmit(e); }}
          className="grid gap-3 sm:grid-cols-[1fr_auto_auto_auto] sm:items-end"
          data-testid="bench-runner-form"
        >
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-ink-600 dark:text-ink-300">
              SE50 Task ID
            </span>
            <input
              type="text"
              value={taskId}
              onChange={(e) => setTaskId(e.target.value)}
              placeholder="e.g. SE50-001 or dataclasses_cfg_parser"
              className="rounded-xl border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-950/50 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/60 font-mono"
              required
              data-testid="task-id-input"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-ink-600 dark:text-ink-300">Mode</span>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as "seeded" | "adaptive")}
              className="rounded-xl border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-950/50 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/60"
              data-testid="mode-select"
            >
              {MODE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-ink-600 dark:text-ink-300">Ollama model</span>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value as "qwen2.5-coder:7b" | "deepseek-coder-v2:16b")}
              className="rounded-xl border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-950/50 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/60"
              data-testid="model-select"
            >
              {MODEL_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </label>

          <button
            type="submit"
            className="btn-primary transition-all duration-200 ease-out hover:bg-brand-600 hover:shadow-md active:scale-[0.98] active:shadow-inner"
            disabled={isPending || !taskId.trim()}
            data-testid="run-button"
          >
            <Play className="h-4 w-4" />
            {isPending ? "Running…" : "Run"}
          </button>
        </form>
      </section>

      {lastResult ? <ResultCard envelope={lastResult} /> : null}
    </DashboardShell>
  );
}

function BenchmarkRunnerSuspenseFallback(): React.JSX.Element {
  return (
    <DashboardShell>
      <header className="flex flex-col gap-1">
        <p className="text-xs uppercase tracking-[0.18em] text-brand-600 dark:text-brand-300 font-semibold">
          P10 · Live Benchmark Runner
          <span className="ml-2 inline-flex items-center gap-1 text-brand-500 dark:text-brand-400">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500 dark:bg-brand-400" />
            loading
          </span>
        </p>
        <h1 className="text-2xl font-bold tracking-tight text-ink-950 dark:text-ink-50">
          Bench Runner — ad-hoc SE50 task evaluation against live Ollama models.
        </h1>
      </header>
      <section className="card p-5 animate-pulse opacity-60">
        <div className="h-10 w-full rounded-xl bg-ink-200 dark:bg-ink-800 mb-3" />
        <div className="h-10 w-full rounded-xl bg-ink-200 dark:bg-ink-800" />
      </section>
    </DashboardShell>
  );
}

export default function BenchmarkRunnerPage(): React.JSX.Element {
  return (
    <Suspense fallback={<BenchmarkRunnerSuspenseFallback />}>
      <BenchmarkRunnerInner />
    </Suspense>
  );
}
