"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
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
  Mail,
} from "lucide-react";
import { AppShell } from "./AppShell";
import { cn } from "@/lib/utils";

const ADMIN_NAV = [
  { label: "Admin Dashboard", href: "/admin", icon: LayoutDashboard },
  { label: "Users", href: "/admin/users", icon: Users },
  { label: "Roles", href: "/admin/roles", icon: Lock },
  { label: "LLM Providers", href: "/admin/llm-settings", icon: BrainCircuit },
  { label: "Agent Model Mapping", href: "/admin/agent-mapping", icon: Network },
  { label: "Connector Management", href: "/admin/connectors", icon: Plug },
  { label: "Custom Connectors", href: "/admin/custom-connectors", icon: Wrench },
  { label: "System Health", href: "/admin/system-health", icon: HeartPulse },
  { label: "Audit Logs", href: "/admin/audit-logs", icon: ScrollText },
  { label: "Notifications", href: "/admin/notifications", icon: Bell },
  { label: "Email / SMTP", href: "/admin/email", icon: Mail },
  { label: "Import / Export", href: "/admin/import-export", icon: Upload },
];

interface Props {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

export function AdminShell({ children, title, subtitle, actions }: Props) {
  const pathname = usePathname() || "";
  return (
    <AppShell title={title} subtitle={subtitle} actions={actions} crumbs={[{ label: "Admin" }]}>
      <div className="grid grid-cols-12 gap-6">
        <aside className="col-span-12 lg:col-span-3 xl:col-span-2">
          <nav aria-label="Administration" className="rounded-2xl border border-hx bg-surface p-2 shadow-xs">
            {ADMIN_NAV.map((item) => {
              const Icon = item.icon;
              const active = item.href === "/admin" ? pathname === "/admin" : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] transition-colors",
                    active ? "bg-helix-50 text-helix-800 font-medium" : "text-ink-3 hover:bg-zinc-50"
                  )}
                >
                  <Icon aria-hidden className={cn("h-4 w-4", active ? "text-helix-600" : "text-ink-4")} />
                  <span className="truncate">{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </aside>
        <div className="col-span-12 lg:col-span-9 xl:col-span-10 space-y-6">{children}</div>
      </div>
    </AppShell>
  );
}
