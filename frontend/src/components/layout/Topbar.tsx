"use client";

import { Bell, Moon, PanelLeftClose, PanelLeftOpen, Search, Sun } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { cn } from "@/lib/format";

export function Topbar({
  compact,
  onToggleCompact,
}: {
  readonly compact: boolean;
  readonly onToggleCompact: () => void;
}): JSX.Element {
  const [dark, setDark] = useState<boolean>(() => {
    if (typeof window === "undefined") return true;
    const stored = window.localStorage.getItem("theme");
    return stored ? stored === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", dark);
    window.localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);

  const onKey = useCallback(
    (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        const el = document.querySelector<HTMLInputElement>("input[name='global-search']");
        el?.focus();
      } else if (e.key === "[" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        onToggleCompact();
      }
    },
    [onToggleCompact],
  );

  useEffect(() => {
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onKey]);

  return (
    <header className="sticky top-0 z-20 flex h-16 shrink-0 items-center gap-3 border-b border-ink-200 dark:border-ink-800 bg-white/70 dark:bg-ink-950/60 backdrop-blur px-4">
      <button
        type="button"
        onClick={onToggleCompact}
        className="btn-ghost !p-2 rounded-xl"
        aria-label={compact ? "Expand sidebar" : "Collapse sidebar"}
        aria-pressed={compact}
      >
        {compact ? <PanelLeftOpen className="h-[18px] w-[18px]" /> : <PanelLeftClose className="h-[18px] w-[18px]" />}
      </button>

      <div className="relative flex-1 max-w-xl">
        <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-400" aria-hidden />
        <kbd className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 hidden md:inline-flex items-center gap-1 rounded-md border border-ink-200 dark:border-ink-800 bg-ink-50 dark:bg-ink-900/60 px-1.5 py-0.5 text-[10px] font-medium text-ink-500 dark:text-ink-400">
          <span>⌘</span>
          <span>K</span>
        </kbd>
        <input
          name="global-search"
          type="search"
          placeholder="Search memory, documents, agents, runs…"
          className={cn(
            "w-full rounded-xl border border-ink-200 dark:border-ink-800 bg-ink-50 dark:bg-ink-900/50 pl-10 pr-16 py-2.5 text-sm",
            "placeholder:text-ink-400 focus:outline-none focus:ring-2 focus:ring-brand-500/60 focus:border-brand-400 transition",
          )}
        />
      </div>

      <div className="ml-auto flex items-center gap-2">
        <button
          type="button"
          onClick={() => setDark((d) => !d)}
          className="btn-ghost !p-2 rounded-xl"
          aria-pressed={dark}
          aria-label="Toggle theme"
        >
          {dark ? <Sun className="h-[18px] w-[18px]" /> : <Moon className="h-[18px] w-[18px]" />}
        </button>
        <button type="button" className="btn-ghost !p-2 rounded-xl relative" aria-label="Notifications">
          <Bell className="h-[18px] w-[18px]" />
          <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-brand-500 ring-2 ring-white dark:ring-ink-950" />
        </button>
      </div>
    </header>
  );
}
