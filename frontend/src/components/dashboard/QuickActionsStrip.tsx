"use client";

import { FilePlus, MessageSquarePlus, Rocket, Sparkles, SquareTerminal, Wand2 } from "lucide-react";
import Link from "next/link";
import type { ComponentType, SVGProps } from "react";

import { cn } from "@/lib/format";
import { Tooltip } from "@/components/ui/Tooltip";

interface Action {
  readonly label: string;
  readonly hint: string;
  readonly href: string;
  readonly tooltip: string;
  readonly Icon: ComponentType<SVGProps<SVGSVGElement>>;
  readonly accent: "brand" | "ink" | "emerald" | "amber";
}

const ACTIONS: readonly Action[] = [
  { label: "New conversation", hint: "Start an autonomous agent run", href: "/conversations/new", tooltip: "Create a new multi-agent chat session", Icon: MessageSquarePlus, accent: "brand" },
  { label: "Agent playground", hint: "Test planner / reflection directly", href: "/agents", tooltip: "Launch agent workbench with 12 Sanskrit codenames", Icon: Rocket, accent: "emerald" },
  { label: "Upload document", hint: "PDF, MD, DOCX, CSV, HTML", href: "/documents/upload", tooltip: "Index documents for hybrid RAG retrieval", Icon: FilePlus, accent: "ink" },
  { label: "Query memory", hint: "Semantic search across 6 tiers", href: "/memory?q=okr", tooltip: "BM25 + dense vector search across Gy\u0101n tiers", Icon: Sparkles, accent: "amber" },
  { label: "Quick shell", hint: "Sandboxed shell tool (capability gated)", href: "/agents?tab=tools", tooltip: "Capability-gated shell with full audit trail", Icon: SquareTerminal, accent: "ink" },
  { label: "Generate patch", hint: "CodingAgent: edit + test + commit", href: "/agents?tab=coding", tooltip: "Vidya agent: test-first implementation pipeline", Icon: Wand2, accent: "brand" },
] as const;

const accentStyles: Record<Action["accent"], string> = {
  brand: "from-brand-500/15 to-transparent text-brand-700 dark:text-brand-200",
  ink: "from-ink-500/15 to-transparent text-ink-700 dark:text-ink-200",
  emerald: "from-emerald-500/15 to-transparent text-emerald-700 dark:text-emerald-200",
  amber: "from-amber-500/15 to-transparent text-amber-700 dark:text-amber-200",
};

export function QuickActionsStrip(): JSX.Element {
  return (
    <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6 gap-3" aria-label="Quick actions">
      {ACTIONS.map((a) => (
        <Tooltip key={a.label} content={a.tooltip} side="top" gradient>
          <Link
            href={a.href}
            className="group relative card p-4 overflow-hidden transition hover:shadow-card hover:-translate-y-0.5 focus-visible:ring-2 focus-visible:ring-brand-500/70 block w-full"
          >
            <div
              aria-hidden
              className={cn("pointer-events-none absolute -top-6 -right-6 h-24 w-24 rounded-full bg-gradient-to-br opacity-70 blur-xl", accentStyles[a.accent])}
            />
            <div className={cn("inline-flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br", accentStyles[a.accent])}>
              <a.Icon className="h-[18px] w-[18px]" aria-hidden />
            </div>
            <p className="mt-3 text-sm font-semibold text-ink-950 dark:text-ink-50">{a.label}</p>
            <p className="text-xs text-ink-500 dark:text-ink-400 mt-0.5">{a.hint}</p>
          </Link>
        </Tooltip>
      ))}
    </section>
  );
}
