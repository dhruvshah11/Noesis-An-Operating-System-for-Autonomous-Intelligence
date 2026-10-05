"use client";

import { Suspense, useMemo, useState } from "react";
import type React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, Filter, MessageSquarePlus, Search, SlidersHorizontal, X } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";

import { DashboardShell } from "@/components/layout/DashboardShell";
import { buildMockConversations, type Conversation } from "@/testing/mocks";
import { createConversation, listConversations } from "@/lib/api/endpoints";
import { cn, formatNumber } from "@/lib/format";
import { Badge } from "@/components/ui/Badge";
import { getBadgeColorForCodename, getCodenameForRole } from "@/lib/agents_codenames";
import { useDemoMode } from "@/lib/demo";

const STATUS_FILTERS = [
  { key: "all", label: "All" },
  { key: "active", label: "Active" },
  { key: "completed", label: "Completed" },
  { key: "paused", label: "Paused" },
  { key: "failed", label: "Failed" },
] as const;

type StatusFilter = (typeof STATUS_FILTERS)[number]["key"];

function statusStyles(status: Conversation["status"]): string {
  switch (status) {
    case "active":
      return "!border-emerald-300 !bg-emerald-50 dark:!border-emerald-800 dark:!bg-emerald-950/40 !text-emerald-700 dark:!text-emerald-200";
    case "completed":
      return "!border-ink-200 !bg-ink-50 dark:!border-ink-800 dark:!bg-ink-950/40 !text-ink-600 dark:!text-ink-300";
    case "paused":
      return "!border-amber-300 !bg-amber-50 dark:!border-amber-800 dark:!bg-amber-950/40 !text-amber-700 dark:!text-amber-200";
    case "failed":
      return "!border-rose-300 !bg-rose-50 dark:!border-rose-800 dark:!bg-rose-950/40 !text-rose-700 dark:!text-rose-200";
  }
}

function statusDot(status: Conversation["status"]): string {
  switch (status) {
    case "active": return "bg-emerald-500";
    case "completed": return "bg-ink-400";
    case "paused": return "bg-amber-500";
    case "failed": return "bg-rose-500";
  }
}

async function queryConversations(): Promise<Conversation[]> {
  const live = await listConversations();
  if (live.length > 0) return live;
  await new Promise((r) => setTimeout(r, 1000));
  return buildMockConversations(11);
}

function ConversationsInner(): React.JSX.Element {
  const queryClient = useQueryClient();
  const demo = useDemoMode();
  const { data: all = demo.isDemoMode ? demo.conversations.length > 0 ? demo.conversations : buildMockConversations(demo.seed) : buildMockConversations(11), isFetching, isError } = useQuery({
    queryKey: ["conversations", "list"] as const,
    queryFn: queryConversations,
    placeholderData: demo.isDemoMode ? buildMockConversations(demo.seed) : buildMockConversations(11),
    retry: 1,
    enabled: !demo.isDemoMode,
  });

  const [query, setQuery] = useState<string>("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [agent, setAgent] = useState<string>("all");
  const [showForm, setShowForm] = useState(false);
  const [formTitle, setFormTitle] = useState("");
  const [formAgent, setFormAgent] = useState("Planner");

  const createMutation = useMutation({
    mutationFn: (p: { title: string; agent?: string }) => createConversation(p),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["conversations", "list"] });
      toast.success("Conversation created");
      setShowForm(false);
      setFormTitle("");
    },
    onError: async () => {
      await new Promise((r) => setTimeout(r, 600));
      void queryClient.invalidateQueries({ queryKey: ["conversations", "list"] });
      toast.success("Conversation created (local mock)");
      setShowForm(false);
      setFormTitle("");
    },
  });

  const agents = useMemo(() => {
    const set = new Set<string>();
    all.forEach((c) => set.add(c.agent));
    return ["all", ...Array.from(set)];
  }, [all]);

  const filtered = useMemo(() => {
    return all.filter((c) => {
      if (status !== "all" && c.status !== status) return false;
      if (agent !== "all" && c.agent !== agent) return false;
      if (query.trim()) {
        const q = query.toLowerCase();
        if (
          !c.title.toLowerCase().includes(q) &&
          !c.preview.toLowerCase().includes(q) &&
          !c.tags.some((t) => t.toLowerCase().includes(q))
        ) {
          return false;
        }
      }
      return true;
    });
  }, [all, query, status, agent]);

  const submitForm = (e: React.FormEvent<HTMLFormElement>): void => {
    e.preventDefault();
    if (!formTitle.trim()) return;
    createMutation.mutate({ title: formTitle.trim(), agent: formAgent });
  };

  return (
    <DashboardShell>
      <header className="flex flex-col gap-1">
        <p className="text-xs uppercase tracking-[0.18em] text-brand-600 dark:text-brand-300 font-semibold">
          Conversations
          {isFetching && (
            <span className="ml-2 inline-flex items-center gap-1 text-brand-500 dark:text-brand-400">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500 dark:bg-brand-400" />
              syncing
            </span>
          )}
        </p>
        <h1 className="text-2xl font-bold tracking-tight text-ink-950 dark:text-ink-50">
          Agent conversations \u2014 browse, search and resume autonomous runs.
        </h1>
        {isError && (
          <p className="mt-1 text-sm text-amber-700 dark:text-amber-300">
            Backend unreachable \u2014 falling back to local mock data.
          </p>
        )}
      </header>

      <section className="card p-4 flex flex-col gap-3 sm:flex-row sm:items-center animate-fade-in">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-400" aria-hidden />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search titles, previews, tags\u2026"
            className="w-full rounded-xl border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-950/50 pl-9 pr-3 py-2 text-sm placeholder:text-ink-400 focus:outline-none focus:ring-2 focus:ring-brand-500/60"
          />
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 rounded-xl border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-950/50 p-1">
            <Filter className="h-3.5 w-3.5 text-ink-400 ml-2" aria-hidden />
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as StatusFilter)}
              className="bg-transparent text-sm px-2 py-1.5 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500/60"
            >
              {STATUS_FILTERS.map((f) => (
                <option key={f.key} value={f.key}>{f.label}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-1.5 rounded-xl border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-950/50 p-1">
            <SlidersHorizontal className="h-3.5 w-3.5 text-ink-400 ml-2" aria-hidden />
            <select
              value={agent}
              onChange={(e) => setAgent(e.target.value)}
              className="bg-transparent text-sm px-2 py-1.5 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500/60"
            >
              {agents.map((a) => (
                <option key={a} value={a}>{a === "all" ? "All agents" : a}</option>
              ))}
            </select>
          </div>
          <button type="button" className="btn-ghost" aria-label="Archive selected">
            <Archive className="h-4 w-4" />
            <span className="hidden sm:inline">Archive</span>
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={() => setShowForm((s) => !s)}
            aria-expanded={showForm}
          >
            <MessageSquarePlus className="h-4 w-4" />
            New run
          </button>
        </div>
      </section>

      {showForm && (
        <form
          onSubmit={submitForm}
          className="card p-4 grid gap-3 sm:grid-cols-[1fr_auto_auto] sm:items-end animate-fade-in"
        >
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-ink-600 dark:text-ink-300">Title</span>
            <input
              type="text"
              value={formTitle}
              onChange={(e) => setFormTitle(e.target.value)}
              placeholder="Goal for the autonomous run\u2026"
              className="rounded-xl border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-950/50 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/60"
              required
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-ink-600 dark:text-ink-300">Agent</span>
            <select
              value={formAgent}
              onChange={(e) => setFormAgent(e.target.value)}
              className="rounded-xl border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-950/50 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/60"
            >
              {agents.filter((a) => a !== "all").length === 0
                ? ["Planner", "Coding", "Research", "Reflection", "RAG", "Tool"].map((a) => (
                    <option key={a} value={a}>{a}</option>
                  ))
                : agents.filter((a) => a !== "all").map((a) => (
                    <option key={a} value={a}>{a}</option>
                  ))}
            </select>
          </label>
          <div className="flex items-center gap-2">
            <button
              type="submit"
              className="btn-primary"
              disabled={createMutation.isPending}
            >
              {createMutation.isPending ? "Creating\u2026" : "Create"}
            </button>
            <button
              type="button"
              className="btn-ghost !p-2"
              onClick={() => setShowForm(false)}
              aria-label="Cancel form"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </form>
      )}

      <section className="grid gap-3" aria-label="Conversation list">
        {filtered.length === 0 ? (
          <div className="card p-10 text-center text-ink-500 dark:text-ink-400 animate-fade-in">
            <p className="font-medium">No conversations match your filters.</p>
            <p className="text-sm mt-1">Try clearing the search or changing filters.</p>
          </div>
        ) : (
          filtered.map((c) => (
            <article
              key={c.id}
              className="card p-4 flex flex-col gap-3 sm:flex-row sm:items-start hover:shadow-card hover:-translate-y-0.5 transition cursor-pointer animate-fade-in"
            >
              <div className="flex items-start gap-3 flex-1 min-w-0">
                <div
                  className={cn(
                    "mt-1 h-2.5 w-2.5 shrink-0 rounded-full ring-4 ring-white dark:ring-[rgb(var(--surface))]",
                    statusDot(c.status),
                  )}
                  aria-hidden
                />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-sm font-semibold text-ink-950 dark:text-ink-50 truncate">{c.title}</h3>
                    <span className={cn("chip", statusStyles(c.status))}>{c.status}</span>
                    {(() => {
                      const codename = getCodenameForRole(c.agent);
                      const badgeColor = codename ? getBadgeColorForCodename(codename) : "text-brand-purple";
                      return (
                        <span className="inline-flex items-center gap-1">
                          <span className="chip">{c.agent}</span>
                          {codename && (
                            <Badge variant="default" className={cn("mr-1", badgeColor)}>
                              {codename}
                            </Badge>
                          )}
                        </span>
                      );
                    })()}
                    {c.tags.map((t) => (
                      <span key={t} className="chip !bg-ink-100 dark:!bg-ink-900/60">#{t}</span>
                    ))}
                  </div>
                  <p className="mt-1.5 text-sm text-ink-600 dark:text-ink-300 line-clamp-1">{c.preview}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-500 dark:text-ink-400">
                    <span>{formatNumber(c.messages, 0)} msgs</span>
                    <span>{formatNumber(c.tokens)} tokens</span>
                    <span>
                      {formatDistanceToNow(c.updated_at * 1000, { addSuffix: true })}
                    </span>
                  </div>
                </div>
              </div>
            </article>
          ))
        )}
      </section>
    </DashboardShell>
  );
}

function ConversationsSuspenseFallback(): React.JSX.Element {
  const all = buildMockConversations(11);
  return (
    <DashboardShell>
      <header className="flex flex-col gap-1">
        <p className="text-xs uppercase tracking-[0.18em] text-brand-600 dark:text-brand-300 font-semibold">
          Conversations
          <span className="ml-2 inline-flex items-center gap-1 text-brand-500 dark:text-brand-400">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500 dark:bg-brand-400" />
            loading
          </span>
        </p>
        <h1 className="text-2xl font-bold tracking-tight text-ink-950 dark:text-ink-50">
          Agent conversations \u2014 browse, search and resume autonomous runs.
        </h1>
      </header>
      <section className="card p-4 h-14 animate-pulse opacity-60 rounded-xl" />
      <section className="grid gap-3" aria-label="Conversation list skeleton">
        {all.slice(0, 4).map((c) => (
          <article
            key={c.id}
            className="card p-4 animate-pulse opacity-70"
          >
            <div className="h-4 w-2/3 rounded bg-ink-200 dark:bg-ink-800 mb-2" />
            <div className="h-3 w-1/2 rounded bg-ink-200 dark:bg-ink-800" />
          </article>
        ))}
      </section>
    </DashboardShell>
  );
}

export default function ConversationsPage(): React.JSX.Element {
  return (
    <Suspense fallback={<ConversationsSuspenseFallback />}>
      <ConversationsInner />
    </Suspense>
  );
}
