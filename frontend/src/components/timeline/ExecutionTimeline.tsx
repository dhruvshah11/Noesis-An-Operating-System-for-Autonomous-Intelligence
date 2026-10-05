"use client";

import { Check, ChevronRight, CircleDashed, CircleDot, CircleSlash2, CircleX, Copy, Terminal } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import Link from "next/link";
import type { JSX } from "react";

import type { ExecutionTrace, PlanStep, ToolCall } from "@/lib/schemas";
import { cn, formatDurationMs } from "@/lib/format";
import { useState } from "react";

export type StatusPillColor = "success" | "failed" | "running" | "pending" | "skipped";
export const STATUS_PILL: Record<StatusPillColor, string> = {
  success: "!border-emerald-300 !bg-emerald-50 dark:!border-emerald-800 dark:!bg-emerald-950/40 !text-emerald-700 dark:!text-emerald-200",
  failed: "!border-rose-300 !bg-rose-50 dark:!border-rose-800 dark:!bg-rose-950/40 !text-rose-700 dark:!text-rose-200",
  running: "!border-brand-300 !bg-brand-50 dark:!border-brand-800 dark:!bg-brand-950/40 !text-brand-700 dark:!text-brand-200",
  pending: "!border-ink-200 !bg-ink-50 dark:!border-ink-800 dark:!bg-ink-950/40 !text-ink-600 dark:!text-ink-300",
  skipped: "!border-ink-200 !bg-ink-50 dark:!border-ink-800 dark:!bg-ink-950/40 !text-ink-500 dark:!text-ink-400 italic",
};

function StatusIcon({ status }: { readonly status: PlanStep["status"] }): JSX.Element {
  const cls =
    status === "success"
      ? "text-emerald-500"
      : status === "failed"
        ? "text-rose-500"
        : status === "running"
          ? "text-brand-500 animate-pulse"
          : status === "skipped"
            ? "text-ink-400"
            : "text-ink-300";
  switch (status) {
    case "success":
      return <CircleDot className={cn("h-4 w-4", cls)} aria-hidden />;
    case "failed":
      return <CircleX className={cn("h-4 w-4", cls)} aria-hidden />;
    case "running":
      return <CircleDashed className={cn("h-4 w-4", cls)} aria-hidden />;
    case "skipped":
      return <CircleSlash2 className={cn("h-4 w-4", cls)} aria-hidden />;
    default:
      return <CircleDashed className={cn("h-4 w-4", cls)} aria-hidden />;
  }
}

export function StatusPill({ status, label }: { readonly status: StatusPillColor; readonly label?: string }): JSX.Element {
  const t = label ?? status.toUpperCase();
  return <span className={cn("chip", STATUS_PILL[status])}>{t}</span>;
}

function ToolRow({ call }: { readonly call: ToolCall }): JSX.Element {
  const dur = call.ended_at != null ? (call.ended_at - call.started_at) * 1000 : undefined;
  const statusCol: StatusPillColor =
    call.success == null ? "running" : call.success ? "success" : "failed";
  const [stdoutCopied, setStdoutCopied] = useState(false);

  const copyStdout = async (): Promise<void> => {
    try {
      await navigator.clipboard.writeText(call.stdout_snippet ?? "");
      setStdoutCopied(true);
      setTimeout(() => setStdoutCopied(false), 2000);
    } catch {
      setStdoutCopied(false);
    }
  };

  return (
    <li className="flex items-start gap-3 rounded-xl border border-ink-200/60 dark:border-ink-800/60 bg-ink-50/60 dark:bg-ink-950/40 p-3">
      <div className="grid h-8 w-8 place-items-center rounded-lg bg-ink-100 dark:bg-ink-900 text-ink-700 dark:text-ink-200">
        <Terminal className="h-4 w-4" aria-hidden />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <code className="rounded-md bg-white dark:bg-ink-900 border border-ink-200 dark:border-ink-800 px-1.5 py-0.5 text-xs font-mono text-ink-700 dark:text-ink-200">
            {call.name}
          </code>
          <StatusPill status={statusCol} />
          {dur != null ? <span className="text-xs text-ink-500">{formatDurationMs(dur)}</span> : null}
          {call.exit_code != null ? (
            <span className="text-xs font-mono text-ink-500 dark:text-ink-400">exit {call.exit_code}</span>
          ) : null}
        </div>
        <p className="mt-1 text-xs text-ink-500 dark:text-ink-400 font-mono truncate">
          args: {JSON.stringify(call.args)}
        </p>
        {call.stdout_snippet ? (
          <div className="relative group mt-2">
            <pre className="rounded-lg bg-ink-950 dark:bg-black/60 text-ink-100 text-[11px] leading-5 font-mono p-2.5 pr-10 overflow-x-auto whitespace-pre-wrap">
              {call.stdout_snippet}
            </pre>
            <button
              type="button"
              onClick={() => { void copyStdout(); }}
              className="absolute top-2 right-2 h-7 w-7 grid place-items-center rounded-md bg-ink-800/70 hover:bg-ink-700 border border-ink-700 text-ink-200 opacity-0 group-hover:opacity-100 transition-opacity"
              aria-label={stdoutCopied ? "Copied!" : "Copy stdout"}
            >
              {stdoutCopied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
            </button>
          </div>
        ) : null}
      </div>
    </li>
  );
}

function StepRow({ step, index }: { readonly step: PlanStep; readonly index: number }): JSX.Element {
  const [open, setOpen] = useState<boolean>(step.tool_calls.length > 0 && step.status === "failed");
  const hasTools = step.tool_calls.length > 0;
  const dur =
    step.ended_at != null && step.started_at != null ? (step.ended_at - step.started_at) * 1000 : undefined;

  return (
    <li>
      <button
        type="button"
        onClick={() => hasTools && setOpen((v) => !v)}
        disabled={!hasTools}
        className={cn(
          "group w-full flex items-start gap-3 rounded-xl p-3 text-left transition",
          hasTools ? "hover:bg-ink-100/70 dark:hover:bg-ink-900/50 cursor-pointer" : "cursor-default",
        )}
        aria-expanded={hasTools ? open : undefined}
      >
        <div className="pt-0.5">
          <StatusIcon status={step.status} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-mono text-ink-400 dark:text-ink-500 w-6">S{index}</span>
            <p className="text-sm font-semibold text-ink-900 dark:text-ink-100 truncate">{step.description}</p>
            <StatusPill status={step.status} label={step.status} />
            {step.confidence != null ? (
              <span className="chip" title="Agent confidence">
                conf {(step.confidence * 100).toFixed(0)}%
              </span>
            ) : null}
            {dur != null ? <span className="text-xs text-ink-500">{formatDurationMs(dur)}</span> : null}
          </div>
          <p className="mt-0.5 text-xs text-ink-500 dark:text-ink-400 truncate">
            agent: <span className="font-mono text-ink-700 dark:text-ink-200">{step.assigned_agent}</span>
            {step.depends_on.length > 0 ? ` · depends on: ${step.depends_on.map((i) => `S${i}`).join(", ")}` : ""}
          </p>
        </div>
        {hasTools ? <ChevronRight className={cn("h-4 w-4 text-ink-400 transition-transform", open && "rotate-90")} aria-hidden /> : null}
      </button>
      {open ? (
        <ul className="ml-10 mt-1 space-y-2">
          {step.tool_calls.map((tc) => (
            <ToolRow key={tc.id} call={tc} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

export function ExecutionTimeline({
  traces,
  title = "Execution timeline",
  compact = false,
}: {
  readonly traces: readonly ExecutionTrace[];
  readonly title?: string;
  readonly compact?: boolean;
}): JSX.Element {
  const [traceId, setTraceId] = useState<string | undefined>(traces[0]?.trace_id);
  const active = traces.find((t) => t.trace_id === traceId) ?? traces[0];

  return (
    <section className="card p-5 flex flex-col gap-4" aria-label={title}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-ink-950 dark:text-ink-50">{title}</h2>
          <p className="text-sm text-ink-500 dark:text-ink-400">
            {active ? `${active.plan_steps.length} steps · ${active.plan_steps.reduce((a, s) => a + s.tool_calls.length, 0)} tool calls` : "Select a trace"}
          </p>
        </div>
        <div className="flex items-center gap-2 overflow-x-auto max-w-full">
          {traces.map((t, idx) => (
            <button
              key={t.trace_id}
              type="button"
              onClick={() => setTraceId(t.trace_id)}
              className={cn(
                "btn text-left shrink-0 !py-1.5 !px-3 !text-xs",
                traceId === t.trace_id ? "bg-brand-600 text-white hover:bg-brand-700 shadow-soft" : "bg-white dark:bg-ink-900 border border-ink-200 dark:border-ink-800 hover:bg-ink-50 dark:hover:bg-ink-900/70",
              )}
              aria-current={traceId === t.trace_id ? "true" : undefined}
            >
              <p className="font-semibold line-clamp-1 max-w-[24ch]">#{1000 + idx} · {t.user_query.slice(0, 42)}{t.user_query.length > 42 ? "…" : ""}</p>
              <p className="text-[10px] font-medium opacity-80">
                {formatDistanceToNow(t.created_at * 1000, { addSuffix: true })}
              </p>
            </button>
          ))}
        </div>
      </div>

      {active ? (
        <div className={cn("grid gap-5", compact ? "" : "lg:grid-cols-[14rem_1fr]")}>
          <div className="card border-ink-200 dark:border-ink-800 p-3 flex flex-col gap-2 bg-ink-50/60 dark:bg-ink-950/40 shadow-none">
            <p className="px-2 pt-1 text-xs uppercase tracking-wider font-semibold text-ink-500 dark:text-ink-400">
              Query
            </p>
            <p className="px-2 text-sm font-semibold text-ink-900 dark:text-ink-100">{active.user_query}</p>
            <div className="mt-1 px-2 flex flex-wrap gap-2">
              <StatusPill status={active.status} />
              <Link className="ml-auto text-xs font-medium text-brand-700 dark:text-brand-300 hover:underline" href="/timeline">
                Full trace →
              </Link>
            </div>
          </div>
          <ol className="space-y-1">
            {active.plan_steps.map((s, i) => (
              <StepRow key={`${active.trace_id}-${s.index}`} step={s} index={i} />
            ))}
          </ol>
        </div>
      ) : null}
    </section>
  );
}

export function MiniTimeline({ traces }: { readonly traces: readonly ExecutionTrace[] }): JSX.Element {
  return <ExecutionTimeline traces={traces} title="Latest agent runs" compact />;
}
