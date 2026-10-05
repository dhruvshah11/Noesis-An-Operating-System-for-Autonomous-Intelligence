"use client";

import { useCallback, useState } from "react";

import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { cn } from "@/lib/format";

export function DashboardShell({ children }: { readonly children: React.ReactNode }): JSX.Element {
  const [compact, setCompact] = useState<boolean>(false);
  const onToggle = useCallback(() => setCompact((v) => !v), []);

  return (
    <div className={cn("min-h-screen w-full grid grid-cols-[auto_1fr] bg-ink-50 dark:bg-ink-950 text-ink-900 dark:text-ink-100")}>
      <Sidebar compact={compact} />
      <div className="flex min-w-0 flex-col">
        <Topbar compact={compact} onToggleCompact={onToggle} />
        <main className="min-w-0 flex-1 p-4 md:p-6 xl:p-8 space-y-6 animate-fade-in">{children}</main>
      </div>
    </div>
  );
}
