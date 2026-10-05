"use client";

import {
  BarChart3,
  Bot,
  BrainCircuit,
  Cpu,
  FileSearch,
  LayoutDashboard,
  MessageSquare,
  ScrollText,
  Settings2,
  Sparkles,
  Workflow,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ComponentType, SVGProps } from "react";

import { cn } from "@/lib/format";

type Icon = ComponentType<SVGProps<SVGSVGElement>>;

interface NavItem {
  readonly href: string;
  readonly label: string;
  readonly Icon: Icon;
  readonly badge?: string;
}

const NAV: readonly NavItem[] = [
  { href: "/", label: "Dashboard", Icon: LayoutDashboard },
  { href: "/conversations", label: "Conversations", Icon: MessageSquare, badge: "7" },
  { href: "/agents", label: "Agents", Icon: Bot },
  { href: "/benchmarks", label: "Bench Results", Icon: BarChart3, badge: "Hub" },
  { href: "/agents/benchmark", label: "Bench Runner", Icon: Cpu, badge: "P10" },
  { href: "/timeline", label: "Execution Timeline", Icon: Workflow, badge: "Live" },
  { href: "/memory", label: "Memory Explorer", Icon: BrainCircuit },
  { href: "/documents", label: "Documents", Icon: FileSearch },
  { href: "/metrics", label: "Observability", Icon: Sparkles },
  { href: "/settings", label: "Settings", Icon: Settings2 },
] as const;

export function Sidebar({ compact = false }: { readonly compact?: boolean }): JSX.Element {
  const pathname = (usePathname() as string | null) ?? "/";
  const active = (href: string): boolean =>
    href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);

  return (
    <aside
      className={cn(
        "flex h-full shrink-0 flex-col border-r border-ink-200 dark:border-ink-800 bg-white/70 dark:bg-ink-950/60 backdrop-blur transition-[width] duration-200",
        compact ? "w-[76px]" : "w-64",
      )}
    >
      <div className="flex items-center gap-3 px-4 py-5">
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-card">
          <ScrollText className="h-5 w-5" aria-hidden />
        </div>
        {!compact && (
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-ink-900 dark:text-ink-50">AstraOS</p>
            <p className="truncate text-xs text-ink-500 dark:text-ink-400">Autonomous agent OS</p>
          </div>
        )}
      </div>

      <nav className="flex-1 space-y-1 px-3 py-2 overflow-y-auto">
        {NAV.map(({ href, label, Icon, badge }) => {
          const isActive = active(href);
          return (
            <Link
              key={href}
              href={href}
              className="sidebar-link"
              data-active={isActive || undefined}
              aria-current={isActive ? "page" : undefined}
            >
              <Icon className="h-[18px] w-[18px] shrink-0" aria-hidden />
              {!compact && <span className="truncate flex-1">{label}</span>}
              {!compact && badge ? (
                <span
                  className={cn(
                    "chip",
                    badge === "Live" && "!border-brand-300 !bg-brand-50 dark:!border-brand-800 dark:!bg-brand-950/60 !text-brand-700 dark:!text-brand-200",
                  )}
                >
                  {badge}
                </span>
              ) : null}
            </Link>
          );
        })}
      </nav>

      <footer className="border-t border-ink-200 dark:border-ink-800 px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-full bg-gradient-to-br from-ink-300 to-ink-500 dark:from-ink-700 dark:to-ink-900 text-white grid place-items-center text-xs font-semibold shadow-soft">
            DX
          </div>
          {!compact && (
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-semibold text-ink-900 dark:text-ink-100">Demo Admin</p>
              <p className="truncate text-[11px] text-ink-500 dark:text-ink-400">admin@astraos.local</p>
            </div>
          )}
        </div>
      </footer>
    </aside>
  );
}
