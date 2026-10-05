"use client";

import { Suspense, useEffect, useState } from "react";
import type React from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Bot, Code2, Database, Network, Play, Search, Sparkles, TerminalSquare, Workflow, X, Zap } from "lucide-react";
import { toast } from "sonner";
import type { ComponentType, SVGProps } from "react";

import { DashboardShell } from "@/components/layout/DashboardShell";
import { executeRun, type ExecuteRunResponse, listAgents } from "@/lib/api/endpoints";
import { cn, formatDurationMs, formatNumber } from "@/lib/format";
import { type Agent, buildMockAgents } from "@/testing/mocks";
import { Badge } from "@/components/ui/Badge";
import { getBadgeColorForCodename, getCodenameForRole } from "@/lib/agents_codenames";
import { DemoPipelineSankey, useDemoMode } from "@/lib/demo";

const TYPE_ICON: Record<Agent["type"], ComponentType<SVGProps<SVGSVGElement>>> = {
  planner: Workflow,
  research: Search,
  coding: Code2,
  rag: Database,
  tool: TerminalSquare,
  reflection: Sparkles,
};

const TYPE_TO_ROLE: Record<Agent["type"], string> = {
  planner: "Planner",
  research: "Researcher",
  coding: "Coder",
  rag: "Memory",
  tool: "Tooler",
  reflection: "Critic",
};

const TYPE_TONE: Record<Agent["type"], "brand" | "emerald" | "amber" | "rose" | "violet" | "ink"> = {
  planner: "brand",
  research: "emerald",
  coding: "violet",
  rag: "amber",
  tool: "ink",
  reflection: "rose",
};

const toneBg: Record<ReturnType<typeof typeTone>, string> = {
  brand: "from-brand-500/12 to-brand-700/0 text-brand-700 dark:text-brand-200",
  emerald: "from-emerald-500/12 to-emerald-700/0 text-emerald-700 dark:text-emerald-200",
  amber: "from-amber-500/12 to-amber-700/0 text-amber-700 dark:text-amber-200",
  rose: "from-rose-500/12 to-rose-700/0 text-rose-700 dark:text-rose-200",
  violet: "from-violet-500/12 to-violet-700/0 text-violet-700 dark:text-violet-200",
  ink: "from-ink-500/12 to-ink-700/0 text-ink-700 dark:text-ink-200",
};

function typeTone(t: Agent["type"]): "brand" | "emerald" | "amber" | "rose" | "violet" | "ink" {
  return TYPE_TONE[t];
}

function statusStyles(status: Agent["status"]): { dot: string; chip: string; label: string } {
  switch (status) {
    case "online":
      return {
        dot: "bg-emerald-500",
        chip: "!border-emerald-300 !bg-emerald-50 dark:!border-emerald-800 dark:!bg-emerald-950/40 !text-emerald-700 dark:!text-emerald-200",
        label: "Online",
      };
    case "busy":
      return {
        dot: "bg-amber-500",
        chip: "!border-amber-300 !bg-amber-50 dark:!border-amber-800 dark:!bg-amber-950/40 !text-amber-700 dark:!text-amber-200",
        label: "Busy",
      };
    case "offline":
      return {
        dot: "bg-ink-400",
        chip: "!border-ink-200 !bg-ink-50 dark:!border-ink-800 dark:!bg-ink-950/40 !text-ink-600 dark:!text-ink-300",
        label: "Offline",
      };
    case "error":
      return {
        dot: "bg-rose-500",
        chip: "!border-rose-300 !bg-rose-50 dark:!border-rose-800 dark:!bg-rose-950/40 !text-rose-700 dark:!text-rose-200",
        label: "Error",
      };
  }
}

type NodeStatus = "pending" | "running" | "success" | "failed";

const nodeStatusTone: Record<NodeStatus, string> = {
  pending: "bg-ink-300 dark:bg-ink-700",
  running: "bg-brand-500 animate-pulse",
  success: "bg-emerald-500",
  failed: "bg-rose-500",
};

const nodeStatusChip: Record<NodeStatus, string> = {
  pending: "!border-ink-300 !bg-ink-50 dark:!border-ink-700 dark:!bg-ink-900/60 !text-ink-500 dark:!text-ink-400",
  running: "!border-brand-300 !bg-brand-50 dark:!border-brand-800 dark:!bg-brand-950/40 !text-brand-700 dark:!text-brand-200",
  success: "!border-emerald-300 !bg-emerald-50 dark:!border-emerald-800 dark:!bg-emerald-950/40 !text-emerald-700 dark:!text-emerald-200",
  failed: "!border-rose-300 !bg-rose-50 dark:!border-rose-800 dark:!bg-rose-950/40 !text-rose-700 dark:!text-rose-200",
};

interface RunNode {
  readonly id: string;
  readonly name: string;
  readonly status: NodeStatus;
  readonly progress: number;
}

function buildMockRunNodes(agentName: string, userPrompt: string): RunNode[] {
  const base: RunNode[] = [
    { id: "n-plan", name: "Planner: decompose goal", status: "pending", progress: 0 },
    { id: "n-research", name: "Research: gather context", status: "pending", progress: 0 },
    { id: `n-${agentName.toLowerCase().split(" ")[0] ?? "exec"}`, name: `${agentName}: ${userPrompt.slice(0, 40)}${userPrompt.length > 40 ? "\u2026" : ""}`, status: "pending", progress: 0 },
    { id: "n-reflect", name: "Reflection: verify output", status: "pending", progress: 0 },
  ];
  return base;
}

async function queryAgents(): Promise<Agent[]> {
  const live = await listAgents();
  if (live.length > 0) return live;
  await new Promise((r) => setTimeout(r, 1000));
  return buildMockAgents(9);
}

function AgentsInner(): React.JSX.Element {
  const demo = useDemoMode();

  const { data: agents = demo.isDemoMode ? buildMockAgents(demo.seed) : buildMockAgents(9), isFetching, isError } = useQuery({
    queryKey: ["agents", "list"] as const,
    queryFn: queryAgents,
    placeholderData: demo.isDemoMode ? buildMockAgents(demo.seed) : buildMockAgents(9),
    retry: 1,
    enabled: !demo.isDemoMode,
  });

  const [showWorkbench, setShowWorkbench] = useState(demo.isDemoMode);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [prompt, setPrompt] = useState(demo.isDemoMode ? "Build a JWT auth pipeline with refresh-token denylist" : "");
  const [runNodes, setRunNodes] = useState<RunNode[]>(
    demo.isDemoMode
      ? demo.workflowNodes.map((n): RunNode => ({
          id: n.id,
          name: `${n.role} \u00b7 ${n.codename}: ${n.description.slice(0, 50)}${n.description.length > 50 ? "\u2026" : ""}`,
          status: n.status,
          progress: n.progress,
        }))
      : [],
  );
  const [runStatus, setRunStatus] = useState<"idle" | "running" | "success" | "failed">(
    demo.isDemoMode ? "running" : "idle",
  );

  useEffect(() => {
    if (!showWorkbench) {
      if (!demo.isDemoMode) {
        setRunNodes([]);
        setRunStatus("idle");
      }
    }
  }, [showWorkbench, demo.isDemoMode]);

  const executeMutation = useMutation({
    mutationFn: (p: { agent_id?: string; prompt: string }) => executeRun(p),
    onMutate: (vars) => {
      const agentName = agents.find((a) => a.id === vars.agent_id)?.name ?? "Agent";
      const nodes = buildMockRunNodes(agentName, vars.prompt);
      setRunNodes(nodes);
      setRunStatus("running");
      nodes.forEach((_, i) => {
        const offsets = [400, 1_400, 2_600, 4_200];
        const offStart = offsets[i] ?? i * 1_200;
        let prog = 0;
        const progInterval = setInterval(() => {
          prog = Math.min(95, prog + 7 + Math.floor(Math.random() * 12));
          setRunNodes((prev) => prev.map((n, k) => {
            if (k < i) return { ...n, status: "success", progress: 100 };
            if (k === i) return { ...n, status: "running", progress: prog };
            return n;
          }));
        }, 250);
        setTimeout(() => {
          clearInterval(progInterval);
          setRunNodes((prev) => prev.map((n, k) => {
            if (k < i) return { ...n, status: "success", progress: 100 };
            if (k === i) return { ...n, status: "success", progress: 100 };
            return n;
          }));
          if (i === nodes.length - 1) {
            setRunStatus("success");
            toast.success("Agent run completed");
          }
        }, offStart + 1_000);
      });
    },
    onSuccess: (resp: ExecuteRunResponse) => {
      setRunNodes(resp.nodes.map((n) => ({
        id: n.id,
        name: n.name,
        status: n.status,
        progress: Math.round(n.progress * 100),
      })));
      setRunStatus(resp.status === "success" ? "success" : resp.status === "failed" ? "failed" : "running");
    },
    onError: () => {
      toast.success("Agent run simulated (local mock)");
    },
  });

  const startRun = (e: React.FormEvent<HTMLFormElement>): void => {
    e.preventDefault();
    if (!prompt.trim()) return;
    const payload: { agent_id?: string; prompt: string } = { prompt: prompt.trim() };
    if (selectedAgentId) payload.agent_id = selectedAgentId;
    executeMutation.mutate(payload);
  };

  const summary = {
    online: agents.filter((a) => a.status === "online").length,
    busy: agents.filter((a) => a.status === "busy").length,
    error: agents.filter((a) => a.status === "error").length,
    calls24h: agents.reduce((acc, a) => acc + a.invocations_24h, 0),
  };

  return (
    <DashboardShell>
      <header className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-brand-600 dark:text-brand-300 font-semibold">
            Agents
            {demo.isDemoMode && (
              <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-gradient-to-r from-[#6E56CF]/80 via-[#22c55e]/70 to-[#06b6d4]/60 px-2 py-0.5 text-[10px] font-bold text-white">
                DEMO MODE \u00b7 12-node Sanskrit pipeline
              </span>
            )}
            {!demo.isDemoMode && isFetching && (
              <span className="ml-2 inline-flex items-center gap-1 text-brand-500 dark:text-brand-400">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500 dark:bg-brand-400" />
                syncing
              </span>
            )}
          </p>
          <h1 className="text-2xl font-bold tracking-tight text-ink-950 dark:text-ink-50">
            Agent fleet \u2014 status, capabilities and live health of every worker agents.
          </h1>
          {!demo.isDemoMode && isError && (
            <p className="mt-1 text-sm text-amber-700 dark:text-amber-300">
              Backend unreachable \u2014 falling back to local mock data.
            </p>
          )}
          {demo.isDemoMode && (
            <p className="mt-1 text-sm text-brand-purple dark:text-brand-purple">
              Viva panel demo: 12 Sanskrit codename nodes loaded (Manan \u2192 Vidya \u2192 Kriyak\u0101r\u012b \u2192 Samanyak\u0101). Use seed=42 deterministic data.
            </p>
          )}
        </div>
        <div className="mt-4 sm:mt-0 flex items-center gap-2 flex-wrap">
          <span className="chip">
          <span className="h-2 w-2 rounded-full bg-emerald-500" /> {summary.online} online
          </span>
          <span className="chip">
            <span className="h-2 w-2 rounded-full bg-amber-500" /> {summary.busy} busy
          </span>
          {summary.error > 0 && (
            <span className="chip">
              <span className="h-2 w-2 rounded-full bg-rose-500" /> {summary.error} error
            </span>
          )}
          <span className="chip">
            <Zap className="h-3 w-3" /> {formatNumber(summary.calls24h, 0)} calls / 24h
          </span>
          <button
            type="button"
            className="btn-primary"
            onClick={() => setShowWorkbench(true)}
          >
            <Play className="h-4 w-4" />
            Launch workbench
          </button>
        </div>
      </header>

      {showWorkbench && (
        <section className="card p-5 animate-fade-in border-brand-300/40 dark:border-brand-800/40 ring-1 ring-brand-500/20">
          <div className="flex items-start justify-between gap-3 mb-4">
            <div>
              <h2 className="text-sm font-semibold text-ink-950 dark:text-ink-50 flex items-center gap-2">
                <Network className="h-4 w-4 text-brand-600 dark:text-brand-300" />
                Agent execution workbench
              </h2>
              <p className="text-xs text-ink-500 dark:text-ink-400 mt-0.5">
                Compose a prompt, pick an agent, and stream the node-level execution plan.
              </p>
            </div>
            <button
              type="button"
              className="btn-ghost !p-2"
              onClick={() => setShowWorkbench(false)}
              aria-label="Close workbench"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <form onSubmit={startRun} className="grid gap-3 sm:grid-cols-[1fr_auto_auto] sm:items-end">
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-ink-600 dark:text-ink-300">Prompt</span>
              <input
                type="text"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Summarise Q2 OKRs and email the team\u2026"
                className="rounded-xl border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-950/50 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/60"
                required
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-ink-600 dark:text-ink-300">Agent</span>
              <select
                value={selectedAgentId ?? ""}
                onChange={(e) => setSelectedAgentId(e.target.value || null)}
                className="rounded-xl border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-950/50 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/60"
              >
                <option value="">Any (router)</option>
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>{a.name} \u00b7 {a.type}</option>
                ))}
              </select>
            </label>
            <button
              type="submit"
              className="btn-primary"
              disabled={executeMutation.isPending || runStatus === "running"}
            >
              <Play className="h-4 w-4" />
              {runStatus === "running" ? "Running\u2026" : "Execute"}
            </button>
          </form>

          {runNodes.length > 0 && (
            <div className="mt-5 space-y-2" aria-label="Execution nodes">
              {runNodes.map((n) => (
                <div key={n.id} className="rounded-xl border border-ink-200 dark:border-ink-800 p-3 flex items-center gap-3">
                  <span className={cn("h-2.5 w-2.5 shrink-0 rounded-full ring-2 ring-white dark:ring-[rgb(var(--surface))]", nodeStatusTone[n.status])} aria-hidden />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium text-ink-900 dark:text-ink-100 truncate">{n.name}</p>
                      <span className={cn("chip !py-0.5", nodeStatusChip[n.status])}>
                        {n.status}
                      </span>
                    </div>
                    <div className="mt-2 h-1.5 w-full rounded-full bg-ink-100 dark:bg-ink-900 overflow-hidden">
                      <div
                        className={cn(
                          "h-full rounded-full transition-all duration-300",
                          n.status === "failed"
                            ? "bg-rose-500"
                            : n.status === "success"
                              ? "bg-emerald-500"
                              : "bg-gradient-to-r from-brand-500 to-brand-400",
                        )}
                        style={{ width: `${n.progress}%` }}
                      />
                    </div>
                    <p className="mt-1 text-[11px] text-right tabular-nums text-ink-500 dark:text-ink-400">
                      {n.progress}%
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {demo.isDemoMode && demo.workflowNodes.length > 0 && !showWorkbench && (
        <DemoPipelineSankey nodes={demo.workflowNodes} />
      )}

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-label="Agent cards">
        {agents.map((a) => {
          const Icon = TYPE_ICON[a.type];
          const status = statusStyles(a.status);
          const tone = typeTone(a.type);
          const role = TYPE_TO_ROLE[a.type];
          const codename = getCodenameForRole(role);
          const badgeColor = codename ? getBadgeColorForCodename(codename) : "text-brand-purple";
          return (
            <article
            key={a.id}
            className="card p-5 flex flex-col gap-4 hover:shadow-card hover:-translate-y-0.5 transition animate-fade-in"
            >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <div
                  className={cn(
                    "inline-flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br",
                    toneBg[tone],
                  )}
                >
                  <Icon className="h-[18px] w-[18px]" aria-hidden />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-1 flex-wrap min-w-0">
                    <h3 className="text-sm font-semibold text-ink-950 dark:text-ink-50 truncate">{a.name}</h3>
                    {codename && (
                      <Badge variant="default" className={cn("mr-1", badgeColor)}>
                        {codename}
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs text-ink-500 dark:text-ink-400 font-mono truncate">{a.id} \u00b7 v{a.version} \u00b7 {role}</p>
                </div>
              </div>
              <div className="flex items-center gap-1.5">
                <span className={cn("h-2 w-2 rounded-full ring-2 ring-white dark:ring-[rgb(var(--surface))]", status.dot)} aria-hidden />
                <span className={cn("chip", status.chip)}>{status.label}</span>
              </div>
            </div>

            <p className="text-xs text-ink-600 dark:text-ink-300 leading-relaxed">{a.description}</p>

            <div>
              <p className="text-[11px] uppercase tracking-[0.14em] text-ink-500 dark:text-ink-400 font-semibold mb-2">
                Capabilities
              </p>
              <div className="flex flex-wrap gap-1.5">
                {a.capabilities.map((cap) => (
                  <span key={cap} className="chip !bg-ink-100 dark:!bg-ink-900/60">
                    {cap}
                  </span>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 pt-2 border-t border-ink-100 dark:border-ink-800">
              <div>
                <p className="text-[11px] uppercase tracking-[0.14em] text-ink-500 dark:text-ink-400 font-semibold">
                  24h calls
                </p>
                <p className="mt-1 text-lg font-semibold tabular-nums text-ink-900 dark:text-ink-100">
                  {formatNumber(a.invocations_24h, 0)}
                </p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-[0.14em] text-ink-500 dark:text-ink-400 font-semibold">
                  Avg latency
                </p>
                <p className="mt-1 text-lg font-semibold tabular-nums text-ink-900 dark:text-ink-100">
                  {formatDurationMs(a.avg_latency_ms)}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button type="button" className="btn-ghost flex-1">
                <Bot className="h-4 w-4" />
                Details
              </button>
              <button
                type="button"
                className="btn-primary flex-1"
                onClick={() => {
                  setSelectedAgentId(a.id);
                  setShowWorkbench(true);
                }}
              >
                <Network className="h-4 w-4" />
                Invoke
              </button>
            </div>
            </article>
          );
        })}
      </section>
    </DashboardShell>
  );
}

function AgentsSuspenseFallback(): React.JSX.Element {
  const agents = buildMockAgents(9);
  return (
    <DashboardShell>
      <header className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-brand-600 dark:text-brand-300 font-semibold">
            Agents
            <span className="ml-2 inline-flex items-center gap-1 text-brand-500 dark:text-brand-400">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500 dark:bg-brand-400" />
              loading
            </span>
          </p>
          <h1 className="text-2xl font-bold tracking-tight text-ink-950 dark:text-ink-50">
            Agent fleet \u2014 status, capabilities and live health of every worker agents.
          </h1>
        </div>
      </header>
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-label="Agent cards skeleton">
        {agents.slice(0, 6).map((a) => (
          <div
            key={a.id}
            className="card p-5 animate-pulse opacity-60"
          >
            <div className="h-10 w-10 rounded-xl bg-ink-200 dark:bg-ink-800 mb-3" />
            <div className="h-4 w-2/3 rounded bg-ink-200 dark:bg-ink-800 mb-2" />
            <div className="h-3 w-full rounded bg-ink-200 dark:bg-ink-800 mb-2" />
            <div className="h-3 w-5/6 rounded bg-ink-200 dark:bg-ink-800" />
          </div>
        ))}
      </section>
    </DashboardShell>
  );
}

export default function AgentsPage(): React.JSX.Element {
  return (
    <Suspense fallback={<AgentsSuspenseFallback />}>
      <AgentsInner />
    </Suspense>
  );
}
