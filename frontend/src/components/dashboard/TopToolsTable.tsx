"use client";

import type { JSX } from "react";

import type { ObservabilitySummary } from "@/lib/schemas";
import { cn, formatCurrencyUSD, formatDurationMs, formatNumber } from "@/lib/format";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

export function TopToolsTable({ summary }: { readonly summary: ObservabilitySummary }): JSX.Element {
  const rows = [...summary.tools].sort((a, b) => b.invocations - a.invocations);
  const maxCalls = rows[0]?.invocations ?? 1;

  return (
    <section className="card p-5 flex flex-col gap-4">
      <header className="flex items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-ink-950 dark:text-ink-50">Top tools</h2>
          <p className="text-sm text-ink-500 dark:text-ink-400">Invocations, error rate, and latency p95.</p>
        </div>
        <Link
          href="/metrics"
          className="btn-ghost text-xs"
          aria-label="See full observability dashboard"
        >
          Metrics <ArrowUpRight className="h-3.5 w-3.5" />
        </Link>
      </header>

      <div className="overflow-hidden rounded-xl border border-ink-200 dark:border-ink-800">
        <table className="w-full min-w-[560px] border-collapse text-sm">
          <thead>
            <tr className="bg-ink-50 dark:bg-ink-950/40 text-left text-xs uppercase tracking-wider font-semibold text-ink-500 dark:text-ink-400">
              <th scope="col" className="px-4 py-2.5">Tool</th>
              <th scope="col" className="px-4 py-2.5">Calls</th>
              <th scope="col" className="px-4 py-2.5">Errors</th>
              <th scope="col" className="px-4 py-2.5">Avg</th>
              <th scope="col" className="px-4 py-2.5">p95</th>
              <th scope="col" className="px-4 py-2.5 w-40">Share</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t, i) => {
              const errPct = t.invocations ? (t.errors * 100) / t.invocations : 0;
              const hot = errPct > 3;
              return (
                <tr key={t.tool_name} className={cn(i !== rows.length - 1 && "border-t border-ink-200/70 dark:border-ink-800/70")}>
                  <td className="px-4 py-3">
                    <span className="font-semibold text-ink-900 dark:text-ink-100 font-mono text-[13px]">{t.tool_name}</span>
                  </td>
                  <td className="px-4 py-3 tabular-nums">{formatNumber(t.invocations, 0)}</td>
                  <td className={cn("px-4 py-3 tabular-nums", hot ? "text-rose-600 dark:text-rose-300 font-semibold" : "")}>
                    {formatNumber(t.errors, 0)} <span className="text-ink-400 text-xs">({errPct.toFixed(1)}%)</span>
                  </td>
                  <td className="px-4 py-3 tabular-nums text-ink-600 dark:text-ink-300">{formatDurationMs(t.avg_ms)}</td>
                  <td className="px-4 py-3 tabular-nums">{formatDurationMs(t.p95_ms)}</td>
                  <td className="px-4 py-3">
                    <div className="h-2 w-full rounded-full bg-ink-100 dark:bg-ink-900 overflow-hidden">
                      <div
                        className={cn(
                          "h-full rounded-full bg-gradient-to-r from-brand-400 to-brand-600",
                          hot && "from-amber-400 to-rose-500",
                        )}
                        style={{ width: `${Math.max(3, (t.invocations / maxCalls) * 100).toFixed(1)}%` }}
                      />
                    </div>
                  </td>
                </tr>
              );
            })}
            {rows.length === 0 ? (
              <tr>
                <td className="px-4 py-10 text-center text-sm text-ink-500" colSpan={6}>
                  No tool invocations yet. Try running an agent on the <Link className="underline text-brand-600 dark:text-brand-300" href="/agents">Agents page</Link>.
                </td>
              </tr>
            ) : null}
          </tbody>
          <tfoot>
            <tr className="border-t border-ink-200 dark:border-ink-800 bg-ink-50/70 dark:bg-ink-950/40 text-xs font-semibold">
              <td className="px-4 py-2.5 text-ink-700 dark:text-ink-300">Totals</td>
              <td className="px-4 py-2.5 tabular-nums">
                {formatNumber(rows.reduce((a, r) => a + r.invocations, 0), 0)}
              </td>
              <td className="px-4 py-2.5 tabular-nums">
                {formatNumber(rows.reduce((a, r) => a + r.errors, 0), 0)}
              </td>
              <td className="px-4 py-2.5 tabular-nums text-ink-600" colSpan={2}>
                {formatCurrencyUSD(summary.total_cost_usd)} cumulative cost
              </td>
              <td className="px-4 py-2.5" />
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}
