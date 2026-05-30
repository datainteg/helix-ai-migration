"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import {
  LayoutDashboard,
  FolderKanban,
  Bot,
  ShieldCheck,
  GitCompareArrows,
  TerminalSquare,
  Plug,
  FileText,
  FolderUp,
  LayoutTemplate,
  Puzzle,
  Settings,
  Search,
  DollarSign,
  X,
} from "lucide-react";
import { HelixWordmark } from "./HelixLogo";
import { Avatar } from "@/components/ui/Avatar";
import { Kbd } from "@/components/ui/Kbd";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";

type NavItem = {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  count?: number;
  live?: boolean;
  shortcut?: string;
};

const PRIMARY: NavItem[] = [
  { label: "Command Center",     href: "/dashboard",            icon: LayoutDashboard, shortcut: "1" },
  { label: "Projects",           href: "/projects",             icon: FolderKanban,    shortcut: "2" },
  { label: "Agents",             href: "/agents",               icon: Bot,             shortcut: "3", live: true },
  { label: "Validation",         href: "/validation",           icon: ShieldCheck,     shortcut: "4" },
  { label: "Reconciliation",     href: "/reconciliation",       icon: GitCompareArrows, shortcut: "5" },
  { label: "Dev Workspace",      href: "/developer-workspace",  icon: TerminalSquare,  shortcut: "6" },
];

const RESOURCES: NavItem[] = [
  { label: "Connectors",         href: "/connectors",   icon: Plug },
  { label: "Files",              href: "/files",        icon: FolderUp },
  { label: "Reports",            href: "/reports",      icon: FileText },
  { label: "Templates",          href: "/templates",    icon: LayoutTemplate },
  { label: "Knowledge",          href: "/knowledge",    icon: FileText },
  { label: "Marketplace",        href: "/marketplace",  icon: Puzzle },
];

const ADMIN: NavItem[] = [
  { label: "Administration",     href: "/admin",                icon: Settings },
  { label: "Cost limits",        href: "/admin/cost-limits",    icon: DollarSign },
];

function NavLink({ item, active, onNavigate }: { item: NavItem; active: boolean; onNavigate?: () => void }) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group relative flex items-center gap-2.5 px-2 py-1.5 rounded-md text-[12.5px] transition-colors",
        active
          ? "bg-app-2 text-ink font-medium"
          : "text-ink-3 hover:bg-[rgba(10,10,10,0.03)] hover:text-ink-2"
      )}
    >
      {/* Status rail */}
      <span
        aria-hidden
        className={cn(
          "absolute -left-2.5 top-1/2 -translate-y-1/2 w-[2px] rounded-full bg-ink transition-[height]",
          active ? "h-3.5" : "h-0"
        )}
      />
      <Icon className={cn("h-[15px] w-[15px]", active ? "text-ink" : "text-ink-4")} />
      <span className="flex-1 truncate">{item.label}</span>
      {item.live && (
        <span className="h-1.5 w-1.5 rounded-full bg-[var(--con-brand)] motion-safe:animate-pulse-dot" />
      )}
      {item.count !== undefined && (
        <span className="font-mono tabular-nums text-[10.5px] text-ink-4">{item.count}</span>
      )}
      {item.shortcut && !active && (
        <span className="hidden group-hover:inline-block">
          <Kbd>{item.shortcut}</Kbd>
        </span>
      )}
    </Link>
  );
}

function NavGroup({ label, items, isActive, onNavigate }: { label?: string; items: NavItem[]; isActive: (href: string) => boolean; onNavigate?: () => void }) {
  return (
    <div className="flex flex-col gap-px px-3.5">
      {label && (
        <div className="eyebrow text-[9.5px] px-2 pt-3 pb-1.5">{label}</div>
      )}
      {items.map((item) => (
        <NavLink key={item.href} item={item} active={isActive(item.href)} onNavigate={onNavigate} />
      ))}
    </div>
  );
}

function WorkspaceSwitcher() {
  // UI-030 — there's no org-switcher menu yet, so render a static info block
  // rather than a button with a ChevronDown that implies a dropdown does nothing.
  return (
    <div className="w-full flex items-center gap-2 px-2.5 py-2 bg-surface border border-hx-2 rounded-[8px] text-left text-[12.5px] text-ink-2">
      <span
        className="grid place-items-center h-[18px] w-[18px] rounded-[4px] text-[10px] font-semibold text-white"
        style={{ background: "linear-gradient(135deg,#4F46E5,#06B6D4)" }}
      >
        D
      </span>
      <div className="flex-1 min-w-0">
        <div className="font-medium text-ink truncate">DataInteg Inc.</div>
        <div className="text-[10.5px] text-ink-4 font-mono">prod · us-east-1</div>
      </div>
    </div>
  );
}

function SearchTrigger() {
  // UI-021 — the global command palette isn't built, so don't advertise a ⌘K
  // shortcut that does nothing. Disable the trigger and drop the Kbd hint until
  // a palette ships (no new palette feature is in scope for this pass).
  return (
    <button
      type="button"
      disabled
      aria-label="Global search (coming soon)"
      title="Coming soon"
      className="w-full flex items-center gap-2 px-2.5 py-1.5 bg-transparent border border-hx-2 rounded-[8px] text-[12px] text-ink-4 cursor-default opacity-70"
    >
      <Search className="h-[13px] w-[13px]" />
      <span className="flex-1 text-left">Search…</span>
    </button>
  );
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

/**
 * UI-041 — bind the footer status pill to the real /api/v1/system/health summary
 * instead of a hardcoded green dot. Falls back to a neutral "Status unknown"
 * state when the call fails or there's no session yet, so we never claim
 * "operational" without evidence.
 */
function SystemStatus() {
  const { token } = useAuth();
  const [state, setState] = useState<"unknown" | "ok" | "degraded">("unknown");

  useEffect(() => {
    // SC-010: auth via the HttpOnly cookie (credentials:"include"); no token gate.
    let cancelled = false;
    fetch(`${API_BASE}/api/v1/system/health`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (cancelled) return;
        const comps: Array<{ status?: string }> = data?.components ?? [];
        if (comps.length === 0) { setState("unknown"); return; }
        const allHealthy = comps.every((c) => c.status === "healthy");
        setState(allHealthy ? "ok" : "degraded");
      })
      .catch(() => { if (!cancelled) setState("unknown"); });
    return () => { cancelled = true; };
  }, [token]);

  const dotColor =
    state === "ok" ? "var(--con-ok)" :
    state === "degraded" ? "var(--con-warn)" : "var(--con-ink-4)";
  const label =
    state === "ok" ? "All systems operational" :
    state === "degraded" ? "Some systems degraded" : "Status unknown";

  return (
    <Link
      href="/admin/system-health"
      className="flex items-center gap-2 px-1 py-1.5 text-[11px] text-ink-3 rounded-md hover:bg-app-2 focus-ring"
    >
      <span
        aria-hidden
        className={cn("h-1.5 w-1.5 rounded-full", state === "ok" && "motion-safe:animate-pulse-dot")}
        style={{ background: dotColor }}
      />
      <span>{label}</span>
      <span aria-hidden className="ml-auto font-mono text-[10px] text-ink-4">↗</span>
    </Link>
  );
}

function UserFooter() {
  const { user } = useAuth();
  const name = user?.name || user?.email || "Signed in";
  const role = user ? "Member" : "Sign in";
  return (
    <div className="flex items-center gap-2.5 px-1 py-2 mt-1 border-t border-hx">
      <Avatar name={name} size={26} />
      <div className="flex-1 min-w-0">
        <div className="text-[12px] font-medium text-ink truncate">{name}</div>
        <div className="text-[10.5px] text-ink-4 truncate">{role}</div>
      </div>
      {/* UI-030 — no user menu wired yet; omit the ChevronDown that implies one. */}
    </div>
  );
}

interface SidebarProps {
  /** When true, render as mobile drawer (overlay). Ignored on lg+ screens. */
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}

export function Sidebar({ mobileOpen = false, onMobileClose }: SidebarProps = {}) {
  const pathname = usePathname() || "";
  const isActive = (href: string) =>
    href === "/dashboard"
      ? pathname === "/dashboard" || pathname === "/"
      : pathname.startsWith(href);

  // Close drawer on Escape and lock body scroll while open.
  useEffect(() => {
    if (!mobileOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && onMobileClose) onMobileClose();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      document.removeEventListener("keydown", onKey);
    };
  }, [mobileOpen, onMobileClose]);

  const navContent = (
    <>
      {/* Brand */}
      <div className="px-5 pt-4 pb-3.5 border-b border-hx flex items-center justify-between">
        <Link href="/dashboard" aria-label="Helix Console home" onClick={onMobileClose}>
          <HelixWordmark size={22} />
        </Link>
        {/* Mobile-only close button inside drawer */}
        {onMobileClose && (
          <button
            type="button"
            onClick={onMobileClose}
            aria-label="Close navigation"
            className="lg:hidden grid place-items-center h-9 w-9 rounded-md text-ink-3 hover:bg-app-2"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Workspace + search */}
      <div className="px-3.5 pt-2.5 pb-3 flex flex-col gap-2">
        <WorkspaceSwitcher />
        <SearchTrigger />
      </div>

      {/* Nav */}
      <nav aria-label="Primary" className="flex-1 overflow-y-auto pb-3">
        <NavGroup items={PRIMARY} isActive={isActive} onNavigate={onMobileClose} />
        <NavGroup label="Resources" items={RESOURCES} isActive={isActive} onNavigate={onMobileClose} />
        <NavGroup label="System" items={ADMIN} isActive={isActive} onNavigate={onMobileClose} />
      </nav>

      {/* Status + user */}
      <div className="px-3.5 pt-2 pb-3 border-t border-hx bg-surface-hi">
        <SystemStatus />
        <UserFooter />
      </div>
    </>
  );

  return (
    <>
      {/* Desktop sticky sidebar */}
      <aside
        aria-label="Primary navigation"
        className="hidden lg:flex w-[232px] flex-shrink-0 flex-col h-screen sticky top-0 bg-surface-hi border-r border-hx"
      >
        {navContent}
      </aside>

      {/* Mobile drawer overlay */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-40 flex" role="presentation">
          {/* UI-023 — distinct label from the in-drawer X ("Close navigation")
              so screen readers don't announce two identical controls. */}
          <button
            type="button"
            aria-label="Dismiss navigation overlay"
            tabIndex={-1}
            className="absolute inset-0 bg-black/40"
            onClick={onMobileClose}
          />
          <aside
            aria-label="Primary navigation"
            className="relative w-[280px] max-w-[85vw] h-full flex flex-col bg-surface-hi border-r border-hx shadow-lg"
          >
            {navContent}
          </aside>
        </div>
      )}
    </>
  );
}
