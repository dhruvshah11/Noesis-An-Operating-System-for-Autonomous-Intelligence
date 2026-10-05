"use client";

import { type ReactNode, useState } from "react";
import { Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/format";

export interface CodeBlockProps {
  readonly code: string;
  readonly language?: string;
  readonly filename?: string;
  readonly children?: ReactNode;
  readonly className?: string;
}

export function CodeBlock({
  code,
  language,
  filename,
  children,
  className,
}: CodeBlockProps): JSX.Element {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (): Promise<void> => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  const textContent = children && typeof children === "string" ? children : code;

  return (
    <div className={cn("relative group rounded-xl border border-ink-200 dark:border-ink-800 overflow-hidden", className)}>
      {(Boolean(filename) || Boolean(language)) && (
        <div className="flex items-center justify-between px-3 py-2 bg-ink-50 dark:bg-ink-900/50 border-b border-ink-200 dark:border-ink-800">
          <div className="flex items-center gap-2">
            {filename && (
              <span className="text-xs font-medium text-ink-700 dark:text-ink-300 font-mono">
                {filename}
              </span>
            )}
            {language && (
              <span className="text-[10px] uppercase tracking-wider text-ink-500 dark:text-ink-400">
                {language}
              </span>
            )}
          </div>
        </div>
      )}
      <div className="relative">
        <pre className="p-4 overflow-x-auto text-xs font-mono text-ink-800 dark:text-ink-200 bg-white dark:bg-ink-950/60">
          <code>{textContent}</code>
        </pre>
        <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={() => { void handleCopy(); }}
            aria-label={copied ? "Copied!" : "Copy to clipboard"}
          >
            {copied ? (
              <Check className="h-3.5 w-3.5 text-emerald-600" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
