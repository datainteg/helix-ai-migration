"use client";

import React, { useState } from "react";
import { Sidebar } from "./Sidebar";
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
  // Normalize crumb shape for the topbar trail (string labels only)
  const trailLabels: string[] = (crumbs || []).map((c) =>
    typeof c === "string" ? c : c.label
  );

  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[232px_1fr] min-h-screen bg-app text-ink">
      {/* Skip-to-main link — first focusable element on every page.
          Hidden until focused, then visible at top-left. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[60] focus:bg-surface focus:text-ink focus:border focus:border-ink focus:rounded-md focus:px-3 focus:py-2 focus:text-[12.5px] focus:font-medium focus:shadow-lg"
      >
        Skip to main content
      </a>

      {/* Sidebar — desktop sticky, mobile drawer */}
      <Sidebar mobileOpen={mobileNavOpen} onMobileClose={() => setMobileNavOpen(false)} />

      <div className="flex flex-col min-w-0">
        <Topbar
          crumbs={trailLabels}
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
              crumbs={crumbs}
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
