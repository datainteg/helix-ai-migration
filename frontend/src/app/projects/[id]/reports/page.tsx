"use client";

/**
 * /projects/[id]/reports — a report-style rollup of the project, built entirely
 * from REAL data returned by GET /projects/{id}/overview (counts, per-schema
 * progress, latest workflow run, validation/recon rollups). No dedicated
 * reports endpoint exists, so this composes the overview into a printable
 * summary plus links to the real export endpoints.
 */

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Download, FileSpreadsheet, FileText, BarChart3 } from "lucide-react";

import { ProjectShell } from "@/components/layout/ProjectShell";
import {
  Card, Button, MetricCard, StatusBadge, EmptyState, ErrorBanner, LoadingState,
  Table, THead, TBody, TR, TH, TD,
} from "@/components/ui";
import { useRegisterCrumbLabel } from "@/lib/breadcrumbs";
import { useProjectKey } from "@/lib/projects/useProjectKey";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface OverviewSchema { schema: string; schema_type: string; tables: number; rows: number; }
interface OverviewRun {
  workflow_id: string; status: string; kind: string; mode: string | null;
  created_at: string | null; steps_done: number; steps_total: number;
}
interface ProjectOverview {
  schema_count: number;
  table_count: number;
  schemas: OverviewSchema[];
  latest_run: OverviewRun | null;
  validation: { pct: number | null; total: number };
  recon: { pct: number | null; total: number };
}

async function download(path: string, filename: string) {
  const res = await fetch(`${API_BASE}${path}`, { credentials: "include" });
  if (!res.ok) return false;
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
  return true;
}

const fmt = (n: number) => n.toLocaleString();
const pctText = (pct: number | null, total: number) =>
  pct == null ? "—" : `${pct}%`;

export default function ProjectReportsPage() {
  const projectKey = String(useParams<{ id: string }>().id);
  const { id } = useProjectKey(projectKey);
  const [projectName, setProjectName] = useState("Project");
  const [projectStatus, setProjectStatus] = useState("draft");
  const [onHold, setOnHold] = useState(false);
  const [overview, setOverview] = useState<ProjectOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useRegisterCrumbLabel(projectKey, projectName !== "Project" ? projectName : undefined);

  useEffect(() => {
    if (!id) return;
    fetch(`${API_BASE}/api/v1/projects/${id}`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((p) => {
        setProjectName(p?.name || "Project");
        if (p?.status) setProjectStatus(p.status);
        setOnHold(!!p?.on_hold);
      })
      .catch(() => setProjectName("Project"));
  }, [id]);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    fetch(`${API_BASE}/api/v1/projects/${id}/overview`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`Overview unavailable (${r.status})`))))
      .then((d: ProjectOverview) => { setOverview(d); setError(""); })
      .catch((e) => setError(e instanceof Error ? e.message : "Couldn't load this project's report data."))
      .finally(() => setLoading(false));
  }, [id]);

  const run = overview?.latest_run ?? null;
  const hasData =
    !!overview &&
    (overview.schema_count > 0 ||
      overview.table_count > 0 ||
      overview.validation.total > 0 ||
      overview.recon.total > 0 ||
      !!run);

  return (
    <ProjectShell
      projectId={projectKey}
      projectName={projectName}
      projectStatus={projectStatus as any}
      onHold={onHold}
      subtitle="Summary report rolled up from this project's real migration metrics."
    >
      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      {loading ? (
        <LoadingState label="Compiling report…" />
      ) : !hasData ? (
        <Card>
          <EmptyState
            icon={<BarChart3 className="h-4 w-4" />}
            title="Nothing to report yet"
            description="Once schemas are discovered and a migration run produces validation or reconciliation results, this report fills in automatically — connect a source on Source & Target to begin."
          />
        </Card>
      ) : (
        <div className="flex flex-col gap-4">
          {/* ── Header stats ── */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <MetricCard label="Schemas" value={fmt(overview!.schema_count)} />
            <MetricCard label="Tables" value={fmt(overview!.table_count)} />
            <MetricCard
              label="Validation"
              value={pctText(overview!.validation.pct, overview!.validation.total)}
              hint={overview!.validation.total ? `${fmt(overview!.validation.total)} results` : "no runs yet"}
            />
            <MetricCard
              label="Reconciliation"
              value={pctText(overview!.recon.pct, overview!.recon.total)}
              hint={overview!.recon.total ? `${fmt(overview!.recon.total)} results` : "no runs yet"}
            />
          </div>

          {/* ── Migration by schema ── */}
          <Card
            title="Migration by schema"
            description="Per-schema scope from introspected metadata."
          >
            {overview!.schemas.length ? (
              <Table>
                <THead>
                  <TR>
                    <TH>Schema</TH>
                    <TH>Type</TH>
                    <TH align="right">Tables</TH>
                    <TH align="right">Rows</TH>
                  </TR>
                </THead>
                <TBody>
                  {overview!.schemas.map((s, i) => (
                    <TR key={`${s.schema}-${i}`}>
                      <TD mono>{s.schema}</TD>
                      <TD>
                        <span className="text-[11px] uppercase tracking-wider font-mono text-ink-3">
                          {s.schema_type}
                        </span>
                      </TD>
                      <TD align="right" mono>{fmt(s.tables)}</TD>
                      <TD align="right" mono>{fmt(s.rows)}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            ) : (
              <EmptyState
                icon={<BarChart3 className="h-4 w-4" />}
                title="No schemas discovered"
                description="Run schema introspection from Source & Target to populate this table."
              />
            )}
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-4">
            {/* ── Latest run summary ── */}
            <Card title="Latest run" description="Most recent workflow run for this project.">
              {run ? (
                <div className="flex flex-col gap-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-[13px] font-medium text-ink truncate">{run.workflow_id}</div>
                      <div className="text-[11px] text-ink-4 font-mono">
                        {run.kind}{run.mode ? ` · ${run.mode}` : ""}
                        {run.created_at ? ` · ${new Date(run.created_at).toLocaleString()}` : ""}
                      </div>
                    </div>
                    <StatusBadge status={run.status} />
                  </div>
                  <div>
                    <div className="flex items-center justify-between text-[12px] text-ink-3 mb-1">
                      <span>{run.steps_done} of {run.steps_total} steps complete</span>
                      <span className="font-mono tabular-nums">
                        {run.steps_total ? Math.round((run.steps_done / run.steps_total) * 100) : 0}%
                      </span>
                    </div>
                    <div className="h-1.5 rounded-full bg-app-2 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-[var(--con-brand)]"
                        style={{ width: `${run.steps_total ? (run.steps_done / run.steps_total) * 100 : 0}%` }}
                      />
                    </div>
                  </div>
                </div>
              ) : (
                <EmptyState
                  icon={<FileText className="h-4 w-4" />}
                  title="No run yet"
                  description="No workflow run has been started for this project."
                />
              )}
            </Card>

            {/* ── Downloadable exports ── */}
            <Card title="Downloadable exports" description="Real exports available for this project.">
              <div className="flex flex-col gap-3">
                <ExportItem
                  icon={<FileText className="h-4 w-4" />}
                  title="Compliance bundle (PDF)"
                  desc="Audit chain, validation + recon runs, cutovers and artifacts for this project."
                  onClick={() => void download(`/api/v1/projects/${id}/compliance-bundle`, `helix-compliance-${id}.pdf`)}
                />
                <ExportItem
                  icon={<FileSpreadsheet className="h-4 w-4" />}
                  title="LLM usage (CSV)"
                  desc="Per-agent token + cost usage for the last 30 days."
                  onClick={() => void download("/api/v1/usage/llm/export.csv?days=30", "helix-usage-30d.csv")}
                />
              </div>
            </Card>
          </div>
        </div>
      )}
    </ProjectShell>
  );
}

function ExportItem({ icon, title, desc, onClick }: { icon: React.ReactNode; title: string; desc: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-left rounded-[10px] border border-hx bg-surface p-4 hover:bg-surface-hi hover:border-hx-2 transition-colors"
    >
      <div className="flex items-start gap-3">
        <div className="grid place-items-center h-9 w-9 rounded-lg bg-app-2 text-ink-3 flex-shrink-0">{icon}</div>
        <div className="min-w-0">
          <div className="text-[13px] font-medium text-ink flex items-center gap-1.5">{title} <Download className="h-3 w-3 text-ink-4" /></div>
          <div className="text-[12px] text-ink-3 mt-0.5">{desc}</div>
        </div>
      </div>
    </button>
  );
}
