"use client";

import React, { useEffect, useState } from "react";
import { Sidebar } from "./Sidebar";
import type { Crumb } from "./Topbar";
import { useAutoCrumbs } from "@/lib/breadcrumbs";
import { Topbar } from "./Topbar";
import { PageHero } from "./PageHero";
import { cn } from "@/lib/utils";

interface AppShellProps {
  children: React.ReactNode;
  /** Backward-compatible props from the original AppShell */
  title?: string;
  subtitle?: string;
  description?: React.ReactNode;
  eyebrow?: React.ReactNode;
  metric?: React.ReactNode;
  crumbs?: { label: string; href?: string }[] | string[];
  actions?: React.ReactNode;
  withArt?: boolean;
  /** When true, content fills the main area without inner padding (e.g. workspace IDE) */
  fullBleed?: boolean;
}

export function AppShell({
  children,
  title,
  subtitle,
  description,
  eyebrow,
  metric,
  crumbs,
  actions,
  fullBleed,
}: AppShellProps) {
  // Breadcrumbs: a page may pass explicit `crumbs`; otherwise we derive a
  // generic, fully-linked trail from the URL path (useAutoCrumbs) so every
  // route — including deep ones like /projects/<id>/sprints — gets
  // Helix › Projects › <name> › Sprints with each segment clickable.
  const SECTION_HREFS: Record<string, string> = {
    Projects: "/projects", Agents: "/agents", Validation: "/validation",
    Reconciliation: "/reconciliation", Dashboard: "/dashboard",
    Connectors: "/connectors", Admin: "/admin",
  };
  const autoCrumbs = useAutoCrumbs();
  let trailCrumbs: Crumb[];
  if (crumbs && crumbs.length > 0) {
    trailCrumbs = crumbs.map((c, i) => {
      if (typeof c !== "string") return c;
      const isLast = i === crumbs.length - 1;
      return { label: c, href: !isLast ? SECTION_HREFS[c] : undefined };
    });
  } else {
    // Auto trail: last segment is the active page (drop its href).
    trailCrumbs = autoCrumbs.map((c, i) =>
      i === autoCrumbs.length - 1 ? { label: c.label } : c
    );
  }

  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  // Desktop sidebar collapse — slim icon rail when collapsed. Persisted so the
  // choice sticks across navigation/reloads.
  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => {
    try { setCollapsed(localStorage.getItem("hx-sidebar-collapsed") === "1"); } catch { /* ignore */ }
  }, []);
  const toggleCollapsed = () => {
    setCollapsed((v) => {
      const next = !v;
      try { localStorage.setItem("hx-sidebar-collapsed", next ? "1" : "0"); } catch { /* ignore */ }
      return next;
    });
  };

  return (
    <div className={cn(
      "grid grid-cols-1 min-h-screen bg-app text-ink transition-[grid-template-columns] duration-200",
      collapsed ? "lg:grid-cols-[64px_1fr]" : "lg:grid-cols-[232px_1fr]"
    )}>
      {/* Skip-to-main link — first focusable element on every page.
          Hidden until focused, then visible at top-left. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[60] focus:bg-surface focus:text-ink focus:border focus:border-ink focus:rounded-md focus:px-3 focus:py-2 focus:text-[12.5px] focus:font-medium focus:shadow-lg"
      >
        Skip to main content
      </a>

      {/* Sidebar — desktop sticky (collapsible), mobile drawer */}
      <Sidebar
        mobileOpen={mobileNavOpen}
        onMobileClose={() => setMobileNavOpen(false)}
        collapsed={collapsed}
        onToggleCollapse={toggleCollapsed}
      />

      <div className="flex flex-col min-w-0">
        <Topbar
          crumbs={trailCrumbs}
          onMobileMenuClick={() => setMobileNavOpen(true)}
        />
        <main id="main-content" className="flex-1 bg-app" tabIndex={-1}>
          {(title || subtitle || description) && (
            <PageHero
              eyebrow={eyebrow}
              title={title || ""}
              description={description}
              subtitle={subtitle}
              metric={metric}
              actions={actions}
            />
          )}
          <div className={cn(fullBleed ? "" : "px-4 sm:px-6 lg:px-10 py-6")}>
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
