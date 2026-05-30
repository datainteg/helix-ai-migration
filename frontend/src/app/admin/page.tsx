"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Users,
  Lock,
  BrainCircuit,
  Network,
  Plug,
  Wrench,
  HeartPulse,
  ScrollText,
  Bell,
  Upload,
  DollarSign,
  Mail,
} from "lucide-react";
import { AdminShell } from "@/components/layout";
import { Card, Chip, MetricCard } from "@/components/ui";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface Tile {
  href: string;
  icon: typeof Users;
  label: string;
  desc: string;
  /** When true, tile is non-navigable and shown with a "Coming soon" chip. */
  comingSoon?: boolean;
}

const TILES: Tile[] = [
  { href: "/admin/users", icon: Users, label: "Users", desc: "Manage accounts, invites, and access." },
  { href: "/admin/roles", icon: Lock, label: "Roles", desc: "Built-in RBAC roles and permissions." },
  { href: "/admin/llm-settings", icon: BrainCircuit, label: "LLM Providers", desc: "OpenAI · Claude · Gemini · local." },
  { href: "/admin/agent-mapping", icon: Network, label: "Agent Model Mapping", desc: "Route agents to providers and models." },
  { href: "/admin/cost-limits", icon: DollarSign, label: "Cost Limits", desc: "Per-org daily & monthly LLM spend caps." },
  { href: "/admin/email", icon: Mail, label: "Email / SMTP", desc: "Mail transport setup + test connection." },
  { href: "/admin/connectors", icon: Plug, label: "Connector Management", desc: "Supported connectors & capabilities." },
  { href: "/admin/custom-connectors", icon: Wrench, label: "Custom Connectors", desc: "Pluggable connector SDK & deployments." },
  { href: "/admin/system-health", icon: HeartPulse, label: "System Health", desc: "Backend, DB, Redis, Temporal, worker." },
  { href: "/admin/audit-logs", icon: ScrollText, label: "Audit Logs", desc: "Security and activity events." },
  { href: "/admin/notifications", icon: Bell, label: "Notifications", desc: "Alert rules and delivery channels." },
  { href: "/admin/import-export", icon: Upload, label: "Import / Export", desc: "Data exports; project bundles planned." },
];

// Em dash placeholder while loading or when a metric is unavailable (e.g. the
// caller lacks permission for the endpoint). We never fabricate a number.
const DASH = "—";

export default function AdminHomePage() {
  // Real headline metrics — each sourced from a backend endpoint that exists
  // (confirmed against /openapi.json). null = still loading or unavailable; we
  // render "—" rather than any placeholder value.
  const [userCount, setUserCount] = useState<number | null>(null);
  const [providerCount, setProviderCount] = useState<number | null>(null);
  const [health, setHealth] = useState<{ status: string; total: number } | null>(null);
  const [auditCount, setAuditCount] = useState<number | null>(null);

  useEffect(() => {
    // SC-010: auth via the HttpOnly cookie (credentials:"include").

    // Users — only the superadmin roster endpoint can return a count; a regular
    // admin gets 403, in which case we leave "—" rather than guess.
    fetch(`${API_BASE}/api/v1/superadmin/users`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((rows) => { if (Array.isArray(rows)) setUserCount(rows.length); })
      .catch(() => {});

    // LLM providers — count of configured providers for the active org.
    fetch(`${API_BASE}/api/v1/llm-providers`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((rows) => { if (Array.isArray(rows)) setProviderCount(rows.length); })
      .catch(() => {});

    // System health — overall status + number of components reporting.
    fetch(`${API_BASE}/api/v1/system/health`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d) => {
        if (d?.status) setHealth({ status: String(d.status), total: Array.isArray(d.components) ? d.components.length : 0 });
      })
      .catch(() => {});

    // Audit — count of the most recent events (no per-day aggregation endpoint
    // exists, so we report the recent-event count honestly rather than a rate).
    fetch(`${API_BASE}/api/v1/audit-logs?limit=500`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((rows) => { if (Array.isArray(rows)) setAuditCount(rows.length); })
      .catch(() => {});
  }, []);

  const healthValue = health ? (health.status === "ok" ? "OK" : health.status.replace(/\b\w/g, (c) => c.toUpperCase())) : DASH;

  return (
    <AdminShell
      title="Admin"
      subtitle="Platform configuration, security, governance, and observability."
    >
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <MetricCard label="USERS" value={userCount ?? DASH} />
        <MetricCard
          label="LLM PROVIDERS"
          value={providerCount ?? DASH}
          deltaLabel={providerCount !== null ? "configured" : undefined}
        />
        <MetricCard
          label="SYSTEM HEALTH"
          value={healthValue}
          accent={health && health.status !== "ok" ? "var(--con-err)" : undefined}
          deltaLabel={health && health.total > 0 ? `${health.total} components` : undefined}
        />
        <MetricCard
          label="RECENT AUDIT EVENTS"
          value={auditCount ?? DASH}
          deltaLabel={auditCount !== null ? "latest" : undefined}
        />
      </div>

      <Card title="Quick access" description="Most-used administration surfaces.">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {TILES.map((t) => {
            const Icon = t.icon;
            const body = (
              <div className="flex items-start gap-3">
                <div className="grid place-items-center h-9 w-9 rounded-lg bg-[var(--con-brand-soft)] text-[var(--con-brand)] flex-shrink-0">
                  <Icon className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <div className="text-[13.5px] font-semibold text-ink">{t.label}</div>
                    {t.comingSoon && <Chip tone="default">Coming soon</Chip>}
                  </div>
                  <div className="text-[12px] text-ink-3 mt-0.5">{t.desc}</div>
                </div>
              </div>
            );
            if (t.comingSoon) {
              return (
                <div
                  key={t.href}
                  aria-disabled="true"
                  className="rounded-[10px] border border-hx bg-surface p-4 opacity-60 cursor-default"
                >
                  {body}
                </div>
              );
            }
            return (
              <Link
                key={t.href}
                href={t.href}
                className="group rounded-[10px] border border-hx bg-surface p-4 hover:bg-surface-hi hover:border-hx-2 transition-colors"
              >
                {body}
              </Link>
            );
          })}
        </div>
      </Card>
    </AdminShell>
  );
}
