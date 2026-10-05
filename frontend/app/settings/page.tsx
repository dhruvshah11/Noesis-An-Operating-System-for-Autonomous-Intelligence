"use client";

import { useCallback, useEffect, useState } from "react";
import type React from "react";
import {
  BookOpen,
  Copy,
  ExternalLink,
  Eye,
  EyeOff,
  KeyRound,
  Moon,
  Palette,
  Plus,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Sun,
  Trash2,
  Users,
} from "lucide-react";
import { toast } from "sonner";

import { DashboardShell } from "@/components/layout/DashboardShell";
import { cn } from "@/lib/format";

interface ApiKey {
  readonly id: string;
  readonly name: string;
  readonly prefix: string;
  readonly created_at: string;
  readonly last_used: string;
  readonly scopes: readonly string[];
}

interface Provider {
  readonly key: "openai" | "anthropic" | "google" | "ollama" | "openrouter";
  readonly name: string;
  readonly enabled: boolean;
  readonly baseUrl?: string;
  readonly models: readonly string[];
  readonly defaultModel: string;
}

const INITIAL_KEYS: readonly ApiKey[] = [
  { id: "k-1001", name: "CI deploy token", prefix: "sk-ci_", created_at: "2026-04-11", last_used: "2 hours ago", scopes: ["api:read", "api:write"] },
  { id: "k-1002", name: "Docs site search", prefix: "sk-docs_", created_at: "2026-03-22", last_used: "Yesterday", scopes: ["memory:read", "docs:read"] },
  { id: "k-1003", name: "Mobile app staging", prefix: "sk-stg_", created_at: "2026-05-02", last_used: "12 days ago", scopes: ["api:read"] },
] as const;

const INITIAL_PROVIDERS: readonly Provider[] = [
  { key: "ollama", name: "Ollama (local)", enabled: true, baseUrl: "http://localhost:11434", models: ["llama3.1:70b", "qwen2.5:32b", "mistral-nemo:128k"], defaultModel: "llama3.1:70b" },
  { key: "openai", name: "OpenAI", enabled: false, baseUrl: "https://api.openai.com/v1", models: ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"], defaultModel: "gpt-4o" },
  { key: "anthropic", name: "Anthropic", enabled: false, models: ["claude-3-5-sonnet", "claude-3-opus", "claude-3-haiku"], defaultModel: "claude-3-5-sonnet" },
  { key: "google", name: "Google Gemini", enabled: false, models: ["gemini-1.5-pro", "gemini-1.5-flash"], defaultModel: "gemini-1.5-pro" },
  { key: "openrouter", name: "OpenRouter", enabled: false, models: ["router/best", "router/flash", "router/balanced"], defaultModel: "router/best" },
] as const;

type Theme = "light" | "dark" | "system";
type RbacRole = "viewer" | "developer" | "owner" | "auditor";

const RBAC_ROLES: readonly { readonly role: RbacRole; readonly label: string; readonly description: string; readonly tone: "brand" | "emerald" | "amber" | "violet" }[] = [
  { role: "viewer", label: "Viewer", description: "Read-only access to dashboards, conversations, and reports.", tone: "brand" },
  { role: "developer", label: "Developer", description: "Create runs, upload docs, and invoke agents. Cannot manage keys or billing.", tone: "emerald" },
  { role: "owner", label: "Owner", description: "Full workspace admin: billing, RBAC, provider secrets, rotation.", tone: "amber" },
  { role: "auditor", label: "Auditor", description: "Export-only access to audit logs, cost reports, and trace waterfalls.", tone: "violet" },
] as const;

const roleToneChip: Record<(typeof RBAC_ROLES)[number]["tone"], string> = {
  brand: "!border-brand-300 dark:!border-brand-800 !bg-brand-50 dark:!bg-brand-950/40 !text-brand-700 dark:!text-brand-200",
  emerald: "!border-emerald-300 dark:!border-emerald-800 !bg-emerald-50 dark:!bg-emerald-950/40 !text-emerald-700 dark:!text-emerald-200",
  amber: "!border-amber-300 dark:!border-amber-800 !bg-amber-50 dark:!bg-amber-950/40 !text-amber-700 dark:!text-amber-200",
  violet: "!border-violet-300 dark:!border-violet-800 !bg-violet-50 dark:!bg-violet-950/40 !text-violet-700 dark:!text-violet-200",
};

function readCookieTheme(): Theme {
  if (typeof document === "undefined") return "dark";
  const match = /(?:^|;\s*)theme=([^;]+)/.exec(document.cookie);
  const value = match?.[1];
  if (value === "light" || value === "dark" || value === "system") return value;
  return "dark";
}

function writeCookieTheme(theme: Theme): void {
  if (typeof document === "undefined") return;
  document.cookie = `theme=${theme}; path=/; max-age=31536000; SameSite=Lax`;
}

export default function SettingsPage(): React.JSX.Element {
  const [keys, setKeys] = useState<readonly ApiKey[]>(INITIAL_KEYS);
  const [providers, setProviders] = useState<readonly Provider[]>(INITIAL_PROVIDERS);
  const [defaultProvider, setDefaultProvider] = useState<Provider["key"]>("ollama");
  const [theme, setTheme] = useState<Theme>("dark");
  const [accent, setAccent] = useState<string>("brand");
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [mfa, setMfa] = useState<boolean>(true);
  const [sessionTtl, setSessionTtl] = useState<string>("1440");
  const [ipAllowlist, setIpAllowlist] = useState<string>("0.0.0.0/0\n::/0");
  const [rbacRole, setRbacRole] = useState<RbacRole>("owner");

  useEffect(() => {
    setTheme(readCookieTheme());
  }, []);

  const toggleSecret = useCallback((id: string) => {
    setShowSecrets((prev) => ({ ...prev, [id]: !prev[id] }));
  }, []);

  const deleteKey = useCallback((id: string) => {
    setKeys((prev) => prev.filter((k) => k.id !== id));
    toast.success("API key revoked");
  }, []);

  const toggleProvider = useCallback((key: Provider["key"]) => {
    setProviders((prev) => prev.map((p) => (p.key === key ? { ...p, enabled: !p.enabled } : p)));
  }, []);

  const saveAppearance = useCallback(() => {
    writeCookieTheme(theme);
    toast.success(`Appearance saved · theme=${theme}`);
  }, [theme]);

  const saveProviders = useCallback(() => {
    const active = providers.filter((p) => p.enabled).map((p) => p.key).join(", ") || "(none)";
    toast.success(`Providers saved · default=${defaultProvider} · active: ${active}`);
  }, [providers, defaultProvider]);

  const saveSecurity = useCallback(() => {
    toast.success("Security settings saved");
  }, []);

  const saveRbac = useCallback(() => {
    toast.success(`Workspace role saved · acting as ${rbacRole}`);
  }, [rbacRole]);

  return (
    <DashboardShell>
      <header className="flex flex-col gap-1">
        <p className="text-xs uppercase tracking-[0.18em] text-brand-600 dark:text-brand-300 font-semibold">
          Settings
        </p>
        <h1 className="text-2xl font-bold tracking-tight text-ink-950 dark:text-ink-50">
          Workspace settings — keys, providers, appearance and security.
        </h1>
      </header>

      <section aria-labelledby="keys-heading" className="card p-5 animate-fade-in">
        <div className="flex items-start justify-between gap-4 flex-wrap mb-4">
          <div className="flex items-start gap-3">
            <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500/15 to-transparent text-brand-700 dark:text-brand-200">
              <KeyRound className="h-5 w-5" aria-hidden />
            </div>
            <div>
              <h2 id="keys-heading" className="text-sm font-semibold text-ink-950 dark:text-ink-50">
                API keys
              </h2>
              <p className="text-xs text-ink-500 dark:text-ink-400 mt-0.5">
                Manage keys grant programmatic access to AstraOS. Rotate or revoke any time.
              </p>
            </div>
          </div>
          <button type="button" className="btn-primary">
            <Plus className="h-4 w-4" />
            Create key
          </button>
        </div>
        <div className="overflow-hidden rounded-xl border border-ink-200 dark:border-ink-800">
          <table className="w-full text-sm">
            <thead className="bg-ink-50 dark:bg-ink-900/50 text-ink-600 dark:text-ink-300">
              <tr>
                <th className="text-left font-medium px-4 py-3 text-xs">Name</th>
                <th className="text-left font-medium px-4 py-3 text-xs">Prefix</th>
                <th className="text-left font-medium px-4 py-3 text-xs">Scopes</th>
                <th className="text-left font-medium px-4 py-3 text-xs">Created</th>
                <th className="text-left font-medium px-4 py-3 text-xs">Last used</th>
                <th className="text-right font-medium px-4 py-3 text-xs">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100 dark:divide-ink-800">
              {keys.map((k) => (
                <tr key={k.id} className="hover:bg-ink-50/60 dark:hover:bg-ink-900/30 transition">
                  <td className="px-4 py-3 font-medium text-ink-900 dark:text-ink-100">{k.name}</td>
                  <td className="px-4 py-3 font-mono text-xs text-ink-600 dark:text-ink-300">{k.prefix}&hellip;</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {k.scopes.map((s) => (
                        <span key={s} className="chip !bg-ink-100 dark:!bg-ink-900/60">{s}</span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-ink-600 dark:text-ink-300">{k.created_at}</td>
                  <td className="px-4 py-3 text-ink-600 dark:text-ink-300">{k.last_used}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        type="button"
                        className="btn-ghost !px-2 !py-1.5"
                        onClick={() => toggleSecret(k.id)}
                        aria-label={showSecrets[k.id] ? "Hide prefix" : "Show prefix"}
                      >
                        {showSecrets[k.id] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                      <button type="button" className="btn-ghost !px-2 !py-1.5" aria-label="Copy prefix">
                        <Copy className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        className="btn-ghost !px-2 !py-1.5 !text-rose-600 dark:!text-rose-300 hover:!bg-rose-50 dark:hover:!bg-rose-950/40"
                        onClick={() => deleteKey(k.id)}
                        aria-label="Revoke key"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="providers-heading" className="card p-5 animate-fade-in">
        <div className="flex items-start justify-between gap-3 mb-4 flex-wrap">
          <div className="flex items-start gap-3">
            <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500/15 to-transparent text-emerald-700 dark:text-emerald-200">
              <Sparkles className="h-5 w-5" aria-hidden />
            </div>
            <div>
              <h2 id="providers-heading" className="text-sm font-semibold text-ink-950 dark:text-ink-50">
                Model providers
              </h2>
              <p className="text-xs text-ink-500 dark:text-ink-400 mt-0.5">
                Configure LLM backends, model router priority, and per-provider credentials.
              </p>
            </div>
          </div>
          <label className="flex items-center gap-2 text-xs">
            <span className="font-medium text-ink-600 dark:text-ink-300">Default provider</span>
            <select
              value={defaultProvider}
              onChange={(e) => setDefaultProvider(e.target.value as Provider["key"])}
              className="rounded-lg border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-950/50 px-2.5 py-1.5 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-brand-500/60"
            >
              {INITIAL_PROVIDERS.map((p) => (
                <option key={p.key} value={p.key}>{p.name}</option>
              ))}
            </select>
          </label>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {providers.map((p) => (
          <form key={p.key} className="rounded-xl border border-ink-200 dark:border-ink-800 p-4 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold text-ink-950 dark:text-ink-50">{p.name}</p>
                  {defaultProvider === p.key ? (
                    <span className="chip !border-emerald-300 dark:!border-emerald-800 !bg-emerald-50 dark:!bg-emerald-950/40 !text-emerald-700 dark:!text-emerald-200 !text-[10px] !px-1.5 !py-0.5">
                      default
                    </span>
                  ) : null}
                </div>
                <p className="text-xs text-ink-500 dark:text-ink-400 font-mono">{p.key}</p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  className="sr-only peer"
                  checked={p.enabled}
                  onChange={() => toggleProvider(p.key)}
                />
                <div className="w-11 h-6 bg-ink-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-brand-500/60 dark:bg-ink-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-ink-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-brand-600" />
              </label>
            </div>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-ink-600 dark:text-ink-300">API key</span>
              <div className="relative">
                <input
                  type={showSecrets[p.key] ? "text" : "password"}
                  defaultValue={p.enabled && p.key !== "ollama" ? "sk-&hellip;&hellip;&hellip;&hellip;&hellip;" : ""}
                  placeholder={`Paste your ${p.name} key&hellip;`}
                  className="w-full rounded-lg border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-950/50 px-3 py-2 text-sm pr-9 font-mono placeholder:text-ink-400 focus:outline-none focus:ring-2 focus:ring-brand-500/60"
                  autoComplete="off"
                  spellCheck={false}
                />
                <button
                  type="button"
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-ink-400 hover:text-ink-600 dark:hover:text-ink-200"
                  onClick={() => toggleSecret(p.key)}
                  aria-label={`Toggle ${p.name} key visibility`}
                >
                  {showSecrets[p.key] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </label>
            {p.baseUrl !== undefined ? (
              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-ink-600 dark:text-ink-300">Base URL</span>
                <input
                  type="text"
                  defaultValue={p.baseUrl}
                  className="rounded-lg border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-950/50 px-3 py-2 text-sm font-mono placeholder:text-ink-400 focus:outline-none focus:ring-2 focus:ring-brand-500/60"
                />
              </label>
            ) : null}
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-ink-600 dark:text-ink-300">Default model</span>
              <select
                defaultValue={p.defaultModel} className="rounded-lg border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-950/50 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/60">
                {p.models.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </label>
          </form>
        ))}
        </div>
        <div className="mt-4 flex items-center justify-end gap-2">
          <button type="button" className="btn-ghost">Discard</button>
          <button type="button" className="btn-primary" onClick={saveProviders}>Save providers</button>
        </div>
      </section>

      <section aria-labelledby="appearance-heading" className="card p-5 animate-fade-in">
        <div className="flex items-start gap-3 mb-5">
          <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-amber-500/15 to-transparent text-amber-700 dark:text-amber-200">
            <Palette className="h-5 w-5" aria-hidden />
          </div>
          <div>
            <h2 id="appearance-heading" className="text-sm font-semibold text-ink-950 dark:text-ink-50">
              Appearance
            </h2>
            <p className="text-xs text-ink-500 dark:text-ink-400 mt-0.5">
              Theme, accent color, and density preferences for your dashboard (persisted via cookie).
            </p>
          </div>
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <p className="text-xs font-semibold text-ink-700 dark:text-ink-200 mb-2">Theme</p>
            <div className="grid grid-cols-3 gap-2">
              {(["light", "dark", "system"] as const).map((t) => {
                const active = theme === t;
                const Icon = t === "light" ? Sun : t === "dark" ? Moon : Sparkles;
                return (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setTheme(t)}
                    className={cn(
                      "flex flex-col items-center gap-1.5 rounded-xl border p-3 text-xs font-medium transition",
                      active
                        ? "border-brand-500 bg-brand-50 dark:bg-brand-950/40 text-brand-700 dark:text-brand-200"
                        : "border-ink-200 dark:border-ink-800 hover:bg-ink-50 dark:hover:bg-ink-900/40 text-ink-600 dark:text-ink-300",
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    <span className="capitalize">{t}</span>
                  </button>
                );
              })}
            </div>
          </div>
          <div>
            <p className="text-xs font-semibold text-ink-700 dark:text-ink-200 mb-2">Accent color</p>
            <div className="flex flex-wrap gap-2">
              {[
                { key: "brand", swatch: "bg-brand-500" },
                { key: "emerald", swatch: "bg-emerald-500" },
                { key: "amber", swatch: "bg-amber-500" },
                { key: "rose", swatch: "bg-rose-500" },
                { key: "violet", swatch: "bg-violet-500" },
                { key: "cyan", swatch: "bg-cyan-500" },
              ].map((c) => (
                <button
                  key={c.key}
                  type="button"
                  onClick={() => setAccent(c.key)}
                  className={cn(
                    "h-8 w-8 rounded-full border-2 transition",
                    accent === c.key ? "border-ink-950 dark:border-white scale-110" : "border-transparent",
                    c.swatch,
                  )}
                  aria-label={`${c.key} accent`}
                />
              ))}
            </div>
          </div>
          <div className="sm:col-span-2">
            <label className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold text-ink-700 dark:text-ink-200">Compact sidebar density</p>
                <p className="text-xs text-ink-500 dark:text-ink-400 mt-0.5">Reduces padding and icon size on the nav sidebar.</p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" className="sr-only peer" defaultChecked />
                <div className="w-11 h-6 bg-ink-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-brand-500/60 dark:bg-ink-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-ink-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-brand-600" />
              </label>
            </label>
          </div>
        </div>
        <div className="mt-5 flex items-center justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={() => { setTheme("dark"); setAccent("brand"); }}>Reset to defaults</button>
          <button type="button" className="btn-primary" onClick={saveAppearance}>Save appearance</button>
        </div>
      </section>

      <section aria-labelledby="rbac-heading" className="card p-5 animate-fade-in">
        <div className="flex items-start gap-3 mb-5">
          <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500/15 to-transparent text-violet-700 dark:text-violet-200">
            <Users className="h-5 w-5" aria-hidden />
          </div>
          <div>
            <h2 id="rbac-heading" className="text-sm font-semibold text-ink-950 dark:text-ink-50">
              Workspace role (RBAC)
            </h2>
            <p className="text-xs text-ink-500 dark:text-ink-400 mt-0.5">
              Select your active role for this session. Scoped access controls are enforced by the kernel MAC layer.
            </p>
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {RBAC_ROLES.map((r) => {
            const active = rbacRole === r.role;
            return (
              <button
                key={r.role}
                type="button"
                onClick={() => setRbacRole(r.role)}
                className={cn(
                  "rounded-xl border p-4 flex flex-col gap-2 text-left transition",
                  active
                    ? "border-brand-500 bg-brand-50 dark:bg-brand-950/40 ring-2 ring-brand-500/30"
                    : "border-ink-200 dark:border-ink-800 hover:bg-ink-50 dark:hover:bg-ink-900/40",
                )}
              >
                <div className="flex items-center justify-between">
                  <span className={cn("chip !text-[10px] !px-1.5 !py-0.5", roleToneChip[r.tone])}>{r.label}</span>
                  {active ? (
                    <ShieldCheck className="h-4 w-4 text-brand-600 dark:text-brand-300" />
                  ) : (
                    <Shield className="h-4 w-4 text-ink-400" />
                  )}
                </div>
                <p className="text-xs font-semibold text-ink-950 dark:text-ink-50 capitalize mt-1">{r.role}</p>
                <p className="text-[11px] text-ink-500 dark:text-ink-400 leading-relaxed flex-1">{r.description}</p>
              </button>
            );
          })}
        </div>
        <div className="mt-5 flex items-center justify-end gap-2">
          <button type="button" className="btn-ghost">Discard</button>
          <button type="button" className="btn-primary" onClick={saveRbac}>Save role</button>
        </div>
      </section>

      <section aria-labelledby="security-heading" className="card p-5 animate-fade-in">
        <div className="flex items-start gap-3 mb-5">
          <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-rose-500/15 to-transparent text-rose-700 dark:text-rose-200">
            <Shield className="h-5 w-5" aria-hidden />
          </div>
          <div>
            <h2 id="security-heading" className="text-sm font-semibold text-ink-950 dark:text-ink-50">
              Security
            </h2>
            <p className="text-xs text-ink-500 dark:text-ink-400 mt-0.5">
              Authentication, session lifetime and network-level access controls.
            </p>
          </div>
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          <label className="flex items-start justify-between gap-4 rounded-xl border border-ink-200 dark:border-ink-800 p-4">
            <div className="flex items-start gap-3">
              {mfa ? (
                <ShieldCheck className="h-5 w-5 text-emerald-600 dark:text-emerald-300 mt-0.5" />
              ) : (
                <ShieldAlert className="h-5 w-5 text-amber-600 dark:text-amber-300 mt-0.5" />
              )}
              <div>
                <p className="text-sm font-semibold text-ink-950 dark:text-ink-50">Two-factor authentication</p>
                <p className="text-xs text-ink-500 dark:text-ink-400 mt-0.5">
                  Require a time-based one-time password on every login.
                </p>
              </div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer mt-0.5">
              <input
                type="checkbox"
                className="sr-only peer"
                checked={mfa}
                onChange={(e) => setMfa(e.target.checked)}
              />
              <div className="w-11 h-6 bg-ink-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-brand-500/60 dark:bg-ink-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-ink-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-brand-600" />
            </label>
          </label>

          <label className="flex flex-col gap-1.5 rounded-xl border border-ink-200 dark:border-ink-800 p-4">
            <p className="text-sm font-semibold text-ink-950 dark:text-ink-50">Session TTL (minutes)</p>
            <p className="text-xs text-ink-500 dark:text-ink-400">Idle sessions expire after this many minutes of inactivity.</p>
            <input
              type="number"
              min={5}
              step={5}
              value={sessionTtl}
              onChange={(e) => setSessionTtl(e.target.value)}
              className="mt-1 rounded-lg border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-950/50 px-3 py-2 text-sm tabular-nums focus:outline-none focus:ring-2 focus:ring-brand-500/60"
            />
          </label>

          <label className="flex flex-col gap-1.5 rounded-xl border border-ink-200 dark:border-ink-800 p-4 sm:col-span-2">
            <p className="text-sm font-semibold text-ink-950 dark:text-ink-50">IP allowlist (CIDR)</p>
            <p className="text-xs text-ink-500 dark:text-ink-400">
              One CIDR block per line. Leave 0.0.0.0/0 and ::/0 to allow any address.
            </p>
            <textarea
              rows={4}
              value={ipAllowlist}
              onChange={(e) => setIpAllowlist(e.target.value)}
              className="mt-1 rounded-lg border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-950/50 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500/60"
            />
          </label>

          <div className="rounded-xl border border-ink-200 dark:border-ink-800 p-4 sm:col-span-2">
            <p className="text-sm font-semibold text-ink-950 dark:text-ink-50">Active sessions</p>
            <p className="text-xs text-ink-500 dark:text-ink-400 mt-0.5 mb-3">
              Signed-in browsers and service tokens currently allowed access to this workspace.
            </p>
            <div className="divide-y divide-ink-100 dark:divide-ink-800 rounded-lg border border-ink-100 dark:border-ink-800 overflow-hidden text-sm">
              {[
                { device: "Chrome \u00b7 Windows", loc: "Bengaluru, IN", ip: "103.25.110.14", when: "Current session" },
                { device: "Safari \u00b7 macOS", loc: "Singapore, SG", ip: "18.136.24.9", when: "2 hours ago" },
                { device: "GitHub Actions runner", loc: "us-east-1", ip: "3.234.11.88", when: "Yesterday" },
              ].map((s, i) => (
                <div key={i} className="px-3 py-2.5 flex items-center justify-between gap-3">
                  <div>
                    <p className="text-ink-800 dark:text-ink-100 font-medium">{s.device}</p>
                    <p className="text-xs text-ink-500 dark:text-ink-400 font-mono">{s.loc} \u00b7 {s.ip}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={cn("chip", i === 0 && "!border-emerald-300 !bg-emerald-50 dark:!border-emerald-800 dark:!bg-emerald-950/40 !text-emerald-700 dark:!text-emerald-200")}>{s.when}</span>
                    {i !== 0 ? <button type="button" className="btn-ghost !px-2.5 !py-1.5 text-xs">Revoke</button> : null}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="mt-5 flex items-center justify-end gap-2">
          <button type="button" className="btn-ghost">Cancel</button>
          <button type="button" className="btn-primary" onClick={saveSecurity}>Save security</button>
        </div>
      </section>

      <section aria-labelledby="openapi-heading" className="card p-5 animate-fade-in">
        <div className="flex items-start justify-between gap-3 mb-4 flex-wrap">
          <div className="flex items-start gap-3">
            <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500/15 to-transparent text-cyan-700 dark:text-cyan-200">
              <BookOpen className="h-5 w-5" aria-hidden />
            </div>
            <div>
              <h2 id="openapi-heading" className="text-sm font-semibold text-ink-950 dark:text-ink-50">
                OpenAPI reference
              </h2>
              <p className="text-xs text-ink-500 dark:text-ink-400 mt-0.5">
                Interactive Swagger UI for the Noesis kernel v1 REST surface. Try endpoints directly from the dashboard.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a
              href="/openapi.json"
              target="_blank"
              rel="noopener noreferrer"
              className="btn-ghost !px-2.5 !py-1.5 text-xs inline-flex items-center gap-1"
            >
              <ExternalLink className="h-3.5 w-3.5" /> openapi.json
            </a>
          </div>
        </div>
        <div className="rounded-xl overflow-hidden border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-950">
          <div className="relative w-full" style={{ height: "640px" }}>
            <iframe
              src="/docs"
              title="OpenAPI Swagger reference"
              className="w-full h-full border-0 bg-white dark:bg-white"
              sandbox="allow-same-origin allow-scripts allow-forms allow-popups"
              onError={(e) => {
                e.currentTarget.style.display = "none";
              }}
            >
              <div className="p-8 text-center text-sm text-ink-500 dark:text-ink-400">
                <BookOpen className="h-10 w-10 mx-auto mb-3 opacity-50" />
                <p className="font-medium text-ink-700 dark:text-ink-200 mb-1">Swagger UI unavailable inline</p>
                <p>
                  Open the interactive reference at{" "}
                  <a href="/docs" className="underline text-brand-600 dark:text-brand-300">/docs</a>
                  {" "}or download the raw spec from{" "}
                  <a href="/openapi.json" className="underline text-brand-600 dark:text-brand-300">/openapi.json</a>.
                </p>
              </div>
            </iframe>
          </div>
        </div>
      </section>
    </DashboardShell>
  );
}
