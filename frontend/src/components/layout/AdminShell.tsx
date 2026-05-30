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
  DollarSign,
} from "lucide-react";
import { AppShell } from "./AppShell";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";

// Admin sub-nav. `perm` gates visibility (same can() rules as the main sidebar).
const ADMIN_NAV = [
  { label: "Admin Home", href: "/admin", icon: LayoutDashboard, perm: "admin:users:read" },
  { label: "Users", href: "/admin/users", icon: Users, perm: "admin:users:read" },
  { label: "Roles", href: "/admin/roles", icon: Lock, perm: "admin:roles:read" },
  { label: "LLM Providers", href: "/admin/llm-settings", icon: BrainCircuit, perm: "admin:llm:read" },
  { label: "Agent Model Mapping", href: "/admin/agent-mapping", icon: Network, perm: "admin:llm:read" },
  { label: "Cost Limits", href: "/admin/cost-limits", icon: DollarSign, perm: "admin:llm:read" },
  { label: "Notifications", href: "/admin/notifications", icon: Bell, perm: "admin:llm:read" },
  { label: "Email / SMTP", href: "/admin/email", icon: Mail, perm: "admin:llm:read" },
  { label: "Connector Management", href: "/admin/connectors", icon: Plug, perm: "admin:llm:read" },
  { label: "Custom Connectors", href: "/admin/custom-connectors", icon: Wrench, perm: "admin:llm:read" },
  { label: "System Health", href: "/admin/system-health", icon: HeartPulse, adminOnly: true },
  { label: "Audit Logs", href: "/admin/audit-logs", icon: ScrollText, perm: "admin:audit:read" },
  { label: "Import / Export", href: "/admin/import-export", icon: Upload, perm: "admin:audit:read" },
];

interface Props {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  actions?: React.ReactNode;
  /** Current page label, used for the "Admin > <page>" breadcrumb. Falls back
   * to the matching nav item's label. */
  page?: string;
}

export function AdminShell({ children, title, subtitle, actions, page }: Props) {
  const pathname = usePathname() || "";
  const { can, role, isSuperAdmin } = useAuth();
  const isAdmin = isSuperAdmin || role === "admin";
  const items = ADMIN_NAV.filter((i) => (i.adminOnly ? isAdmin : (!i.perm || can(i.perm))));

  const isActive = (href: string) =>
    href === "/admin" ? pathname === "/admin" : pathname.startsWith(href);

  // Breadcrumb: Helix > Admin > <page>. Derive the leaf from `page`, else the
  // active nav item, else the title.
  const leaf = page || ADMIN_NAV.find((i) => isActive(i.href) && i.href !== "/admin")?.label || title;
  const crumbs = leaf && leaf !== "Admin"
    ? [{ label: "Admin", href: "/admin" }, { label: leaf }]
    : [{ label: "Admin" }];

  return (
    <AppShell title={title} subtitle={subtitle} actions={actions} crumbs={crumbs}>
      <div className="grid grid-cols-1 lg:grid-cols-[210px_1fr] gap-6">
        {/* Sticky admin sub-nav — quick switching between admin features. */}
        <aside className="hidden lg:block">
          <nav aria-label="Administration" className="sticky top-[64px] rounded-xl border border-hx bg-surface p-1.5">
            {items.map((item) => {
              const Icon = item.icon;
              const active = isActive(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-[12.5px] transition-colors",
                    active
                      ? "bg-[var(--con-brand-soft)] text-[var(--con-brand)] font-medium"
                      : "text-ink-3 hover:bg-app-2 hover:text-ink-2"
                  )}
                >
                  <Icon aria-hidden className={cn("h-[15px] w-[15px] flex-shrink-0", active ? "text-[var(--con-brand)]" : "text-ink-4")} />
                  <span className="truncate">{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </aside>

        {/* Mobile admin nav — horizontal scroll row */}
        <nav aria-label="Administration" className="lg:hidden -mx-1 flex gap-1.5 overflow-x-auto pb-1">
          {items.map((item) => {
            const active = isActive(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "whitespace-nowrap px-3 py-1.5 rounded-lg text-[12.5px] border transition-colors",
                  active ? "border-[var(--con-brand)] bg-[var(--con-brand-soft)] text-[var(--con-brand)]" : "border-hx-2 bg-surface text-ink-3"
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="min-w-0 space-y-4">{children}</div>
      </div>
    </AppShell>
  );
}
