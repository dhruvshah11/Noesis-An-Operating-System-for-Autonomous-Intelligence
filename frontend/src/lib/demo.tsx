"use client";

import { useMemo } from "react";
import { useSearchParams } from "next/navigation";
import type { Agent, Conversation } from "@/testing/mocks";
import type { MemoryRecord } from "@/lib/schemas";
import { buildMockAgents, buildMockConversations, buildMockMemory } from "@/testing/mocks";
import {
  AGENT_CODENAMES,
  getPaletteClassForCodename,
} from "@/lib/agents_codenames";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/format";

export interface DemoWorkflowNode {
  readonly id: string;
  readonly role: string;
  readonly codename: string;
  readonly status: "success" | "running" | "pending" | "failed";
  readonly progress: number;
  readonly description: string;
  readonly depends_on: readonly number[];
  readonly accent: string;
  readonly paletteBorderClass: string;
  readonly paletteBgClass: string;
  readonly paletteHex: string;
  readonly paletteTextClass: string;
}

export interface DemoModeState {
  readonly isDemoMode: boolean;
  readonly seed: number;
  readonly conversations: Conversation[];
  readonly memoryItems: MemoryRecord[];
  readonly agents: Agent[];
  readonly workflowNodes: DemoWorkflowNode[];
}

const DEMO_WORKFLOW_DESCRIPTIONS: readonly string[] = [
  "Decompose goal into measurable plan steps with confidence scoring",
  "Gather reference material and research vector DB benchmarks",
  "Retrieve relevant context from memory tiers (Gy\u0101n layer)",
  "Draft implementation: JWT rotation + refresh-token denylist",
  "Execute unit + integration tests with coverage gating",
  "Invoke shell: docker build + integration harness",
  "Search web for recent CVE advisories on auth patterns",
  "Critique design: detect edge cases in session expiry",
  "Persist conversation + plan artifacts to episodic memory",
  "Audit tool-call chain for capability escapes and leaks",
  "Synthesise final output with citations and changelog",
  "Supervise end-to-end run, sign-off or trigger replan",
] as const;

export function useDemoMode(): DemoModeState {
  const searchParams = useSearchParams();
  const demo = searchParams.get("demo");
  const isDemoMode = demo === "true" || demo === "1" || demo === "yes";
  const seed = 42;

  return useMemo<DemoModeState>(() => {
    if (!isDemoMode) {
      return {
        isDemoMode: false,
        seed,
        conversations: [],
        memoryItems: [],
        agents: [],
        workflowNodes: [],
      };
    }

    const conversations = buildMockConversations(seed);
    const memoryItems = buildMockMemory(seed, 48);
    const agents = buildMockAgents(seed);

    const statuses: DemoWorkflowNode["status"][] = [
      "success", "success", "success", "success",
      "success", "success", "running", "pending",
      "pending", "pending", "pending", "pending",
    ];
    const progress: number[] = [
      100, 100, 100, 100, 100, 100, 42, 0, 0, 0, 0, 0,
    ];

    const workflowNodes: DemoWorkflowNode[] = AGENT_CODENAMES.map((entry, idx): DemoWorkflowNode => ({
      id: `demo-node-${idx}`,
      role: entry.role,
      codename: entry.codename,
      status: statuses[idx] ?? "pending",
      progress: progress[idx] ?? 0,
      description: DEMO_WORKFLOW_DESCRIPTIONS[idx] ?? `${entry.role} step ${idx}`,
      depends_on: idx === 0 ? [] : [idx - 1],
      accent: entry.paletteBorderClass,
      paletteBorderClass: entry.paletteBorderClass,
      paletteBgClass: entry.paletteBgClass,
      paletteHex: entry.paletteHex,
      paletteTextClass: entry.paletteClass,
    }));

    return {
      isDemoMode: true,
      seed,
      conversations,
      memoryItems,
      agents,
      workflowNodes,
    };
  }, [isDemoMode, seed]);
}

export function DemoPipelineSankey({ nodes }: { readonly nodes: readonly DemoWorkflowNode[] }): JSX.Element {
  return (
    <div
      className="card p-5 border-dashed animate-fade-in"
      aria-label="Demo mode 12-node Sanskrit codename workflow"
      data-testid="demo-pipeline-sankey"
    >
      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-brand-600 dark:text-brand-300 font-semibold">
            Demo mode · 12-node pipeline
          </p>
          <h2 className="text-sm font-semibold text-ink-950 dark:text-ink-50 mt-0.5">
            Pre-built workflow: Manan → Vidya → Kriyakārī → Samanyakā
          </h2>
        </div>
        <span className="chip !border-brand-300 dark:!border-brand-800 !bg-brand-50 dark:!bg-brand-950/40 !text-brand-700 dark:!text-brand-200">
          seed=42
        </span>
      </div>

      <div className="space-y-2">
        {nodes.map((node, idx) => (
          <div
            key={node.id}
            data-testid={`sankey-node-${node.codename.toLowerCase()}`}
            data-palette-hex={node.paletteHex}
            className={cn(
              "flex items-center gap-3 rounded-xl border border-ink-200 dark:border-ink-800 p-3 transition",
              node.paletteBorderClass,
            )}
            style={{ borderColor: `${node.paletteHex}50` }}
          >
            <div
              className="flex items-center justify-center h-8 w-8 rounded-full text-xs font-bold shrink-0"
              style={{ backgroundColor: `${node.paletteHex}20`, color: node.paletteHex }}
              data-testid={`sankey-node-badge-${node.codename.toLowerCase()}`}
            >
              {String(idx + 1).padStart(2, "0")}
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-semibold text-ink-950 dark:text-ink-50">
                  {node.role}
                </span>
                <Badge
                  variant="brand"
                  className={cn("mr-1", getPaletteClassForCodename(node.codename))}
                  style={{ color: node.paletteHex }}
                  data-testid={`sankey-codename-${node.codename.toLowerCase()}`}
                >
                  {node.codename}
                </Badge>
              </div>
              <p className="text-xs text-ink-500 dark:text-ink-400 mt-0.5 truncate">
                {node.description}
              </p>
              <div className="mt-2 h-1.5 w-full rounded-full bg-ink-100 dark:bg-ink-900 overflow-hidden">
                <div
                  className={cn(
                    "h-full rounded-full transition-all duration-300",
                    node.status === "success"
                      ? "bg-gradient-to-r from-emerald-500 to-emerald-400"
                      : node.status === "running"
                        ? `${node.paletteBgClass} animate-pulse`
                        : node.status === "failed"
                          ? "bg-gradient-to-r from-rose-500 to-rose-400"
                          : "bg-ink-300 dark:bg-ink-700",
                  )}
                  style={node.status === "running" ? { backgroundColor: node.paletteHex, width: `${node.progress}%` } : { width: `${node.progress}%` }}
                />
              </div>
            </div>

            <span className={cn(
              "chip !py-0.5 shrink-0",
              node.status === "success"
                ? "!border-emerald-300 !bg-emerald-50 dark:!border-emerald-800 dark:!bg-emerald-950/40 !text-emerald-700 dark:!text-emerald-200"
                : node.status === "running"
                  ? `${node.paletteBorderClass} !bg-white dark:!bg-ink-950/40`
                  : node.status === "failed"
                    ? "!border-rose-300 !bg-rose-50 dark:!border-rose-800 dark:!bg-rose-950/40 !text-rose-700 dark:!text-rose-200"
                    : "!border-ink-300 !bg-ink-50 dark:!border-ink-700 dark:!bg-ink-900/60 !text-ink-500 dark:!text-ink-400",
            )}
            style={node.status === "running" ? { borderColor: `${node.paletteHex}50`, color: node.paletteHex } : undefined}>
              {node.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
