"use client";

import React from "react";
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

  return (
    <div className="grid grid-cols-[232px_1fr] min-h-screen bg-app text-ink">
      <Sidebar />
      <div className="flex flex-col min-w-0">
        <Topbar crumbs={trailLabels} />
        <main className="flex-1 bg-app">
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
          <div className={cn(fullBleed ? "" : "px-10 py-6")}>
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
