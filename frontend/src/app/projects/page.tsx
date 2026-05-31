"use client";

/**
 * /projects — Enterprise migrations list.
 *
 * Visual layout from Figma `pages-projects.jsx`. Live data via `/api/v1/projects`;
 * fields the backend doesn't yet expose (source/target/risk/valid/recon/phase) are
 * surfaced as em-dashes — replace as the backend grows.
 */

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import {
  Download,
  Plus,
  ArrowUpRight,
  ArrowRight,
  MoreHorizontal,
} from "lucide-react";

import { AppShell } from "@/components/layout";
import {
  Avatar,
  Button,
  Card,
  EmptyState,
  MetricCell,
  ProgressBar,
  SearchInput,
  SkeletonTable,
  StatusBadge,
  Tabs,
  ConfirmModal,
  ErrorBanner,
} from "@/components/ui";
import { AppIcon } from "@/components/icons";
import { useAuth } from "@/lib/auth-context";
import { formatRelative as formatRelativeUtil } from "@/lib/utils";
import { archiveProject, restoreProject, deleteProject, forceDeleteProject } from "@/lib/projects/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface APIProject {
  id: string;
  slug?: string;
  name: string;
  description?: string;
  status: string;
  risk_level?: string;
  source_system?: string;
  target_system?: string;
  environment?: string;
  owner_name?: string;
  risk_score?: number;
  validation_pct?: number | null;
  recon_pct?: number | null;
  table_count?: number;
  phase?: string;
  environments?: string[];
  updated_at?: string;
}

interface ProjectSummary {
  validation_pct: number | null;
  recon_pct: number | null;
  table_count: number;
  latest_status: string | null;
  phase: string | null;
}

const PAGE_SIZE = 50;
type Filter = "all" | "running" | "awaiting" | "completed" | "failed" | "draft" | "archived";

export default function ProjectsPage() {
  const { token, can, role, isSuperAdmin } = useAuth();
  const canWrite = can("project:write");
  const isAdmin = isSuperAdmin || role === "admin";
  const [projects, setProjects] = useState<APIProject[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  const [confirmForce, setConfirmForce] = useState<APIProject | null>(null);
  const [actionErr, setActionErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const refetch = () => setReloadKey((k) => k + 1);

  useEffect(() => {
    setLoading(true);
    // Paginated fetch + per-project summary merge (validation %, recon %, …).
    Promise.all([
      // Only managers (project:write) fetch + see archived projects; regular
      // members just see active ones.
      fetch(`${API_BASE}/api/v1/projects?include_archived=${canWrite}&limit=${PAGE_SIZE}&offset=${offset}`, { credentials: "include" })
        .then((r) => (r.ok ? r.json() : { items: [], total: 0 })),
      fetch(`${API_BASE}/api/v1/projects/summary`, { credentials: "include" })
        .then((r) => (r.ok ? r.json() : {}))
        .catch(() => ({})),
    ])
      .then(([data, summary]: [any, Record<string, ProjectSummary>]) => {
        const items: APIProject[] = Array.isArray(data) ? data : (data.items ?? []);
        setTotal(typeof data?.total === "number" ? data.total : items.length);
        // Merge summary rollups into each project.
        const merged = items.map((p) => {
          const s = summary[p.id];
          return s ? { ...p, validation_pct: s.validation_pct, recon_pct: s.recon_pct, table_count: s.table_count, phase: s.phase ?? undefined } : p;
        });
        setProjects(merged);
      })
      .catch(() => { setProjects([]); setTotal(0); })
      .finally(() => setLoading(false));
  }, [token, offset, reloadKey, canWrite]);

  const counts = {
    all: projects.filter((p) => p.status !== "archived").length,
    running: projects.filter((p) => p.status === "running").length,
    awaiting: projects.filter((p) => p.status === "awaiting").length,
    completed: projects.filter((p) => p.status === "completed").length,
    failed: projects.filter((p) => p.status === "failed").length,
    draft: projects.filter((p) => p.status === "draft" || p.status === "queued").length,
    archived: projects.filter((p) => p.status === "archived").length,
  };

  const filtered = projects.filter((p) => {
    const matchStatus =
      filter === "all"
        ? p.status !== "archived"   // "All" hides archived; use the Archived tab
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
          <Button variant="outline" onClick={() => exportProjectsCsv(filtered)} disabled={filtered.length === 0}>
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
        {actionErr && <ErrorBanner message={actionErr} onDismiss={() => setActionErr("")} />}
        {/* Summary cells */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 bg-surface border border-hx rounded-[10px] divide-y lg:divide-y-0 lg:divide-x divide-[var(--con-line)] overflow-hidden">
          <MetricCell label="TOTAL"     value={counts.all}       hint="All time" />
          <MetricCell label="RUNNING"   value={counts.running}   hint="In progress"     accent="var(--con-info)" />
          <MetricCell label="AWAITING"  value={counts.awaiting}  hint="Human review"    accent="var(--con-warn)" />
          <MetricCell label="COMPLETED" value={counts.completed} hint="30 days"         accent="var(--con-ok)" />
          <MetricCell label="FAILED"    value={counts.failed}    hint="Needs attention" accent="var(--con-err)" />
          <MetricCell label="DRAFT"     value={counts.draft}     hint="Not started"     accent="var(--con-ink-3)" />
        </div>

        {/* Filter bar — wraps below ~900px so controls never clip (UI-028); the
            6-tab strip scrolls horizontally rather than overflowing. */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3.5 py-2 bg-surface border border-hx rounded-[10px]">
          <SearchInput
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search projects, owners, or IDs…"
            ariaLabel="Search projects"
            wrapperClassName="max-w-[400px] flex-1 min-w-[180px]"
          />
          <div className="max-w-full overflow-x-auto">
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
                // Archived is a manager concern — only show to project:write holders.
                ...(canWrite ? [{ id: "archived", label: "Archived", count: counts.archived }] : []),
              ]}
            />
          </div>
          <div className="flex-1" />
          <span className="text-[11.5px] text-ink-4 font-mono">{filtered.length} shown</span>
        </div>

        {loading ? (
          // UI-046 — shaped skeleton rows reserve the list's footprint on first
          // paint instead of a centered spinner, cutting layout shift.
          <SkeletonTable rows={8} />
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
                    const env = p.environment || (p.environments?.length ? p.environments.join(", ") : "");
                    const riskColor =
                      risk >= 80 ? "var(--con-err)" :
                      risk >= 60 ? "var(--con-warn)" :
                      risk >= 40 ? "var(--con-info)" :
                      risk === 0 ? "var(--con-ink-5)" :
                                   "var(--con-ok)";
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
                          <Link href={`/projects/${p.slug ?? p.id}`} className="block max-w-[240px]">
                            <div className="flex flex-col gap-0.5">
                              <span className="font-medium text-ink truncate">{p.name}</span>
                              <span className="font-mono text-[11px] text-ink-3">
                                {p.id.slice(0, 8)}{env ? ` · ${env}` : ""}
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
                          <div className="flex items-center justify-end gap-0.5">
                            <Link
                              href={`/projects/${p.slug ?? p.id}`}
                              aria-label={`Open ${p.name}`}
                              className="inline-flex items-center justify-center h-8 w-8 rounded-md text-ink-4 hover:text-ink-2 hover:bg-app-2 focus-ring"
                            >
                              <ArrowUpRight className="h-3.5 w-3.5" />
                            </Link>
                            {(canWrite || isAdmin) && (
                              <RowActions
                                project={p}
                                canWrite={canWrite}
                                isAdmin={isAdmin}
                                onArchive={async () => { setActionErr(""); try { await archiveProject(p.id); refetch(); } catch (e) { setActionErr(e instanceof Error ? e.message : "Archive failed"); } }}
                                onRestore={async () => { setActionErr(""); try { await restoreProject(p.id); refetch(); } catch (e) { setActionErr(e instanceof Error ? e.message : "Restore failed"); } }}
                                onSoftDelete={async () => { setActionErr(""); try { await deleteProject(p.id); refetch(); } catch (e) { setActionErr(e instanceof Error ? e.message : "Delete failed"); } }}
                                onForceDelete={() => setConfirmForce(p)}
                              />
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        {/* Pagination — only when the org has more than one page of projects. */}
        {!loading && total > PAGE_SIZE && (
          <div className="flex items-center justify-between text-[12px] text-ink-3">
            <span className="font-mono">
              {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
            </span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Previous</Button>
              <Button variant="outline" size="sm" disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>Next</Button>
            </div>
          </div>
        )}
      </div>

      <ConfirmModal
        open={confirmForce !== null}
        onClose={() => setConfirmForce(null)}
        onConfirm={async () => {
          if (!confirmForce) return;
          setBusy(true); setActionErr("");
          try { await forceDeleteProject(confirmForce.id); setConfirmForce(null); refetch(); }
          catch (e) { setActionErr(e instanceof Error ? e.message : "Force delete failed"); }
          finally { setBusy(false); }
        }}
        title={`Permanently delete "${confirmForce?.name}"?`}
        description="Admin force-delete removes the project and ALL its data — runs, steps, reconciliation, validation, connections, and schema. This cannot be undone."
        destructive
        busy={busy}
        confirmLabel="Force delete"
      />
    </AppShell>
  );
}

function RowActions({ project, canWrite, isAdmin, onArchive, onRestore, onSoftDelete, onForceDelete }: {
  project: APIProject;
  canWrite: boolean;
  isAdmin: boolean;
  onArchive: () => void;
  onRestore: () => void;
  onSoftDelete: () => void;
  onForceDelete: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState<{ top: number; right: number } | null>(null);
  const btnRef = useRef<HTMLButtonElement>(null);

  // Count visible items to estimate menu height for flip logic.
  const itemCount =
    (canWrite && (project.status === "archived" || project.status === "deleted") ? 1 : 0) +
    (canWrite && project.status !== "archived" && project.status !== "deleted" ? 1 : 0) +
    (canWrite && project.status !== "deleted" ? 1 : 0) +
    (isAdmin ? 1 : 0);

  // Render the menu in a portal at the button's viewport position so it escapes
  // the table's overflow-x-auto clipping. Flip ABOVE the button when there's
  // not enough room below (e.g. last rows near the viewport bottom).
  const toggle = () => {
    if (!open && btnRef.current) {
      const r = btnRef.current.getBoundingClientRect();
      const menuH = itemCount * 36 + 8;           // ~36px/item + padding
      const spaceBelow = window.innerHeight - r.bottom;
      const flipUp = spaceBelow < menuH + 12 && r.top > menuH + 12;
      setCoords({
        top: flipUp ? r.top - menuH - 4 : r.bottom + 4,
        right: window.innerWidth - r.right,
      });
    }
    setOpen((v) => !v);
  };

  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    // Close on any outside click, scroll, or resize (position would go stale).
    window.addEventListener("mousedown", close);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    document.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", close);
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const item = "w-full text-left px-3 py-2 hover:bg-app-2 transition-colors";

  return (
    <>
      <button ref={btnRef} type="button" aria-label="Project actions" aria-haspopup="menu" aria-expanded={open}
        onMouseDown={(e) => e.stopPropagation()} onClick={toggle}
        className="inline-flex items-center justify-center h-8 w-8 rounded-md text-ink-4 hover:text-ink-2 hover:bg-app-2 focus-ring">
        <MoreHorizontal className="h-3.5 w-3.5" />
      </button>
      {open && coords && createPortal(
        <div
          role="menu"
          onMouseDown={(e) => e.stopPropagation()}
          style={{ position: "fixed", top: coords.top, right: coords.right }}
          className="z-[200] w-44 rounded-lg border border-hx bg-surface shadow-xl py-1 text-[12.5px]"
        >
          {canWrite && (project.status === "archived" || project.status === "deleted") && (
            <button type="button" onClick={() => { setOpen(false); onRestore(); }} className={`${item} text-[var(--con-ok)] font-medium`}>Restore</button>
          )}
          {canWrite && project.status !== "archived" && project.status !== "deleted" && (
            <button type="button" onClick={() => { setOpen(false); onArchive(); }} className={`${item} text-ink-2`}>Archive</button>
          )}
          {canWrite && project.status !== "deleted" && (
            <button type="button" onClick={() => { setOpen(false); onSoftDelete(); }} className={`${item} text-ink-2`}>Delete (soft)</button>
          )}
          {isAdmin && (
            <button type="button" onClick={() => { setOpen(false); onForceDelete(); }} className={`${item} text-[var(--con-err)] border-t border-hx mt-0.5`}>Force delete</button>
          )}
        </div>,
        document.body
      )}
    </>
  );
}

function exportProjectsCsv(projects: APIProject[]) {
  const head = ["id", "name", "status", "source", "target", "environment", "tables", "validation_pct", "recon_pct"];
  const esc = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const rows = projects.map((p) => [
    p.id, p.name, p.status, p.source_system ?? "", p.target_system ?? "", p.environment ?? "",
    p.table_count ?? "", p.validation_pct ?? "", p.recon_pct ?? "",
  ].map(esc).join(","));
  const csv = head.join(",") + "\n" + rows.join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url; a.download = "helix-projects.csv";
  document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
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

// UI-044 — delegate to the centralised formatter in lib/utils; keep only the
// undefined→em-dash guard this table needs.
function formatRelative(iso?: string): string {
  if (!iso) return "—";
  return formatRelativeUtil(iso) || "—";
}
