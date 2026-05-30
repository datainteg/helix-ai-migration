"use client";

/**
 * Generic, path-driven breadcrumbs.
 *
 * `useAutoCrumbs()` turns the current URL into a clickable trail with zero
 * per-page wiring — e.g. /projects/<id>/sprints → Projects › <name> › Sprints,
 * each segment linked to its cumulative path. Dynamic id segments (UUIDs) show
 * a friendly label when a page has registered one via <RegisterCrumbLabel>.
 */

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import type { Crumb } from "@/components/layout/Topbar";

// Static labels for known path segments. Anything not here is title-cased.
const SEGMENT_LABELS: Record<string, string> = {
  dashboard: "Dashboard",
  projects: "Projects",
  agents: "Agents",
  validation: "Validation",
  reconciliation: "Reconciliation",
  "developer-workspace": "Dev Workspace",
  connectors: "Connectors",
  files: "Files",
  reports: "Reports",
  templates: "Templates",
  knowledge: "Knowledge",
  marketplace: "Marketplace",
  admin: "Admin",
  sprints: "Sprints",
  compliance: "Compliance",
  cutover: "Cutover",
  migration: "Migration",
  "cost-limits": "Cost Limits",
  notifications: "Notifications",
  email: "Email / SMTP",
  roles: "Roles",
  users: "Users",
  "agent-mapping": "Agent Mapping",
  "llm-settings": "LLM Providers",
  "audit-logs": "Audit Logs",
  "system-health": "System Health",
  "import-export": "Import / Export",
  "custom-connectors": "Custom Connectors",
  new: "New",
};

// A segment that looks like a UUID or long hash — only shown if a label was
// registered for it (else skipped so we don't show raw ids in the trail).
const looksLikeId = (seg: string) =>
  /^[0-9a-f]{8}-[0-9a-f]{4}-/i.test(seg) || /^[0-9a-f]{16,}$/i.test(seg) || /^\d+$/.test(seg);

function humanize(seg: string): string {
  return seg.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// ── label registry: pages register id → friendly name (e.g. project name) ──
type LabelMap = Record<string, string>;
const CrumbLabelContext = createContext<{
  labels: LabelMap;
  register: (key: string, label: string) => void;
}>({ labels: {}, register: () => {} });

export function CrumbLabelProvider({ children }: { children: ReactNode }) {
  const [labels, setLabels] = useState<LabelMap>({});
  const register = (key: string, label: string) =>
    setLabels((prev) => (prev[key] === label ? prev : { ...prev, [key]: label }));
  const value = useMemo(() => ({ labels, register }), [labels]);
  return <CrumbLabelContext.Provider value={value}>{children}</CrumbLabelContext.Provider>;
}

/** Register a friendly label for a dynamic path segment (e.g. a project id →
 * its name) so the auto-breadcrumb shows the name instead of the raw id. */
export function useRegisterCrumbLabel(key: string | null | undefined, label: string | null | undefined) {
  const { register } = useContext(CrumbLabelContext);
  useEffect(() => {
    if (key && label) register(key, label);
  }, [key, label, register]);
}

/** Build the breadcrumb trail from the current path. */
export function useAutoCrumbs(): Crumb[] {
  const pathname = usePathname() || "/";
  const { labels } = useContext(CrumbLabelContext);
  return useMemo(() => {
    const segs = pathname.split("/").filter(Boolean);
    const crumbs: Crumb[] = [];
    let acc = "";
    for (const seg of segs) {
      acc += `/${seg}`;
      const registered = labels[seg];
      if (looksLikeId(seg) && !registered) continue; // hide raw ids
      crumbs.push({ label: registered || SEGMENT_LABELS[seg] || humanize(seg), href: acc });
    }
    return crumbs;
  }, [pathname, labels]);
}
