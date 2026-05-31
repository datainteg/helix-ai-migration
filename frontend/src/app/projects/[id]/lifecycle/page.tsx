"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ProjectShell } from "@/components/layout/ProjectShell";
import { Card, ProgressBar, LoadingState, ErrorBanner, EmptyState, Button } from "@/components/ui";
import { useProjectKey } from "@/lib/projects/useProjectKey";
import { useAuth } from "@/lib/auth-context";
import { useRegisterCrumbLabel } from "@/lib/breadcrumbs";
import * as api from "@/lib/lifecycle/api";
import type { MigrationStage } from "@/lib/lifecycle/api";
import { LifecycleTimeline } from "@/components/lifecycle/LifecycleTimeline";
import { StageStatusBadge } from "@/components/lifecycle/StageStatusBadge";
import { nextActionHint, isAgentRunnable, STAGE_OBJECTIVE } from "@/components/lifecycle/labels";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function ProjectLifecyclePage() {
  const projectParam = String(useParams<{ id: string }>().id);
  const { id, key, name } = useProjectKey(projectParam);
  const { can } = useAuth();
  useRegisterCrumbLabel(projectParam, name);

  const [proj, setProj] = useState<any>(null);
  const [stages, setStages] = useState<MigrationStage[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    if (!id) return;
    fetch(`${API_BASE}/api/v1/projects/${id}`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null)).then(setProj).catch(() => {});
    api.getLifecycle(id).then(setStages).catch((e) => { setErr(String(e.message || e)); setStages([]); });
  }, [id]);
  useEffect(load, [load]);

  const current = stages?.find((s) => !["approved", "completed", "skipped"].includes(s.status) && !(s.is_optional && s.status === "not_started"));
  const progress = proj?.stage_progress_percent ?? (stages && stages.length
    ? Math.round((100 * stages.filter((s) => ["approved", "completed", "skipped"].includes(s.status)).length) / stages.length)
    : 0);

  async function initialize() {
    if (!id) return;
    setBusy(true); setErr(null);
    try { setStages(await api.initializeLifecycle(id)); }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  return (
    <ProjectShell projectId={key} projectName={name || "Project"} projectStatus={proj?.status}>
      {err && <ErrorBanner message={err} onDismiss={() => setErr(null)} />}

      {/* Summary header */}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-[13px] text-helix-700">{proj?.alias || "—"}</span>
              <span className="text-[13px] text-ink-3">·</span>
              <span className="text-[14px] font-medium text-ink-1">{name}</span>
            </div>
            <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[13px] text-ink-3">
              <span>Current stage:</span>
              {current ? <><span className="text-ink-1">{current.stage_name}</span><StageStatusBadge status={current.status} /></>
                : <span className="text-ink-1">{proj?.lifecycle_status === "completed" ? "All stages complete 🎉" : "—"}</span>}
            </div>
            {current && <p className="mt-1 text-[12px] text-ink-3">Next action: {nextActionHint(current.status, isAgentRunnable(current.assigned_agent))}</p>}
          </div>
          <div className="min-w-[200px]">
            <div className="flex items-center justify-between text-[12px] text-ink-3"><span>Progress</span><span className="tabular-nums">{progress}%</span></div>
            <div className="mt-1"><ProgressBar value={progress} tone="brand" height={6} /></div>
          </div>
        </div>
      </Card>

      {/* Timeline */}
      <Card title="Execution lifecycle" description="Stage-gated migration — each stage runs an agent, produces an artifact, and waits for approval before the next stage starts.">
        {stages === null ? (
          <LoadingState label="Loading lifecycle…" />
        ) : stages.length === 0 ? (
          <EmptyState
            title="Lifecycle not initialized"
            description="This project has no lifecycle stages yet."
            action={can("project:write") ? <Button onClick={initialize} disabled={busy}>{busy ? "Initializing…" : "Initialize lifecycle"}</Button> : undefined}
          />
        ) : (
          <LifecycleTimeline stages={stages} projectKey={key} currentStageKey={current?.stage_key} />
        )}
      </Card>
    </ProjectShell>
  );
}
