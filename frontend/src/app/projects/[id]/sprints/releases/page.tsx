"use client";

/**
 * /projects/[id]/sprints/releases — Migration Release Dashboard.
 *
 * Upcoming release hero + stage timeline + deployment checklist + all
 * releases table for the project. Pulls from the releases API.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { CheckCircle2, Circle, Rocket, ShieldCheck, ShieldAlert } from "lucide-react";

import { AppShell } from "@/components/layout";
import {
  Button,
  Card,
  Chip,
  EmptyState,
  LoadingState,
  ProgressBar,
  StatusBadge,
} from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import { useProjectKey } from "@/lib/projects/useProjectKey";
import {
  fetchReleases,
  seedSprints,
  type MigrationRelease,
  type ReleaseStage,
} from "@/lib/sprints";

const STAGES: { id: ReleaseStage; label: string }[] = [
  { id: "planned",          label: "Planned" },
  { id: "validation",       label: "Validation" },
  { id: "recon",            label: "Recon" },
  { id: "uat_ready",        label: "UAT ready" },
  { id: "approved",         label: "Approved" },
  { id: "production_ready", label: "Production ready" },
  { id: "released",         label: "Released" },
];

function stageIndex(stage: ReleaseStage): number {
  return STAGES.findIndex((s) => s.id === stage);
}

function scoreColor(v: number, kind: "validation" | "recon"): string {
  const threshold = kind === "validation" ? 95 : 99;
  if (v >= threshold) return "var(--con-ok)";
  if (v >= threshold - 20) return "var(--con-warn)";
  if (v > 0) return "var(--con-err)";
  return "var(--con-ink-4)";
}

export default function MigrationReleasesPage() {
  const projectKey = String(useParams<{ id: string }>().id);
  const { id: projectId } = useProjectKey(projectKey);
  const { token } = useAuth();

  const [releases, setReleases] = useState<MigrationRelease[]>([]);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);

  const load = useCallback(() => {
    if (!token || !projectId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    fetchReleases(token, projectId)
      .then(setReleases)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token, projectId]);

  useEffect(() => {
    load();
  }, [load]);

  const upcoming = releases[0];

  const checklistDone = useMemo(() => {
    if (!upcoming) return 0;
    if (upcoming.checklist.length === 0) return 0;
    const done = upcoming.checklist.filter((c) => c.done).length;
    return Math.round((done / upcoming.checklist.length) * 100);
  }, [upcoming]);

  const handleSeed = () => {
    if (!token || !projectId) return;
    setSeeding(true);
    seedSprints(token, projectId)
      .then(() => {
        load();
      })
      .catch(() => {})
      .finally(() => setSeeding(false));
  };

  if (loading) {
    return (
      <AppShell
        eyebrow={`SPRINTS · ${projectKey}`}
        title="Migration releases"
        crumbs={["Projects", projectKey, "Sprints", "Releases"]}
      >
        <LoadingState />
      </AppShell>
    );
  }

  if (!upcoming) {
    return (
      <AppShell
        eyebrow={`SPRINTS · ${projectKey}`}
        title="Migration releases"
        crumbs={["Projects", projectKey, "Sprints", "Releases"]}
      >
        <Card>
          <EmptyState
            icon={<Rocket className="h-4 w-4" />}
            title="No releases scheduled"
            description="Run the seed to populate demo data, or schedule a cutover from the API."
            action={
              <Button variant="primary" loading={seeding} onClick={handleSeed}>
                Run seed
              </Button>
            }
          />
        </Card>
      </AppShell>
    );
  }

  const activeStageIdx = stageIndex(upcoming.stage);

  return (
    <AppShell
      eyebrow={`SPRINTS · ${projectKey}`}
      title="Migration releases"
      description="Upcoming cutover, deployment checklist, and full release history."
      crumbs={["Projects", projectKey, "Sprints", "Releases"]}
    >
      {/* Hero — upcoming release */}
      <Card className="mb-6">
        <div className="flex flex-col lg:flex-row gap-6 lg:items-center">
          <div className="flex-1 min-w-0">
            <div className="eyebrow text-[10px] mb-2">UPCOMING CUTOVER</div>
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <Chip tone="brand" mono>{upcoming.targetEnvironment.toUpperCase()}</Chip>
              <StatusBadge status={upcoming.stage} />
              {upcoming.rollbackReady ? (
                <Chip tone="ok" dot>
                  <ShieldCheck className="h-3 w-3" /> Rollback ready
                </Chip>
              ) : (
                <Chip tone="err" dot>
                  <ShieldAlert className="h-3 w-3" /> Rollback NOT ready
                </Chip>
              )}
            </div>
            <h2 className="text-[20px] font-semibold text-ink tracking-tight">{upcoming.name}</h2>
            <div className="text-[12px] text-ink-3 mt-1 font-mono">
              {new Date(upcoming.scheduledFor).toLocaleString()}
              <span className="mx-2 text-ink-5">·</span>
              {upcoming.sprintIds.join(", ")}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-6 flex-shrink-0">
            <ScoreBox label="Validation" value={upcoming.validationScore} kind="validation" />
            <ScoreBox label="Recon"      value={upcoming.reconScore}      kind="recon" />
          </div>
        </div>
      </Card>

      {/* Stage timeline */}
      <Card title="Release stages" eyebrow="PIPELINE" className="mb-6">
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
          {STAGES.map((s, i) => {
            const done    = i <  activeStageIdx;
            const current = i === activeStageIdx;
            const bg      = done ? "var(--con-ok-soft)" : current ? "var(--con-brand-soft)" : "var(--con-bg-2)";
            const fg      = done ? "var(--con-ok)" : current ? "var(--con-brand)" : "var(--con-ink-4)";
            return (
              <div key={s.id} className="flex items-center gap-1.5 flex-shrink-0">
                <div
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-[11.5px] font-medium`}
                  style={{ background: bg, color: fg, border: current ? `1px solid ${fg}` : undefined }}
                >
                  {done ? (
                    <CheckCircle2 className="h-3 w-3" />
                  ) : (
                    <span className="h-1.5 w-1.5 rounded-full" style={{ background: fg }} />
                  )}
                  {s.label}
                </div>
                {i < STAGES.length - 1 && (
                  <span className="h-px w-3" style={{ background: done ? "var(--con-ok)" : "var(--con-line)" }} />
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {/* Deployment checklist */}
      <Card title="Deployment checklist" eyebrow={`${checklistDone}% READY`} className="mb-6">
        <div className="mb-4">
          <ProgressBar value={checklistDone} tone={checklistDone >= 80 ? "ok" : checklistDone >= 50 ? "warn" : "err"} height={6} />
        </div>
        {upcoming.checklist.length === 0 ? (
          <p className="text-[12px] text-ink-3">Checklist not configured for this release yet.</p>
        ) : (
          <div className="space-y-1">
            {upcoming.checklist.map((c) => (
              <div key={c.id} className="flex items-center gap-3 py-2 border-b border-hx last:border-b-0">
                {c.done ? (
                  <CheckCircle2 className="h-4 w-4 flex-shrink-0" style={{ color: "var(--con-ok)" }} />
                ) : (
                  <Circle className="h-4 w-4 flex-shrink-0" style={{ color: "var(--con-ink-4)" }} />
                )}
                <span className={`text-[12.5px] ${c.done ? "text-ink-3 line-through" : "text-ink"}`}>{c.label}</span>
                <span className="ml-auto font-mono text-[11px] text-ink-4">{c.owner}</span>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* All releases table */}
      <Card title="All releases" eyebrow="HISTORY" bodyClassName="p-0">
        <div className="w-full overflow-x-auto">
          <table className="w-full border-collapse text-[12.5px]">
            <thead className="bg-surface-hi">
              <tr>
                <TH>ID</TH>
                <TH>Name</TH>
                <TH>Stage</TH>
                <TH>Env</TH>
                <TH>Scheduled</TH>
                <TH align="right">Validation</TH>
                <TH align="right">Recon</TH>
                <TH align="center">Rollback</TH>
              </tr>
            </thead>
            <tbody>
              {releases.map((r) => (
                <tr key={r.id} className="border-b border-hx last:border-b-0 hover:bg-surface-hi">
                  <TD mono>
                    <span className="text-ink-4">{r.id}</span>
                  </TD>
                  <TD>
                    <span className="font-medium text-ink">{r.name}</span>
                  </TD>
                  <TD>
                    <StatusBadge status={r.stage} />
                  </TD>
                  <TD>
                    <Chip tone={r.targetEnvironment === "prod" ? "err" : r.targetEnvironment === "staging" ? "warn" : "info"} mono>
                      {r.targetEnvironment}
                    </Chip>
                  </TD>
                  <TD mono>
                    {new Date(r.scheduledFor).toLocaleDateString()}
                  </TD>
                  <TD align="right" mono>
                    <span style={{ color: scoreColor(r.validationScore, "validation") }}>
                      {r.validationScore}%
                    </span>
                  </TD>
                  <TD align="right" mono>
                    <span style={{ color: scoreColor(r.reconScore, "recon") }}>
                      {r.reconScore}%
                    </span>
                  </TD>
                  <TD align="center" mono>
                    {r.rollbackReady ? (
                      <span style={{ color: "var(--con-ok)" }}>✓</span>
                    ) : (
                      <span style={{ color: "var(--con-err)" }}>✗</span>
                    )}
                  </TD>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </AppShell>
  );
}

function ScoreBox({ label, value, kind }: { label: string; value: number; kind: "validation" | "recon" }) {
  const color = scoreColor(value, kind);
  const threshold = kind === "validation" ? 95 : 99;
  return (
    <div className="text-center">
      <div className="eyebrow text-[10px] mb-1">{label}</div>
      <div
        className="font-mono tabular-nums text-[40px] font-medium leading-none tracking-editorial"
        style={{ color }}
      >
        {value}%
      </div>
      <div className="text-[10.5px] text-ink-4 font-mono mt-1">Target ≥ {threshold}%</div>
    </div>
  );
}

function TH({ children, align = "left" }: { children: React.ReactNode; align?: "left" | "right" | "center" }) {
  return (
    <th
      className={`px-3.5 py-2.5 font-medium text-ink-4 text-[10.5px] uppercase tracking-[0.08em] font-mono border-b border-hx ${
        align === "right" ? "text-right" : align === "center" ? "text-center" : "text-left"
      }`}
    >
      {children}
    </th>
  );
}

function TD({
  children,
  align = "left",
  mono = false,
}: {
  children: React.ReactNode;
  align?: "left" | "right" | "center";
  mono?: boolean;
}) {
  return (
    <td
      className={`px-3.5 py-3 align-middle ${
        align === "right" ? "text-right" : align === "center" ? "text-center" : "text-left"
      } ${mono ? "font-mono" : ""}`}
    >
      {children}
    </td>
  );
}
