"use client";

/**
 * /projects — Enterprise migrations list.
 *
 * Visual layout from Figma `pages-projects.jsx`. Live data via `/api/v1/projects`;
 * fields the backend doesn't yet expose (source/target/risk/valid/recon/phase) are
 * surfaced as em-dashes — replace as the backend grows.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Download,
  Filter,
  MoreHorizontal,
  Plus,
  Search,
  ArrowUpRight,
  ArrowRight,
} from "lucide-react";

import { AppShell } from "@/components/layout";
import {
  Avatar,
  Button,
  Card,
  EmptyState,
  LoadingState,
  MetricCell,
  ProgressBar,
  StatusBadge,
  Tabs,
} from "@/components/ui";
import { AppIcon } from "@/components/icons";
import { useAuth } from "@/lib/auth-context";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface APIProject {
  id: string;
  name: string;
  description?: string;
  status: string;
  source_system?: string;
  target_system?: string;
  owner_name?: string;
  risk_score?: number;
  validation_pct?: number;
  recon_pct?: number;
  table_count?: number;
  phase?: string;
  environments?: string[];
  updated_at?: string;
}

type Filter = "all" | "running" | "awaiting" | "completed" | "failed" | "draft";

export default function ProjectsPage() {
  const { token } = useAuth();
  const [projects, setProjects] = useState<APIProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    fetch(`${API_BASE}/api/v1/projects`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : []))
      .then((data: unknown) => {
        // Backend returns a paginated envelope {items, total, limit, offset}.
        // Guard against bare-array responses from older backends.
        const items: APIProject[] = Array.isArray(data)
          ? (data as APIProject[])
          : (((data as any).items as APIProject[]) ?? []);
        setProjects(items);
      })
      .catch(() => setProjects([]))
      .finally(() => setLoading(false));
  }, [token]);

  const counts = {
    all: projects.length,
    running: projects.filter((p) => p.status === "running").length,
    awaiting: projects.filter((p) => p.status === "awaiting").length,
    completed: projects.filter((p) => p.status === "completed").length,
    failed: projects.filter((p) => p.status === "failed").length,
    draft: projects.filter((p) => p.status === "draft" || p.status === "queued").length,
  };

  const filtered = projects.filter((p) => {
    const matchStatus =
      filter === "all"
        ? true
        : filter === "draft"
        ? p.status === "draft" || p.status === "queued"
        : p.status === filter;
    const matchSearch =
      !search ||
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.id.toLowerCase().includes(search.toLowerCase());
    return matchStatus && matchSearch;
  });

  return (
    <AppShell
      eyebrow="ENTERPRISE MIGRATIONS"
      title="Projects"
      metric={`${projects.length} total`}
      description="Track every active migration across teams, environments, and source/target systems."
      crumbs={["Projects"]}
      actions={
        <>
          <Button variant="outline">
            <Download className="h-3.5 w-3.5" /> Export
          </Button>
          <Link href="/projects/new">
            <Button variant="primary">
              <Plus className="h-3.5 w-3.5" /> New migration
            </Button>
          </Link>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {/* Summary cells */}
        <div className="grid grid-cols-6 bg-surface border border-hx rounded-[10px] divide-x divide-[var(--con-line)] overflow-hidden">
          <MetricCell label="TOTAL"     value={counts.all}       hint="All time" />
          <MetricCell label="RUNNING"   value={counts.running}   hint="In progress"     accent="var(--con-info)" />
          <MetricCell label="AWAITING"  value={counts.awaiting}  hint="Human review"    accent="var(--con-warn)" />
          <MetricCell label="COMPLETED" value={counts.completed} hint="30 days"         accent="var(--con-ok)" />
          <MetricCell label="FAILED"    value={counts.failed}    hint="Needs attention" accent="var(--con-err)" />
          <MetricCell label="DRAFT"     value={counts.draft}     hint="Not started"     accent="var(--con-ink-3)" />
        </div>

        {/* Filter bar */}
        <div className="flex items-center gap-3 px-3.5 py-2 bg-surface border border-hx rounded-[10px]">
          <label className="relative max-w-[400px] flex-1">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-ink-4" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search projects, owners, or IDs…"
              className="w-full h-8 rounded-[7px] border border-hx bg-surface pl-8 pr-3 text-[12.5px] focus-ring"
            />
          </label>
          <Tabs
            value={filter}
            onChange={(v) => setFilter(v as Filter)}
            tabs={[
              { id: "all",       label: "All",       count: counts.all },
              { id: "running",   label: "Running",   count: counts.running },
              { id: "awaiting",  label: "Awaiting",  count: counts.awaiting },
              { id: "completed", label: "Completed", count: counts.completed },
              { id: "failed",    label: "Failed",    count: counts.failed },
              { id: "draft",     label: "Draft",     count: counts.draft },
            ]}
          />
          <div className="flex-1" />
          <Button variant="outline" size="sm">
            <Filter className="h-3.5 w-3.5" /> Filters
          </Button>
          <Button variant="ghost" size="icon">
            <MoreHorizontal className="h-3.5 w-3.5" />
          </Button>
        </div>

        {loading ? (
          <LoadingState />
        ) : filtered.length === 0 ? (
          <EmptyState
            title={projects.length === 0 ? "No projects yet" : "No matches"}
            description={
              projects.length === 0
                ? "Create your first migration project to start orchestrating agents."
                : "Try changing the search term or status filter."
            }
            action={
              projects.length === 0 ? (
                <Link href="/projects/new">
                  <Button variant="primary">
                    <Plus className="h-3.5 w-3.5" /> Create project
                  </Button>
                </Link>
              ) : undefined
            }
          />
        ) : (
          <Card bodyClassName="p-0">
            <div className="overflow-x-auto border-t border-hx">
              <table className="w-full border-collapse text-[12.5px] min-w-[1280px]">
                <thead>
                  <tr className="bg-surface-hi">
                    {[
                      { l: "", w: 4 },
                      { l: "Project" },
                      { l: "Source → Target", w: 260 },
                      { l: "Phase", w: 130 },
                      { l: "Tables", w: 80, num: true },
                      { l: "Risk", w: 100, num: true },
                      { l: "Valid", w: 110, num: true },
                      { l: "Recon", w: 110, num: true },
                      { l: "Owner", w: 160 },
                      { l: "Updated", w: 80 },
                      { l: "Status", w: 100 },
                      { l: "", w: 32 },
                    ].map((h, i) => (
                      <th
                        key={i}
                        className={`px-3 py-2.5 font-medium text-ink-4 text-[10.5px] uppercase tracking-[0.08em] font-mono border-b border-hx ${
                          h.num ? "text-right" : "text-left"
                        }`}
                        style={h.w ? { width: h.w } : undefined}
                      >
                        {h.l}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((p, idx) => {
                    const risk = p.risk_score ?? 0;
                    const valid = p.validation_pct ?? 0;
                    const recon = p.recon_pct ?? 0;
                    const riskColor =
                      risk >= 80 ? "var(--con-err)" :
                      risk >= 60 ? "var(--con-warn)" :
                      risk >= 40 ? "var(--con-info)" :
                      risk === 0 ? "var(--con-ink-5)" :
                                   "var(--con-ok)";
                    const envs = p.environments?.length ? p.environments.join(", ") : "—";
                    return (
                      <tr
                        key={p.id}
                        className={`hover:bg-surface-hi cursor-pointer ${
                          idx === filtered.length - 1 ? "" : "border-b border-hx"
                        }`}
                      >
                        <td className="p-0" style={{ width: 4 }}>
                          <div className="w-[3px] h-[46px]" style={{ background: riskColor }} />
                        </td>
                        <td className="px-3 py-3">
                          <Link href={`/projects/${p.id}`} className="block max-w-[240px]">
                            <div className="flex flex-col gap-0.5">
                              <span className="font-medium text-ink truncate">{p.name}</span>
                              <span className="font-mono text-[10.5px] text-ink-4">
                                {p.id.slice(0, 8)} · {envs}
                              </span>
                            </div>
                          </Link>
                        </td>
                        <td className="px-3 py-3">
                          <SourceTarget source={p.source_system} target={p.target_system} />
                        </td>
                        <td className="px-3 py-3 text-ink-3">{p.phase ?? "—"}</td>
                        <td className="px-3 py-3 text-right font-mono tabular-nums text-ink-2">
                          {p.table_count ?? "—"}
                        </td>
                        <td className="px-3 py-3 text-right">
                          {risk > 0 ? (
                            <span className="font-mono tabular-nums font-medium" style={{ color: riskColor }}>
                              {risk}
                            </span>
                          ) : (
                            <span className="font-mono text-ink-5">—</span>
                          )}
                        </td>
                        <td className="px-3 py-3">
                          <ProgressCell pct={valid} positive />
                        </td>
                        <td className="px-3 py-3">
                          <ProgressCell pct={recon} positive />
                        </td>
                        <td className="px-3 py-3">
                          <div className="flex items-center gap-1.5">
                            <Avatar name={p.owner_name ?? "Unassigned"} size={20} />
                            <span className="text-ink-2 text-[12px]">{p.owner_name ?? "Unassigned"}</span>
                          </div>
                        </td>
                        <td className="px-3 py-3 text-ink-4 text-[11.5px]">{formatRelative(p.updated_at)}</td>
                        <td className="px-3 py-3">
                          <StatusBadge status={p.status} />
                        </td>
                        <td className="px-3 py-3">
                          <Link href={`/projects/${p.id}`} className="text-ink-4 hover:text-ink-2">
                            <ArrowUpRight className="h-3.5 w-3.5" />
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
    </AppShell>
  );
}

// ── Helpers ─────────────────────────────────────────────────────

function ProgressCell({ pct, positive }: { pct: number; positive?: boolean }) {
  if (pct === 0) {
    return (
      <div className="flex items-center gap-1.5 justify-end">
        <span className="font-mono text-ink-5">—</span>
      </div>
    );
  }
  const tone: "ok" | "ink" | "warn" =
    pct >= 95 ? "ok" : pct >= 80 ? "ink" : positive ? "warn" : "ink";
  return (
    <div className="flex items-center gap-1.5 justify-end">
      <div className="w-9">
        <ProgressBar value={pct} tone={tone} height={3} />
      </div>
      <span className="font-mono tabular-nums text-[11.5px] text-ink-2 min-w-[32px] text-right">
        {pct}%
      </span>
    </div>
  );
}

function SourceTarget({ source, target }: { source?: string; target?: string }) {
  if (!source && !target) return <span className="text-ink-5 font-mono text-[11.5px]">—</span>;
  return (
    <div className="flex items-center gap-1.5 text-[12px] text-ink-2">
      <AppIcon name={source ?? "unknown"} />
      <span className="font-mono text-[11.5px]">{source ?? "?"}</span>
      <ArrowRight className="h-3 w-3 text-ink-4" />
      <AppIcon name={target ?? "unknown"} />
      <span className="font-mono text-[11.5px]">{target ?? "?"}</span>
    </div>
  );
}

function formatRelative(iso?: string): string {
  if (!iso) return "—";
  const d = new Date(iso).getTime();
  if (Number.isNaN(d)) return "—";
  const diff = Date.now() - d;
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const days = Math.floor(h / 24);
  return `${days}d ago`;
}
