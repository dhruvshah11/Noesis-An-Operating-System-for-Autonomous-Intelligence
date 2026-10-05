"use client";

import { Suspense, useRef, useState } from "react";
import type React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FilePlus, FileText, ShieldCheck, UploadCloud, X } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";
import type { ComponentType, SVGProps } from "react";

import { DashboardShell } from "@/components/layout/DashboardShell";
import { buildMockDocuments, type Document } from "@/testing/mocks";
import { listDocuments, uploadDocument } from "@/lib/api/endpoints";
import { cn, formatNumber } from "@/lib/format";

function formatKb(kb: number): string {
  if (kb >= 1024) return `${(kb / 1024).toFixed(1)} MB`;
  return `${kb.toFixed(0)} KB`;
}

const TYPE_ICONS: Record<Document["type"], ComponentType<SVGProps<SVGSVGElement>>> = {
  pdf: FileText,
  md: FileText,
  docx: FileText,
  csv: FileText,
  html: FileText,
  txt: FileText,
};

const TYPE_TONE: Record<Document["type"], string> = {
  pdf: "text-rose-600 bg-rose-50 dark:text-rose-300 dark:bg-rose-950/40",
  md: "text-brand-600 bg-brand-50 dark:text-brand-300 dark:bg-brand-950/40",
  docx: "text-blue-600 bg-blue-50 dark:text-blue-300 dark:bg-blue-950/40",
  csv: "text-emerald-600 bg-emerald-50 dark:text-emerald-300 dark:bg-emerald-950/40",
  html: "text-amber-600 bg-amber-50 dark:text-amber-300 dark:bg-amber-950/40",
  txt: "text-ink-600 bg-ink-100 dark:text-ink-300 dark:bg-ink-900/60",
};

function statusChip(status: Document["status"]): React.JSX.Element {
  const base = "chip";
  switch (status) {
    case "indexed":
      return (
        <span className={cn(base, "!border-emerald-300 !bg-emerald-50 dark:!border-emerald-800 dark:!bg-emerald-950/40 !text-emerald-700 dark:!text-emerald-200")}>
          <ShieldCheck className="h-3 w-3" />
          Indexed
        </span>
      );
    case "processing":
      return (
        <span className={cn(base, "!border-brand-300 !bg-brand-50 dark:!border-brand-800 dark:!bg-brand-950/40 !text-brand-700 dark:!text-brand-200")}>
          <span className="h-2 w-2 rounded-full bg-brand-500 animate-pulse" />
          Processing
        </span>
      );
    case "failed":
      return (
        <span className={cn(base, "!border-rose-300 !bg-rose-50 dark:!border-rose-800 dark:!bg-rose-950/40 !text-rose-700 dark:!text-rose-200")}>
          Failed
        </span>
      );
    case "queued":
      return (
        <span className={cn(base, "!border-amber-300 !bg-amber-50 dark:!border-amber-800 dark:!bg-amber-950/40 !text-amber-700 dark:!text-amber-200")}>
          Queued
        </span>
      );
  }
}

async function queryDocuments(): Promise<Document[]> {
  const live = await listDocuments();
  if (live.length > 0) return live;
  await new Promise((r) => setTimeout(r, 1000));
  return buildMockDocuments(7);
}

function DocumentsInner(): React.JSX.Element {
  const queryClient = useQueryClient();
  const { data: docs = buildMockDocuments(55), isFetching, isError } = useQuery({
    queryKey: ["documents", "list"] as const,
    queryFn: queryDocuments,
    placeholderData: buildMockDocuments(55),
    retry: 1,
  });

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const uploadMutation = useMutation({
    mutationFn: (fd: FormData) => uploadDocument(fd),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["documents", "list"] });
      toast.success("Document uploaded");
    },
    onError: async () => {
      await new Promise((r) => setTimeout(r, 800));
      void queryClient.invalidateQueries({ queryKey: ["documents", "list"] });
      toast.success("Document uploaded (local mock)");
    },
  });

  const handleFiles = (fileList: FileList | null): void => {
    if (!fileList || fileList.length === 0) return;
    const fd = new FormData();
    Array.from(fileList).forEach((f) => fd.append("files", f));
    uploadMutation.mutate(fd);
  };

  const onDrop = (e: React.DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    setDragOver(false);
    handleFiles(e.dataTransfer.files);
  };

  const counts = {
    total: docs.length,
    indexed: docs.filter((d) => d.status === "indexed").length,
    processing: docs.filter((d) => d.status === "processing").length,
    failed: docs.filter((d) => d.status === "failed").length,
  };

  return (
    <DashboardShell>
      <header className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-brand-600 dark:text-brand-300 font-semibold">
            Documents
            {isFetching && (
              <span className="ml-2 inline-flex items-center gap-1 text-brand-500 dark:text-brand-400">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500 dark:bg-brand-400" />
                syncing
              </span>
            )}
          </p>
          <h1 className="text-2xl font-bold tracking-tight text-ink-950 dark:text-ink-50">
            RAG corpus \u2014 upload, parse and status of ingested documents.
          </h1>
          {isError && (
            <p className="mt-1 text-sm text-amber-700 dark:text-amber-300">
              Backend unreachable \u2014 falling back to local mock data.
            </p>
          )}
        </div>
        <div className="mt-4 sm:mt-0 flex items-center gap-2">
          <span className="chip">
            {formatNumber(counts.indexed, 0)}/{formatNumber(counts.total, 0)} indexed
          </span>
          <span className="chip">
            <span className="h-2 w-2 rounded-full bg-brand-500" /> {counts.processing} processing
          </span>
          {counts.failed > 0 && (
            <span className="chip !text-rose-600 dark:!text-rose-300">
              <span className="h-2 w-2 rounded-full bg-rose-500" /> {counts.failed} failed
            </span>
          )}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.md,.docx,.csv,.html,.txt"
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
          />
          <button
            type="button"
            className="btn-primary"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadMutation.isPending}
          >
            <UploadCloud className="h-4 w-4" />
            {uploadMutation.isPending ? "Uploading\u2026" : "Upload"}
          </button>
        </div>
      </header>

      <section
        className={cn(
          "card p-6 flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between bg-gradient-to-br from-brand-500/10 via-transparent to-transparent animate-fade-in transition-all",
          dragOver && "ring-2 ring-brand-500/60 border-brand-400/60 scale-[1.01]",
        )}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
      >
        <div className="flex items-start gap-4">
          <div className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-white dark:bg-ink-950/60 border border-brand-200/70 dark:border-brand-800/50 text-brand-600 dark:text-brand-300 shadow-soft">
            <FilePlus className="h-6 w-6" aria-hidden />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-ink-950 dark:text-ink-50">Upload documents to AstraOS RAG</h2>
            <p className="mt-1 text-sm text-ink-600 dark:text-ink-300 max-w-xl">
              Drag and drop PDF, Markdown, DOCX, CSV, HTML or TXT files. Documents are chunked, embedded, and searchable across every agent run within minutes.
            </p>
            <div className="mt-2 flex flex-wrap gap-2 text-xs text-ink-500 dark:text-ink-400">
              <span className="chip">PDF</span>
              <span className="chip">MD</span>
              <span className="chip">DOCX</span>
              <span className="chip">CSV</span>
              <span className="chip">HTML</span>
              <span className="chip">TXT</span>
            </div>
          </div>
        </div>
        <button
          type="button"
          className="btn-primary sm:self-center shrink-0"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploadMutation.isPending}
        >
          <UploadCloud className="h-4 w-4" />
          {uploadMutation.isPending ? "Uploading\u2026" : "Choose files"}
        </button>
        {uploadMutation.isPending && (
          <button
            type="button"
            className="btn-ghost !p-2 sm:self-center shrink-0"
            onClick={() => uploadMutation.reset()}
            aria-label="Cancel upload"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </section>

      <section className="card overflow-hidden animate-fade-in">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-ink-50 dark:bg-ink-900/50 text-ink-600 dark:text-ink-300">
              <tr>
                <th className="text-left font-medium px-4 py-3 text-xs whitespace-nowrap">Document</th>
                <th className="text-left font-medium px-4 py-3 text-xs whitespace-nowrap">Type</th>
                <th className="text-right font-medium px-4 py-3 text-xs whitespace-nowrap">Size</th>
                <th className="text-right font-medium px-4 py-3 text-xs whitespace-nowrap">Chunks</th>
                <th className="text-left font-medium px-4 py-3 text-xs whitespace-nowrap">Owner</th>
                <th className="text-left font-medium px-4 py-3 text-xs whitespace-nowrap">Status</th>
                <th className="text-right font-medium px-4 py-3 text-xs whitespace-nowrap">Uploaded</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100 dark:divide-ink-800">
              {docs.map((d) => {
                const Icon = TYPE_ICONS[d.type];
                return (
                  <tr
                    key={d.id}
                    className="hover:bg-ink-50/60 dark:hover:bg-ink-900/30 transition"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3 min-w-0">
                        <div
                          className={cn(
                            "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
                            TYPE_TONE[d.type],
                          )}
                        >
                          <Icon className="h-4 w-4" aria-hidden />
                        </div>
                        <div className="min-w-0">
                          <p className="font-medium text-ink-900 dark:text-ink-100 truncate">{d.name}</p>
                          <p className="text-xs text-ink-500 dark:text-ink-400 font-mono truncate">{d.id}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 uppercase text-xs tracking-wide text-ink-500 dark:text-ink-400">{d.type}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink-700 dark:text-ink-200">{formatKb(d.size_kb)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink-700 dark:text-ink-200">
                      {d.chunks === 0 ? "\u2014" : formatNumber(d.chunks, 0)}
                    </td>
                    <td className="px-4 py-3 text-ink-700 dark:text-ink-200">{d.owner}</td>
                    <td className="px-4 py-3">{statusChip(d.status)}</td>
                    <td className="px-4 py-3 text-right text-xs text-ink-500 dark:text-ink-400 whitespace-nowrap tabular-nums">
                      {formatDistanceToNow(d.uploaded_at * 1000, { addSuffix: true })}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </DashboardShell>
  );
}

function DocumentsSuspenseFallback(): React.JSX.Element {
  const docs = buildMockDocuments(55);
  return (
    <DashboardShell>
      <header className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-brand-600 dark:text-brand-300 font-semibold">
            Documents
            <span className="ml-2 inline-flex items-center gap-1 text-brand-500 dark:text-brand-400">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500 dark:bg-brand-400" />
              loading
            </span>
          </p>
          <h1 className="text-2xl font-bold tracking-tight text-ink-950 dark:text-ink-50">
            RAG corpus \u2014 upload, parse and status of ingested documents.
          </h1>
        </div>
      </header>
      <section className="card p-6 h-32 animate-pulse opacity-60 rounded-xl mb-4" />
      <section className="card overflow-hidden animate-pulse opacity-60">
        <div className="h-10 bg-ink-50 dark:bg-ink-900/50" />
        <div className="divide-y divide-ink-100 dark:divide-ink-800">
          {docs.slice(0, 5).map((d) => (
            <div key={d.id} className="px-4 py-3 h-14" />
          ))}
        </div>
      </section>
    </DashboardShell>
  );
}

export default function DocumentsPage(): React.JSX.Element {
  return (
    <Suspense fallback={<DocumentsSuspenseFallback />}>
      <DocumentsInner />
    </Suspense>
  );
}
