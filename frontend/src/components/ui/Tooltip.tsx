"use client";

import { type ReactNode, useRef, useState } from "react";
import { cn } from "@/lib/format";

export interface TooltipProps {
  readonly content: ReactNode;
  readonly children: ReactNode;
  readonly side?: "top" | "bottom" | "left" | "right";
  readonly className?: string;
  readonly gradient?: boolean;
}

export function Tooltip({
  content,
  children,
  side = "top",
  className,
  gradient = false,
}: TooltipProps): JSX.Element {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLSpanElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  const sideClasses: Record<NonNullable<TooltipProps["side"]>, string> = {
    top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
    bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
    left: "right-full top-1/2 -translate-y-1/2 mr-2",
    right: "left-full top-1/2 -translate-y-1/2 ml-2",
  };

  const arrowClasses: Record<NonNullable<TooltipProps["side"]>, string> = {
    top: "top-full left-1/2 -translate-x-1/2 border-t-[#6E56CF]/80",
    bottom: "bottom-full left-1/2 -translate-x-1/2 border-b-[#6E56CF]/80",
    left: "left-full top-1/2 -translate-y-1/2 border-l-[#6E56CF]/80",
    right: "right-full top-1/2 -translate-y-1/2 border-r-[#6E56CF]/80",
  };

  const gradientBg = gradient
    ? "bg-gradient-to-r from-[#6E56CF]/90 via-[#22c55e]/85 to-[#06b6d4]/75 text-white border-transparent"
    : "bg-[rgb(var(--surface))] border-[rgb(var(--border))] text-ink-800 dark:text-ink-100";

  return (
    <span
      ref={triggerRef}
      className="relative inline-flex"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      {children}
      {open && (
        <div
          ref={tooltipRef}
          role="tooltip"
          className={cn(
            "pointer-events-none absolute z-50 whitespace-nowrap rounded-lg border px-2.5 py-1.5 text-xs font-medium shadow-lg animate-fade-in",
            sideClasses[side],
            gradientBg,
            className,
          )}
        >
          {content}
          <span
            className={cn(
              "absolute h-2 w-2 rotate-45 border border-r-0 border-b-0",
              arrowClasses[side],
              gradient ? "opacity-90" : "bg-[rgb(var(--surface))]",
            )}
          />
        </div>
      )}
    </span>
  );
}
