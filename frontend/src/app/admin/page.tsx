import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Admin · Helix" };
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
} from "lucide-react";
import { AdminShell } from "@/components/layout";
import { Card, Chip, MetricCard } from "@/components/ui";

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
  { href: "/admin/roles", icon: Lock, label: "Roles", desc: "Configure RBAC roles and permissions.", comingSoon: true },
  { href: "/admin/llm-settings", icon: BrainCircuit, label: "LLM Providers", desc: "OpenAI · Claude · Gemini · local." },
  { href: "/admin/agent-mapping", icon: Network, label: "Agent Model Mapping", desc: "Route agents to providers and models." },
  { href: "/admin/connectors", icon: Plug, label: "Connector Management", desc: "First-party connector status & config.", comingSoon: true },
  { href: "/admin/custom-connectors", icon: Wrench, label: "Custom Connectors", desc: "Pluggable connector SDK & deployments.", comingSoon: true },
  { href: "/admin/system-health", icon: HeartPulse, label: "System Health", desc: "Backend, DB, Redis, Temporal, worker." },
  { href: "/admin/audit-logs", icon: ScrollText, label: "Audit Logs", desc: "Security and activity events." },
  { href: "/admin/notifications", icon: Bell, label: "Notifications", desc: "Alert rules and delivery channels.", comingSoon: true },
  { href: "/admin/import-export", icon: Upload, label: "Import / Export", desc: "Projects, plans, configurations.", comingSoon: true },
];

export default function AdminHomePage() {
  return (
    <AdminShell
      title="Admin"
      subtitle="Platform configuration, security, governance, and observability."
    >
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <MetricCard label="USERS" value="24" delta={4} spark={[20, 22, 22, 23, 24]} />
        <MetricCard label="LLM PROVIDERS" value="7" deltaLabel="active" />
        <MetricCard label="SYSTEM HEALTH" value="OK" deltaLabel="all components" />
        <MetricCard label="AUDIT EVENTS / DAY" value="1.2K" delta={3.4} spark={[900, 1000, 1100, 1150, 1200]} />
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
