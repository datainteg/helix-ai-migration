"use client";

/**
 * /projects/[id] — Project detail.
 *
 * Visual layout ported from Figma `pages-projects.jsx` (ProjectDetailPage,
 * ~261-482). Live data via `${API_BASE}/api/v1/projects/${id}`; phase ticker,
 * schema breakdown, BMAD workflow steps, risk model, and recent activity are
 * rendered from API fields when present and degrade to em-dash / are hidden
 * when missing.
 */

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  Pause,
  Play,
  Eye,
  Sparkles,
  Check,
  FileText,
  ArrowRight,
  Pencil,
  RotateCw,
  ListChecks,
  Database,
  Workflow as WorkflowIcon,
  FileCode,
  ShieldCheck,
  GitCompare,
  Rocket,
  Terminal,
  FileCheck2,
  BarChart3,
  CheckSquare,
  Clock,
  ChevronRight,
} from "lucide-react";

import { AppShell } from "@/components/layout";
import { useProjectKey } from "@/lib/projects/useProjectKey";
import { useRegisterCrumbLabel } from "@/lib/breadcrumbs";
import { AskProject } from "@/components/projects/AskProject";
import { AppIcon, AgentIcon } from "@/components/icons";
import {
  Avatar,
  Button,
  Card,
  Chip,
  ProgressBar,
  StatusBadge,
  ErrorBanner,
  Modal,
} from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";
import {
  updateProject, fetchProjectMembers, setProjectHold,
  fetchProjectComments, addProjectComment,
  type OrgMember, type ProjectComment as ProjectCommentT,
} from "@/lib/projects/api";
import { listRunRequests, listProjectRequirements } from "@/lib/workflows/api";
import { listProjectArtifacts } from "@/lib/artifacts/api";
import { listConnections } from "@/lib/projects/connections";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

// ─── Types ───────────────────────────────────────────────────

interface APISchema {
  schema: string;
  tables?: number;
  done?: number;
  rows?: string;
  size?: string;
  status?: string;
}

interface APIWorkflowStep {
  name: string;
  role: string;
  status: string;
  duration?: string;
  artifact?: string | null;
}

interface APIRiskFactor {
  name: string;
  value: number;
  invert?: boolean;
}

interface APIPhase {
  id: string;
  label: string;
  status: "completed" | "running" | "pending" | string;
}

interface APIActivity {
  who: string;
  action: string;
  time: string;
}

interface APIProject {
  id: string;
  name: string;
  description?: string;
  status: string;
  source_system?: string;
  target_system?: string;
  owner_id?: string;
  owner_name?: string;
  on_hold?: boolean;
  require_run_approval?: boolean;
  team?: string;
  environment?: string;
  environments?: string[];
  llm_routing?: string;
  table_count?: number;
  schema_count?: number;
  total_size?: string;
  created_at?: string;
  created_by_name?: string;
  progress_pct?: number;
  phase_label?: string;
  phases_complete?: number;
  phases_total?: number;
  tables_done?: number;
  eta?: string;
  phases?: APIPhase[];
  schemas?: APISchema[];
  workflow_id?: string;
  workflow_mode?: string;
  workflow_started?: string;
  workflow_steps?: APIWorkflowStep[];
  risk_score?: number;
  risk_trend?: "up" | "down" | "flat" | string;
  risk_factors?: APIRiskFactor[];
  recent_activity?: APIActivity[];
}

// ─── Overview (real data from GET /projects/{id}/overview) ─

interface OverviewSchema { schema: string; schema_type: string; tables: number; rows: number; }
interface OverviewStep { agent: string; order: number; status: string; error?: string | null; artifact_path?: string | null; }
interface OverviewRun {
  workflow_id: string; status: string; kind: string; mode?: string; created_at?: string | null;
  steps_done: number; steps_total: number; steps: OverviewStep[];
}
interface ProjectOverview {
  schema_count: number;
  table_count: number;
  schemas: OverviewSchema[];
  latest_run: OverviewRun | null;
  validation: { pct: number | null; total: number };
  recon: { pct: number | null; total: number };
}

function SourceTarget({ source, target }: { source?: string; target?: string }) {
  if (!source && !target) return <span className="text-ink-5 font-mono text-[11.5px]">—</span>;
  return (
    <span className="inline-flex items-center gap-1.5 text-[12px] text-ink-2">
      <AppIcon name={source ?? "unknown"} size={18} />
      <span className="font-mono text-[11.5px]">{source ?? "?"}</span>
      <ArrowRight className="h-3 w-3 text-ink-4" />
      <AppIcon name={target ?? "unknown"} size={18} />
      <span className="font-mono text-[11.5px]">{target ?? "?"}</span>
    </span>
  );
}

/** One PM status tile — label, a value node, optional sub-line, optional link. */
function StatusTile({ label, value, sub, href }: { label: string; value: React.ReactNode; sub?: string; href?: string }) {
  const inner = (
    <div className={cn("rounded-[10px] border border-hx bg-surface p-3 h-full", href && "hover:border-hx-2 transition-colors")}>
      <div className="text-[10px] uppercase tracking-wider font-mono text-ink-4">{label}</div>
      <div className="mt-2 flex items-center gap-1.5">{value}</div>
      {sub && <div className="mt-1 text-[11px] text-ink-4">{sub}</div>}
    </div>
  );
  return href ? <Link href={href} className="block">{inner}</Link> : inner;
}

/** A percentage value with a muted "no data yet" fallback. */
function PctValue({ pct, total }: { pct: number | null; total: number }) {
  if (pct == null) return <span className="text-[12px] text-ink-4">{total ? "—" : "No data"}</span>;
  const tone = pct >= 99 ? "var(--con-ok)" : pct >= 90 ? "var(--con-brand)" : "var(--con-err)";
  return <span className="font-mono tabular-nums text-[18px] font-medium" style={{ color: tone }}>{pct.toFixed(1)}%</span>;
}

/** A section-hub card: icon + title + one live quick-stat, links to the tab. */
function SectionCard({ href, icon, title, stat }: { href: string; icon: React.ReactNode; title: string; stat: string }) {
  return (
    <Link href={href} className="group block rounded-[10px] border border-hx bg-surface p-3 hover:border-hx-2 hover:bg-surface-hi transition-colors">
      <div className="flex items-center gap-2">
        <span className="grid place-items-center h-7 w-7 rounded-lg bg-app-2 text-ink-3 group-hover:text-ink-2">{icon}</span>
        <span className="text-[12.5px] font-medium text-ink flex-1 min-w-0 truncate">{title}</span>
        <ChevronRight className="h-3.5 w-3.5 text-ink-4 group-hover:text-ink-2" />
      </div>
      <div className="mt-2 text-[12px] text-ink-3 truncate">{stat}</div>
    </Link>
  );
}

// ─── Page ───────────────────────────────────────────────────────

export default function ProjectDetailPage() {
  const projectKey = String(useParams<{ id: string }>().id);
  const { id } = useProjectKey(projectKey);
  const { token, can } = useAuth();
  const canWrite = can("project:write");
  const [project, setProject] = useState<APIProject | null>(null);
  const [overview, setOverview] = useState<ProjectOverview | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [holdPrompt, setHoldPrompt] = useState(false);
  const [askOpen, setAskOpen] = useState(false);
  const [pendingApprovals, setPendingApprovals] = useState(0);
  const [hub, setHub] = useState<{ reqs: number; artifacts: number; sources: number; targets: number } | null>(null);

  // Pending run-requests count for the PM status view (best-effort).
  useEffect(() => {
    if (!id) return;
    listRunRequests(String(id))
      .then((rs) => setPendingApprovals(rs.filter((r) => r.status === "pending").length))
      .catch(() => setPendingApprovals(0));
  }, [id]);

  // Quick counts for the section hub (best-effort; each tab is the source of truth).
  useEffect(() => {
    if (!id) return;
    Promise.all([
      listProjectRequirements(String(id)).catch(() => []),
      listProjectArtifacts(token, String(id)).catch(() => []),
      listConnections(String(id), "source").catch(() => []),
      listConnections(String(id), "target").catch(() => []),
    ]).then(([reqs, arts, src, tgt]) => {
      const chains = new Set(reqs.map((r) => r.root_id || r.id)).size;
      setHub({ reqs: chains, artifacts: arts.length, sources: src.length, targets: tgt.length });
    });
  }, [id, token]);

  const load = useCallback(async () => {
    if (!id) return;
    // SC-010: auth via the HttpOnly cookie (credentials:"include"); no token gate.
    setLoading(true);
    setError("");
    try {
      const [pRes, oRes] = await Promise.all([
        fetch(`${API_BASE}/api/v1/projects/${id}`, { credentials: "include" }),
        fetch(`${API_BASE}/api/v1/projects/${id}/overview`, { credentials: "include" }),
      ]);

      // The project endpoint is the source of truth for existence: a 404 here
      // means the project genuinely doesn't exist; any other non-OK is treated
      // as a transient/retryable failure.
      if (pRes.status === 404) {
        setProject(null);
        setOverview(null);
        setError("Project not found — it may have been deleted or you don't have access.");
        return;
      }
      if (!pRes.ok) {
        throw new Error(`project ${pRes.status}`);
      }

      const projectData: APIProject = await pRes.json();
      setProject(projectData);

      // Overview is supplementary — if it fails we still show the project, but
      // surface a (dismissable) error so the user knows metrics are stale.
      if (oRes.ok) {
        setOverview(await oRes.json());
      } else {
        setOverview(null);
        if (oRes.status !== 404) {
          setError("Couldn't load this project's overview — retry to refresh metrics.");
        }
      }
    } catch {
      // Network failure or a non-404 project error: keep whatever we had and
      // let the user retry rather than showing a silent blank page.
      setError("Couldn't load this project — retry.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  // Real name once loaded; a neutral placeholder while the fetch is in flight
  // (never "Untitled" for a project that actually has a name).
  const displayName = project?.name || (loading ? "Loading…" : "Untitled project");
  const shortId = String(id).slice(0, 8);
  // Register id → name so breadcrumbs (here + deep sub-pages) show the project
  // name instead of the raw id.
  useRegisterCrumbLabel(projectKey, project?.name);
  const createdLabel = project?.created_at
    ? new Date(project.created_at).toLocaleDateString(undefined, {
        month: "short", day: "numeric", year: "numeric",
      }).toUpperCase()
    : null;
  const createdBy = project?.created_by_name || project?.owner_name;

  const eyebrow = `${shortId}${createdLabel ? ` · STARTED ${createdLabel}` : ""}${
    createdBy ? ` BY ${createdBy.toUpperCase()}` : ""
  }`;

  // Real counts come from the overview endpoint (introspected metadata).
  const tableCount = overview?.table_count ?? project?.table_count;
  const schemaCount = overview?.schema_count ?? project?.schema_count;
  const metricBits = [
    tableCount !== undefined ? `${tableCount} tables` : null,
    schemaCount !== undefined ? `${schemaCount} schemas` : null,
  ].filter(Boolean);
  const metric = metricBits.length ? metricBits.join(" · ") : undefined;

  const run = overview?.latest_run ?? null;
  const environment =
    project?.environments?.join(", ") || project?.environment || null;

  return (
    <AppShell
      eyebrow={eyebrow}
      title={displayName}
      crumbs={[{ label: "Projects", href: "/projects" }, { label: displayName }]}
      metric={project?.on_hold ? `⏸ ON HOLD${metric ? ` · ${metric}` : ""}` : metric}
      actions={
        <>
          {canWrite && (
            project?.on_hold ? (
              <Button variant="outline" onClick={() => setHoldPrompt(true)}>
                <Play className="h-3.5 w-3.5" /> Set live
              </Button>
            ) : (
              <Button variant="outline" onClick={() => setHoldPrompt(true)}>
                <Pause className="h-3.5 w-3.5" /> Hold
              </Button>
            )
          )}
          <Link href={`/projects/${projectKey}/sprints`}>
            <Button variant="outline">
              Sprints
            </Button>
          </Link>
          <Link href={`/projects/${projectKey}/developer-workspace`}>
            <Button variant="outline">
              <Eye className="h-3.5 w-3.5" /> Open workspace
            </Button>
          </Link>
          <Button variant="primary" onClick={() => setAskOpen(true)}>
            <Sparkles className="h-3.5 w-3.5" /> Ask Helix about this
          </Button>
        </>
      }
    >
      {error && (
        <div className="mb-4 flex items-center gap-3">
          <div className="flex-1">
            <ErrorBanner message={error} onDismiss={() => setError("")} />
          </div>
          <Button variant="outline" onClick={() => load()} loading={loading}>
            <RotateCw className="h-3.5 w-3.5" /> Retry
          </Button>
        </div>
      )}

      <div className="flex flex-col gap-4">
        {/* PM status row — every status at a glance. */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <StatusTile label="Status" value={<StatusBadge status={project?.status ?? "draft"} />} />
          <StatusTile label="Operational" value={
            <Chip tone={project?.on_hold ? "amber" : "green"} dot>{project?.on_hold ? "On hold" : "Live"}</Chip>
          } />
          <StatusTile
            label="Run approval"
            value={<Chip tone={project?.require_run_approval ? "indigo" : "zinc"}>{project?.require_run_approval ? "Required" : "Direct"}</Chip>}
            sub={pendingApprovals > 0 ? `${pendingApprovals} pending` : undefined}
          />
          <StatusTile
            label="Pipeline"
            value={run ? <StatusBadge status={run.status} /> : <span className="text-[12px] text-ink-4">Not started</span>}
            sub={run ? `${run.steps_done}/${run.steps_total} steps` : undefined}
          />
          <StatusTile
            label="Validation"
            value={<PctValue pct={overview?.validation.pct ?? null} total={overview?.validation.total ?? 0} />}
          />
          <StatusTile
            label="Reconciliation"
            value={<PctValue pct={overview?.recon.pct ?? null} total={overview?.recon.total ?? 0} />}
          />
        </div>

        {/* Section hub — quick live update from every sub-page, one jump away. */}
        <div>
          <div className="eyebrow mb-2">PROJECT SECTIONS</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {(() => {
              const b = `/projects/${projectKey}`;
              const reqN = hub?.reqs ?? 0;
              const artN = hub?.artifacts ?? 0;
              const st = project?.source_system, tg = project?.target_system;
              const vp = overview?.validation.pct, rp = overview?.recon.pct;
              const cards: { href: string; icon: React.ReactNode; title: string; stat: string }[] = [
                { href: `${b}/requirements`, icon: <ListChecks className="h-4 w-4" />, title: "Requirements", stat: reqN ? `${reqN} requirement${reqN > 1 ? "s" : ""}` : "None yet" },
                { href: `${b}/source-target`, icon: <Database className="h-4 w-4" />, title: "Source & Target", stat: (st || tg) ? `${st ?? "?"} → ${tg ?? "?"}` : "Not configured" },
                { href: `${b}/agents`, icon: <WorkflowIcon className="h-4 w-4" />, title: "Workflows", stat: run ? `${run.status} · ${run.steps_done}/${run.steps_total}` : "No runs yet" },
                { href: `${b}/artifacts`, icon: <FileCode className="h-4 w-4" />, title: "Artifacts", stat: artN ? `${artN} artifact${artN > 1 ? "s" : ""}` : "None yet" },
                { href: `${b}/validation`, icon: <ShieldCheck className="h-4 w-4" />, title: "Validation", stat: vp != null ? `${vp.toFixed(1)}% passed` : "Not run" },
                { href: `${b}/recon`, icon: <GitCompare className="h-4 w-4" />, title: "Reconciliation", stat: rp != null ? `${rp.toFixed(1)}% verified` : "Not run" },
                { href: `${b}/cutover`, icon: <Rocket className="h-4 w-4" />, title: "Cutover", stat: "Plan & execute" },
                { href: `${b}/developer-workspace`, icon: <Terminal className="h-4 w-4" />, title: "Developer Workspace", stat: artN ? `${artN} file${artN > 1 ? "s" : ""}` : "No code yet" },
                { href: `${b}/compliance`, icon: <FileCheck2 className="h-4 w-4" />, title: "Compliance", stat: "Audit & export" },
                { href: `${b}/reports`, icon: <BarChart3 className="h-4 w-4" />, title: "Reports", stat: "Summary & exports" },
                { href: `${b}/approvals`, icon: <CheckSquare className="h-4 w-4" />, title: "Approvals", stat: pendingApprovals ? `${pendingApprovals} pending` : "None pending" },
                { href: `${b}/timeline`, icon: <Clock className="h-4 w-4" />, title: "Timeline", stat: "Activity history" },
              ];
              return cards.map((c) => <SectionCard key={c.href} {...c} />);
            })()}
          </div>
        </div>

        {/* Pipeline progress — REAL steps from the latest workflow run, or an
            honest empty state when nothing has run. No hardcoded phase ladder. */}
        <Card>
          {run ? (
            <>
              <div className="flex items-center justify-between mb-3.5">
                <div>
                  <div className="eyebrow">PIPELINE · {run.kind.toUpperCase()} · {run.status.toUpperCase()}</div>
                  <div className="text-[14px] font-semibold mt-1">
                    {run.steps_done} of {run.steps_total} steps complete
                  </div>
                </div>
                <span className="font-mono tabular-nums text-[30px] font-medium tracking-editorial">
                  {run.steps_total ? Math.round((run.steps_done / run.steps_total) * 100) : 0}%
                </span>
              </div>
              <div className="grid gap-1" style={{ gridTemplateColumns: `repeat(${Math.max(run.steps.length, 1)}, 1fr)` }}>
                {run.steps.map((s) => {
                  const st = (s.status || "").toLowerCase();
                  const bg = st === "completed" || st === "approved" ? "var(--con-ink-1)"
                    : st === "running" || st === "in_progress" ? "var(--con-brand)"
                    : st === "failed" || st === "rejected" ? "var(--con-err)"
                    : "var(--con-bg-2)";
                  return (
                    <div key={`${s.agent}-${s.order}`} className="flex flex-col gap-1.5" title={s.error || s.status}>
                      <div className="h-1 rounded-sm" style={{ background: bg }} />
                      <div className="flex items-center gap-1 text-[11px] truncate" style={{ color: st === "pending" ? "var(--con-ink-4)" : "var(--con-ink-2)" }}>
                        {(st === "running" || st === "in_progress") && (
                          <span className="animate-pulse-dot inline-block rounded-full" style={{ width: 5, height: 5, background: "var(--con-brand)" }} />
                        )}
                        <span className="truncate">{s.agent}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          ) : (
            <div className="flex items-center justify-between">
              <div>
                <div className="eyebrow">PIPELINE</div>
                <div className="text-[14px] font-semibold mt-1">No workflow run yet</div>
                <div className="text-[12px] text-ink-3 mt-0.5">Start the migration pipeline to plan + generate this migration.</div>
              </div>
              <Link href={`/projects/${projectKey}/agents`}><Button variant="primary"><Play className="h-3.5 w-3.5" /> View agents</Button></Link>
            </div>
          )}
        </Card>

        {/* Two-column main layout */}
        <div className="grid grid-cols-3 gap-4">
          {/* LEFT */}
          <div className="col-span-2 flex flex-col gap-4">
            {/* Migration by schema — REAL: introspected source schemas + tables
                + row counts. Populated once the SchemaAnalyst introspects the
                source; honest empty state until then. */}
            <Card
              title="Migration by schema"
              description="Introspected schemas · tables · row counts"
            >
              {overview?.schemas?.length ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-[12.5px]">
                    <thead>
                      <tr className="text-[10.5px] uppercase tracking-[0.08em] text-ink-4 font-mono text-left">
                        <th className="py-2 font-medium">Schema</th>
                        <th className="py-2 font-medium">Type</th>
                        <th className="py-2 font-medium text-right">Tables</th>
                        <th className="py-2 font-medium text-right">Rows</th>
                      </tr>
                    </thead>
                    <tbody>
                      {overview.schemas.map((s, i) => (
                        <tr key={`${s.schema}-${i}`} className={i === overview.schemas.length - 1 ? "" : "border-b border-hx"}>
                          <td className="py-2.5 font-mono text-ink font-medium">{s.schema}</td>
                          <td className="py-2.5"><Chip tone="default">{s.schema_type}</Chip></td>
                          <td className="py-2.5 font-mono tabular-nums text-right text-ink-2">{s.tables}</td>
                          <td className="py-2.5 font-mono tabular-nums text-right text-ink-3">{s.rows.toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="py-6 text-center text-[12.5px] text-ink-4">
                  No schema data yet — run the migration pipeline to introspect the source.
                </div>
              )}
            </Card>

            {/* Latest workflow run — REAL steps with live status + clickable
                artifacts (links to the Agents page). */}
            <Card
              title="Latest workflow run"
              eyebrow={run ? `${run.kind.toUpperCase()} · ${run.status.toUpperCase()}` : "WORKFLOW"}
              description={run ? `${run.steps_done}/${run.steps_total} steps · ${run.mode ?? ""}` : "No run yet"}
              actions={
                <Link href={`/projects/${projectKey}/agents`}>
                  <Button variant="ghost" size="sm">Open in Agents →</Button>
                </Link>
              }
            >
              {run?.steps?.length ? (
                <div className="flex flex-col gap-1.5">
                  {run.steps.map((a) => {
                    const st = (a.status || "").toLowerCase();
                    const sIcon = (st === "completed" || st === "approved")
                      ? <Check className="h-[11px] w-[11px]" />
                      : (st === "running" || st === "in_progress")
                        ? <span className="animate-spin rounded-full" style={{ width: 11, height: 11, border: "2px solid var(--con-brand)", borderRightColor: "transparent" }} />
                        : <span className="rounded-full inline-block" style={{ width: 6, height: 6, background: st === "failed" ? "var(--con-err)" : "var(--con-ink-5)" }} />;
                    const iconColor = (st === "completed" || st === "approved") ? "var(--con-ok)" : (st === "running" || st === "in_progress") ? "var(--con-brand)" : st === "failed" ? "var(--con-err)" : "var(--con-ink-5)";
                    return (
                      <div key={`${a.agent}-${a.order}`} className="grid items-center gap-3 py-1 text-[12.5px]" style={{ gridTemplateColumns: "20px 1fr 90px 1fr" }} title={a.error || a.status}>
                        <div className="grid place-items-center" style={{ color: iconColor, width: 20 }}>{sIcon}</div>
                        <span className="flex items-center gap-2 min-w-0">
                          <AgentIcon name={a.agent} size={18} />
                          <span className="font-medium truncate">{a.agent}</span>
                        </span>
                        <StatusBadge status={a.status} />
                        {a.artifact_path ? (
                          <span className="font-mono text-[11.5px] inline-flex items-center gap-1 text-ink-3 truncate">
                            <FileText className="h-3 w-3" /> {a.artifact_path.split("/").pop()}
                          </span>
                        ) : <span />}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="py-6 text-center text-[12.5px] text-ink-4">
                  No workflow runs yet. Start one from the Agents page.
                </div>
              )}
            </Card>
          </div>

          {/* RIGHT */}
          <div className="flex flex-col gap-4">
            <Card
              title="Details"
              actions={canWrite ? (
                <Button variant="ghost" size="sm" onClick={() => setEditing(true)}>
                  <Pencil className="h-3.5 w-3.5" /> Edit
                </Button>
              ) : undefined}
            >
              <dl
                className="grid text-[12.5px] m-0"
                style={{
                  gridTemplateColumns: "1fr 1fr",
                  gap: "14px 12px",
                }}
              >
                <Detail k="Project ID" v={shortId} mono />
                <Detail
                  k="Created"
                  v={
                    project?.created_at
                      ? new Date(project.created_at).toLocaleDateString(undefined, {
                          month: "short", day: "numeric", year: "numeric",
                        })
                      : "—"
                  }
                />
                <Detail
                  k="Source"
                  v={<SourceTarget source={project?.source_system} target={project?.target_system} />}
                  span={2}
                />
                <Detail k="Schemas" v={schemaCount ?? "—"} />
                <Detail k="Tables" v={tableCount ?? "—"} />
                <Detail
                  k="Owner"
                  v={
                    project?.owner_name ? (
                      <span className="inline-flex items-center gap-1.5">
                        <Avatar name={project.owner_name} size={18} />
                        {project.owner_name}
                      </span>
                    ) : (
                      "—"
                    )
                  }
                />
                <Detail k="Status" v={project?.status ? <StatusBadge status={project.status} /> : "—"} />
                <Detail
                  k="Environment"
                  v={environment ? <Chip mono>{environment}</Chip> : "—"}
                />
                <Detail k="On hold" v={project?.on_hold ? <Chip tone="warn" dot>On hold</Chip> : <Chip tone="ok" dot>Live</Chip>} />
              </dl>
            </Card>

            {/* Validation & reconciliation rollup — the trust signals. */}
            <Card title="Quality" description="Validation & reconciliation outcomes">
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-[8px] border border-hx p-3">
                  <div className="text-[10px] uppercase tracking-wider font-mono text-ink-4">Validation</div>
                  <div className="font-mono tabular-nums text-[22px] mt-1">{overview?.validation.pct != null ? `${overview.validation.pct}%` : "—"}</div>
                  <div className="text-[11px] text-ink-4">{overview?.validation.total ? `${overview.validation.total} results` : "no runs yet"}</div>
                </div>
                <div className="rounded-[8px] border border-hx p-3">
                  <div className="text-[10px] uppercase tracking-wider font-mono text-ink-4">Reconciliation</div>
                  <div className="font-mono tabular-nums text-[22px] mt-1">{overview?.recon.pct != null ? `${overview.recon.pct}%` : "—"}</div>
                  <div className="text-[11px] text-ink-4">{overview?.recon.total ? `${overview.recon.total} results` : "no runs yet"}</div>
                </div>
              </div>
            </Card>

            <CommentsCard projectId={String(id)} canWrite={canWrite} refreshKey={String(project?.on_hold)} />
          </div>
        </div>
      </div>

      {editing && project && (
        <EditProjectModal
          projectId={String(id)}
          current={{ owner_id: project.owner_id, status: project.status }}
          onClose={() => setEditing(false)}
          onSaved={() => { setEditing(false); load(); }}
        />
      )}

      <AskProject
        projectId={String(id)}
        projectName={displayName}
        open={askOpen}
        onClose={() => setAskOpen(false)}
      />

      {holdPrompt && project && (
        <HoldModal
          projectId={String(id)}
          onHold={!project.on_hold}
          onClose={() => setHoldPrompt(false)}
          onSaved={() => { setHoldPrompt(false); load(); }}
        />
      )}
    </AppShell>
  );
}

// Proper, readable date-time for the comments timeline.
function formatDateTime(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric",
    hour: "numeric", minute: "2-digit",
  });
}
function relTime(iso: string | null): string {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function HoldModal({ projectId, onHold, onClose, onSaved }: {
  projectId: string;
  onHold: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [comment, setComment] = useState("");
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);
  const save = async () => {
    if (!comment.trim()) { setErr("A reason is required."); return; }
    setSaving(true); setErr("");
    try { await setProjectHold(projectId, onHold, comment.trim()); onSaved(); }
    catch (e: unknown) { setErr(e instanceof Error ? e.message : "Failed"); }
    finally { setSaving(false); }
  };
  return (
    <Modal open onClose={onClose} title={onHold ? "Put project on hold" : "Set project live"} width="sm">
      <div className="space-y-4">
        {err && <ErrorBanner message={err} onDismiss={() => setErr("")} />}
        <p className="text-[12.5px] text-ink-3">
          {onHold
            ? "While on hold, new BMAD/agent workflows can't be started. Add a reason — it's recorded on the project timeline."
            : "This resumes the project so workflows can run again. Add a note — it's recorded on the project timeline."}
        </p>
        <label className="flex flex-col gap-1.5">
          <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">Reason / note</span>
          <textarea value={comment} onChange={(e) => setComment(e.target.value)} rows={3}
            placeholder={onHold ? "e.g. Pausing for source credential review" : "e.g. Credentials verified, resuming"}
            className="px-2.5 py-2 text-[13px] rounded-[8px] border border-hx bg-surface focus-ring resize-y" />
        </label>
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} loading={saving}>{onHold ? "Put on hold" : "Set live"}</Button>
        </div>
      </div>
    </Modal>
  );
}

function CommentsCard({ projectId, canWrite, refreshKey }: { projectId: string; canWrite: boolean; refreshKey?: string }) {
  const [comments, setComments] = useState<ProjectCommentT[] | null>(null);
  const [body, setBody] = useState("");
  const [err, setErr] = useState("");
  const [posting, setPosting] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const PREVIEW = 3;

  const load = () => { fetchProjectComments(projectId).then(setComments).catch(() => setComments([])); };
  // Reload on mount, and whenever hold/live toggles (refreshKey changes) so the
  // new hold/live timeline entry appears without a manual refresh.
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [projectId, refreshKey]);

  const post = async () => {
    if (!body.trim()) return;
    setPosting(true); setErr("");
    try {
      // Prepend the saved comment immediately (newest-first) so it shows
      // without a manual refresh; no full reload needed.
      const created = await addProjectComment(projectId, body.trim());
      setComments((prev) => [created, ...(prev ?? [])]);
      setBody("");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to post");
    } finally {
      setPosting(false);
    }
  };

  const kindDot = (k: string) =>
    k === "hold" ? "var(--con-warn)" : k === "live" ? "var(--con-ok)" : "var(--con-ink-4)";

  return (
    <Card title="Comments & activity" description="Notes, plus hold/live events">
      {canWrite && (
        <div className="flex flex-col gap-2 mb-3">
          {err && <ErrorBanner message={err} onDismiss={() => setErr("")} />}
          <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={2}
            placeholder="Add a comment…"
            className="px-2.5 py-2 text-[13px] rounded-[8px] border border-hx bg-surface focus-ring resize-y" />
          <div className="flex justify-end">
            <Button size="sm" onClick={post} loading={posting} disabled={!body.trim()}>Comment</Button>
          </div>
        </div>
      )}
      {comments === null ? (
        <p className="text-[12px] text-ink-4">Loading…</p>
      ) : comments.length === 0 ? (
        <p className="text-[12px] text-ink-4">No comments yet.</p>
      ) : (
        <>
          <ul className="flex flex-col gap-3">
            {(expanded ? comments : comments.slice(0, PREVIEW)).map((c) => (
              <li key={c.id} className="flex items-start gap-2.5">
                <span className="mt-1.5 h-1.5 w-1.5 rounded-full flex-shrink-0" style={{ background: kindDot(c.kind) }} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[12.5px] font-medium text-ink">{c.author_name || "System"}</span>
                    {c.kind !== "comment" && <Chip tone={c.kind === "hold" ? "warn" : "ok"}>{c.kind === "hold" ? "Put on hold" : "Set live"}</Chip>}
                    <span className="text-[10.5px] text-ink-4 font-mono" title={formatDateTime(c.created_at)}>
                      {formatDateTime(c.created_at)} · {relTime(c.created_at)}
                    </span>
                  </div>
                  <p className="text-[12.5px] text-ink-2 mt-0.5 whitespace-pre-wrap break-words">{c.body}</p>
                </div>
              </li>
            ))}
          </ul>
          {comments.length > PREVIEW && (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="mt-3 text-[12px] font-medium text-[var(--con-brand)] hover:underline"
            >
              {expanded ? "Show less" : `Show ${comments.length - PREVIEW} more`}
            </button>
          )}
        </>
      )}
    </Card>
  );
}

function EditProjectModal({ projectId, current, onClose, onSaved }: {
  projectId: string;
  current: { owner_id?: string; status?: string };
  onClose: () => void;
  onSaved: () => void;
}) {
  const [members, setMembers] = useState<OrgMember[]>([]);
  const [ownerId, setOwnerId] = useState(current.owner_id ?? "");
  const [status, setStatus] = useState(current.status ?? "draft");
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => { fetchProjectMembers().then(setMembers).catch(() => setMembers([])); }, []);

  const save = async () => {
    setSaving(true); setErr("");
    try {
      await updateProject(projectId, { owner_id: ownerId || undefined, status });
      onSaved();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Update failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Edit project" width="sm">
      <div className="space-y-4">
        {err && <ErrorBanner message={err} onDismiss={() => setErr("")} />}
        <label className="flex flex-col gap-1.5">
          <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">Owner</span>
          <select value={ownerId} onChange={(e) => setOwnerId(e.target.value)} className="h-9 px-2.5 text-[13px] rounded-[8px] border border-hx bg-surface focus-ring">
            <option value="">— Select owner —</option>
            {members.map((m) => <option key={m.user_id} value={m.user_id}>{m.name || m.email}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">Status</span>
          <select value={status} onChange={(e) => setStatus(e.target.value)} className="h-9 px-2.5 text-[13px] rounded-[8px] border border-hx bg-surface focus-ring">
            {["draft", "running", "awaiting", "completed", "failed", "archived"].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} loading={saving}>Save changes</Button>
        </div>
      </div>
    </Modal>
  );
}

// ─── Helpers ───────────────────────────────────────────────────

function Detail({
  k,
  v,
  mono,
  span,
}: {
  k: string;
  v: React.ReactNode;
  mono?: boolean;
  span?: number;
}) {
  return (
    <div style={{ gridColumn: span ? `span ${span}` : undefined }}>
      <dt className="eyebrow text-[9.5px]">{k}</dt>
      <dd
        className={`m-0 mt-1 text-ink ${mono ? "font-mono" : ""}`}
      >
        {v}
      </dd>
    </div>
  );
}
