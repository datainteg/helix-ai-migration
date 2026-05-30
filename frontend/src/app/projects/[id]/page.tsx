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

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  Pause,
  Eye,
  Sparkles,
  Check,
  FileText,
  ArrowRight,
} from "lucide-react";

import { AppShell } from "@/components/layout";
import { AppIcon, AgentIcon } from "@/components/icons";
import {
  Avatar,
  Button,
  Card,
  Chip,
  ProgressBar,
  StatusBadge,
  ErrorBanner,
} from "@/components/ui";
import { useAuth } from "@/lib/auth-context";

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
  owner_name?: string;
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

// ─── Fallback / default phase list (used when API doesn't ship one) ─

const DEFAULT_PHASES: APIPhase[] = [
  { id: "intake",       label: "Intake",         status: "pending" },
  { id: "analysis",     label: "Analysis",       status: "pending" },
  { id: "planning",     label: "Planning",       status: "pending" },
  { id: "architecture", label: "Architecture",   status: "pending" },
  { id: "approval",     label: "Approval gate",  status: "pending" },
  { id: "impl",         label: "Implementation", status: "pending" },
  { id: "validation",   label: "Validation",     status: "pending" },
  { id: "recon",        label: "Reconciliation", status: "pending" },
  { id: "cutover",      label: "Cutover",        status: "pending" },
];

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

// ─── Page ───────────────────────────────────────────────────────

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();
  const [project, setProject] = useState<APIProject | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    // SC-010: auth via the HttpOnly cookie (credentials:"include"); no token gate.
    fetch(`${API_BASE}/api/v1/projects/${id}`, {
      credentials: "include",
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => setProject(data ?? null))
      .catch(() => setProject(null));
  }, [id]);

  const displayName = project?.name || "Untitled project";
  const shortId = String(id).slice(0, 8);
  const createdLabel = project?.created_at
    ? new Date(project.created_at).toLocaleDateString(undefined, {
        month: "short", day: "numeric", year: "numeric",
      }).toUpperCase()
    : null;
  const createdBy = project?.created_by_name || project?.owner_name;

  const eyebrow = `${shortId}${createdLabel ? ` · STARTED ${createdLabel}` : ""}${
    createdBy ? ` BY ${createdBy.toUpperCase()}` : ""
  }`;

  const metricBits = [
    project?.table_count !== undefined ? `${project.table_count} tables` : null,
    project?.total_size || null,
    project?.schema_count !== undefined ? `${project.schema_count} schemas` : null,
  ].filter(Boolean);
  const metric = metricBits.length ? metricBits.join(" · ") : undefined;

  const phases: APIPhase[] = project?.phases?.length ? project.phases : DEFAULT_PHASES;
  const phasesComplete = project?.phases_complete ?? phases.filter((p) => p.status === "completed").length;
  const phasesTotal = project?.phases_total ?? phases.length;
  const progress = project?.progress_pct ?? 0;
  const phaseLabel = project?.phase_label || phases.find((p) => p.status === "running")?.label;
  const tablesDone = project?.tables_done;
  const tablesTotal = project?.table_count;

  const environment =
    project?.environments?.join(", ") || project?.environment || null;

  return (
    <AppShell
      eyebrow={eyebrow}
      title={displayName}
      metric={metric}
      crumbs={["Projects", displayName]}
      actions={
        <>
          <Button variant="outline">
            <Pause className="h-3.5 w-3.5" /> Pause
          </Button>
          <Link href={`/projects/${id}/sprints`}>
            <Button variant="outline">
              Sprints
            </Button>
          </Link>
          <Link href={`/projects/${id}/developer-workspace`}>
            <Button variant="outline">
              <Eye className="h-3.5 w-3.5" /> Open workspace
            </Button>
          </Link>
          <Button variant="primary">
            <Sparkles className="h-3.5 w-3.5" /> Ask Helix about this
          </Button>
        </>
      }
    >
      {error && (
        <div className="mb-4">
          <ErrorBanner message={error} onDismiss={() => setError("")} />
        </div>
      )}

      <div className="flex flex-col gap-4">
        {/* Phase ticker */}
        <Card>
          <div className="flex items-center justify-between mb-3.5">
            <div>
              <div className="eyebrow">
                PROGRESS{phaseLabel ? ` · ${phaseLabel.toUpperCase()} PHASE` : ""}
              </div>
              <div className="text-[14px] font-semibold mt-1">
                {phasesComplete} of {phasesTotal} phases complete
                {tablesDone !== undefined && tablesTotal !== undefined
                  ? ` · ${tablesDone} of ${tablesTotal} tables migrated`
                  : ""}
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="font-mono tabular-nums text-[30px] font-medium tracking-editorial">
                {progress}%
              </span>
              {project?.eta && (
                <span className="text-ink-3 text-[11.5px]">· ETA {project.eta}</span>
              )}
            </div>
          </div>
          <div
            className="grid gap-1"
            style={{ gridTemplateColumns: `repeat(${phases.length}, 1fr)` }}
          >
            {phases.map((ph) => {
              const baseBg =
                ph.status === "completed"
                  ? "var(--con-ink-1)"
                  : ph.status === "running"
                  ? "var(--con-brand)"
                  : "var(--con-bg-2)";
              return (
                <div key={ph.id} className="flex flex-col gap-1.5">
                  <div
                    className="h-1 rounded-sm relative"
                    style={{ background: baseBg }}
                  >
                    {ph.status === "running" && (
                      <div
                        className="absolute left-0 top-0 h-full rounded-sm"
                        style={{
                          width: "55%",
                          background: "var(--con-brand)",
                        }}
                      />
                    )}
                  </div>
                  <div
                    className="flex items-center gap-1 text-[11px]"
                    style={{
                      color:
                        ph.status === "pending"
                          ? "var(--con-ink-4)"
                          : "var(--con-ink-2)",
                    }}
                  >
                    {ph.status === "running" && (
                      <span
                        className="animate-pulse-dot inline-block rounded-full"
                        style={{
                          width: 5,
                          height: 5,
                          background: "var(--con-brand)",
                        }}
                      />
                    )}
                    {ph.label}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        {/* Two-column main layout */}
        <div className="grid grid-cols-3 gap-4">
          {/* LEFT */}
          <div className="col-span-2 flex flex-col gap-4">
            {/* Migration by schema */}
            <Card
              title="Migration by schema"
              description="Tables · row counts · target byte size"
            >
              {project?.schemas?.length ? (
                project.schemas.map((s, i) => {
                  const pct = s.tables && s.done !== undefined ? (s.done / s.tables) * 100 : 0;
                  const tone =
                    s.status === "completed" ? "ok"
                    : s.status === "running" ? "brand"
                    : "ink";
                  return (
                    <div
                      key={s.schema}
                      className={`grid items-center gap-3.5 py-3 ${
                        i === (project.schemas?.length ?? 0) - 1 ? "" : "border-b border-hx"
                      }`}
                      style={{ gridTemplateColumns: "160px 110px 1fr 110px 100px 80px" }}
                    >
                      <div>
                        <div className="font-mono text-[12.5px] text-ink font-medium">{s.schema}</div>
                        <div className="font-mono text-[10.5px] text-ink-4 mt-0.5">
                          {s.tables ?? "—"} tables
                        </div>
                      </div>
                      <div className="font-mono tabular-nums text-[12px] text-ink-2">
                        {s.done ?? "—"} / {s.tables ?? "—"}
                      </div>
                      <div>
                        <ProgressBar value={pct} tone={tone} />
                      </div>
                      <span className="font-mono text-[11.5px] text-ink-3 text-right">
                        {s.rows ?? "—"} rows
                      </span>
                      <span className="font-mono text-[11.5px] text-ink-3 text-right">
                        {s.size ?? "—"}
                      </span>
                      {s.status ? <StatusBadge status={s.status} /> : <span className="text-ink-5 font-mono text-[11px]">—</span>}
                    </div>
                  );
                })
              ) : (
                <div className="py-6 text-center text-[12.5px] text-ink-4">
                  No schema breakdown available.
                </div>
              )}
            </Card>

            {/* Active BMAD workflow */}
            <Card
              title="Active BMAD workflow"
              eyebrow={
                project?.workflow_id
                  ? `WORKFLOW ${project.workflow_id.toUpperCase()}`
                  : "WORKFLOW"
              }
              description={
                project?.workflow_started || project?.workflow_mode
                  ? `${project.workflow_started ?? "—"}${
                      project.workflow_mode ? ` · Mode: ${project.workflow_mode}` : ""
                    }`
                  : "No active workflow"
              }
              actions={
                <Link href={`/projects/${id}/agents`}>
                  <Button variant="ghost" size="sm">Open workflow →</Button>
                </Link>
              }
            >
              {project?.workflow_steps?.length ? (
                <div className="flex flex-col gap-1.5">
                  {project.workflow_steps.map((a, i) => {
                    const sIcon =
                      a.status === "completed" ? (
                        <Check className="h-[11px] w-[11px]" />
                      ) : a.status === "running" ? (
                        <span
                          className="animate-spin rounded-full"
                          style={{
                            width: 11,
                            height: 11,
                            border: "2px solid var(--con-brand)",
                            borderRightColor: "transparent",
                          }}
                        />
                      ) : (
                        <span
                          className="rounded-full inline-block"
                          style={{
                            width: 6,
                            height: 6,
                            background: "var(--con-ink-5)",
                          }}
                        />
                      );
                    const iconColor =
                      a.status === "completed" ? "var(--con-ok)"
                      : a.status === "running" ? "var(--con-brand)"
                      : "var(--con-ink-5)";
                    return (
                      <div
                        key={i}
                        className="grid items-center gap-3 py-1 text-[12.5px]"
                        style={{ gridTemplateColumns: "20px 110px 1fr 80px 100px" }}
                      >
                        <div
                          className="grid place-items-center"
                          style={{ color: iconColor, width: 20 }}
                        >
                          {sIcon}
                        </div>
                        <span className="flex items-center gap-2">
                          <AgentIcon name={a.name} size={18} />
                          <span className="font-medium">{a.name}</span>
                        </span>
                        <span
                          style={{
                            color:
                              a.status === "pending"
                                ? "var(--con-ink-4)"
                                : "var(--con-ink-2)",
                          }}
                        >
                          {a.role}
                        </span>
                        <span className="font-mono text-ink-4 text-[11px] text-right">
                          {a.duration ?? "—"}
                        </span>
                        {a.artifact ? (
                          <a
                            className="font-mono text-[11.5px] inline-flex items-center gap-1"
                            style={{ color: "var(--con-brand)" }}
                          >
                            <FileText className="h-3 w-3" /> {a.artifact}
                          </a>
                        ) : (
                          <span />
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="py-6 text-center text-[12.5px] text-ink-4">
                  No workflow runs yet.
                </div>
              )}
            </Card>
          </div>

          {/* RIGHT */}
          <div className="flex flex-col gap-4">
            <Card title="Details">
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
                <Detail k="Schemas" v={project?.schema_count ?? "—"} />
                <Detail k="Tables" v={project?.table_count ?? "—"} />
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
                <Detail k="Team" v={project?.team ?? "—"} />
                <Detail
                  k="Environment"
                  v={environment ? <Chip mono>{environment}</Chip> : "—"}
                />
                <Detail
                  k="LLM routing"
                  v={
                    project?.llm_routing ? (
                      <Chip tone="brand" mono>{project.llm_routing}</Chip>
                    ) : (
                      "—"
                    )
                  }
                />
              </dl>
            </Card>

            {project?.risk_score !== undefined && (
              <Card
                title="AI risk model"
                eyebrow={`HELIX RISK · ${project.risk_score}`}
              >
                <div className="flex items-baseline gap-2 mb-2.5">
                  <div
                    className="font-mono tabular-nums text-[36px] font-medium tracking-[-0.03em]"
                    style={{
                      color:
                        project.risk_score >= 80
                          ? "var(--con-err)"
                          : project.risk_score >= 60
                          ? "var(--con-warn)"
                          : "var(--con-ok)",
                    }}
                  >
                    {project.risk_score}
                  </div>
                  <div className="text-[11px] text-ink-3">
                    {project.risk_score >= 80
                      ? "HIGH"
                      : project.risk_score >= 60
                      ? "MEDIUM"
                      : "LOW"}
                    {project.risk_trend === "up"
                      ? " · trending ▲"
                      : project.risk_trend === "down"
                      ? " · trending ▼"
                      : ""}
                  </div>
                </div>
                {project.risk_factors?.length ? (
                  project.risk_factors.map((f) => (
                    <div
                      key={f.name}
                      className="grid items-center gap-2 py-1 text-[12px]"
                      style={{ gridTemplateColumns: "1fr 60px 32px" }}
                    >
                      <span className="text-ink-2">{f.name}</span>
                      <ProgressBar
                        value={f.value}
                        tone={f.value >= 80 ? "err" : f.value >= 60 ? "warn" : "ink"}
                        height={3}
                      />
                      <span className="font-mono tabular-nums text-[11px] text-ink-2 text-right">
                        {f.value}
                      </span>
                    </div>
                  ))
                ) : (
                  <p className="text-[12px] text-ink-4">No factor breakdown.</p>
                )}
              </Card>
            )}

            <Card title="Recent activity">
              {project?.recent_activity?.length ? (
                <div className="flex flex-col">
                  {project.recent_activity.map((a, i) => (
                    <div
                      key={i}
                      className={`grid items-start gap-3 py-2 ${
                        i === (project.recent_activity?.length ?? 0) - 1
                          ? ""
                          : "border-b border-hx"
                      }`}
                      style={{ gridTemplateColumns: "8px 1fr auto" }}
                    >
                      <span
                        className="rounded-full inline-block mt-1.5"
                        style={{
                          width: 6,
                          height: 6,
                          background: "var(--con-ink-5)",
                        }}
                      />
                      <div className="text-[12px] text-ink-2 leading-[1.5]">
                        <span className="font-medium text-ink">{a.who}</span>{" "}
                        {a.action}
                      </div>
                      <span className="font-mono text-[11px] text-ink-4">{a.time}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-[12px] text-ink-4">No recent activity.</p>
              )}
            </Card>
          </div>
        </div>
      </div>
    </AppShell>
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
