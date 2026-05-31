"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, Chip, LoadingState } from "@/components/ui";
import * as lc from "@/lib/lifecycle/api";
import type { MigrationStage, StageTransition, MigrationArtifact } from "@/lib/lifecycle/api";
import { listSignoffs, type Signoff } from "@/lib/signoff/api";
import { ProjectAliasBadge, LifecycleProgressBar, StageMiniStatus, NextBestActionCard, MigrationTimeline } from "./console";
import { StageStatusBadge } from "./StageStatusBadge";

const DONE = ["approved", "completed", "skipped"];

function statusOf(stages: MigrationStage[], key: string): string {
  return stages.find((s) => s.stage_key === key)?.status || "not_started";
}

/**
 * Self-contained migration-lifecycle console for the project overview.
 * Fetches its own data so it can be dropped into the existing page with one line.
 */
export function LifecycleConsole({ projectId, projectKey, alias, lifecycleStatus }: {
  projectId: string; projectKey: string; alias?: string | null; lifecycleStatus?: string | null;
}) {
  const [stages, setStages] = useState<MigrationStage[] | null>(null);
  const [transitions, setTransitions] = useState<StageTransition[]>([]);
  const [artifacts, setArtifacts] = useState<MigrationArtifact[]>([]);
  const [signoffs, setSignoffs] = useState<Signoff[]>([]);

  useEffect(() => {
    if (!projectId) return;
    lc.getLifecycle(projectId).then(setStages).catch(() => setStages([]));
    lc.getStageTransitions(projectId).then(setTransitions).catch(() => {});
    lc.listMigrationArtifacts(projectId).then(setArtifacts).catch(() => {});
    listSignoffs(projectId).then(setSignoffs).catch(() => {});
  }, [projectId]);

  if (stages === null) return <Card title="Migration lifecycle"><LoadingState label="Loading lifecycle…" /></Card>;
  if (stages.length === 0) {
    return (
      <Card title="Migration lifecycle">
        <p className="text-[13px] text-ink-3">Stage-gated lifecycle not initialized for this project. Open the
          <Link href={`/projects/${projectKey}/lifecycle`} className="text-helix-700 hover:underline"> Lifecycle</Link> tab to begin.</p>
      </Card>
    );
  }

  const current = stages.find((s) => !DONE.includes(s.status) && !(s.is_optional && s.status === "not_started"));
  const done = stages.filter((s) => DONE.includes(s.status)).length;
  const percent = Math.round((100 * done) / Math.max(1, stages.filter((s) => !(s.is_optional && s.status === "not_started")).length));
  const approvals = stages.filter((s) => ["generated", "under_review", "resubmitted"].includes(s.status)).length;
  const signoffStatus = signoffs[0]?.status || statusOf(stages, "SIGN_OFF");

  const stat = (label: string, value: React.ReactNode) => (
    <div className="rounded-md border border-hx bg-app-2/40 px-3 py-2">
      <div className="text-[11px] uppercase tracking-wide text-ink-3">{label}</div>
      <div className="mt-0.5 text-[13px] text-ink-1">{value}</div>
    </div>
  );

  return (
    <Card
      title="Migration lifecycle"
      actions={<Link href={`/projects/${projectKey}/lifecycle`} className="text-[12.5px] text-helix-700 hover:underline">Open lifecycle →</Link>}
    >
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <ProjectAliasBadge alias={alias} />
          <Chip tone={lifecycleStatus === "completed" ? "ok" : "info"}>{lifecycleStatus || "in_progress"}</Chip>
          {current && <span className="text-[12.5px] text-ink-3">Current: <span className="text-ink-1">{current.stage_name}</span></span>}
          {current && <StageStatusBadge status={current.status} />}
        </div>

        <NextBestActionCard stages={stages} projectKey={projectKey} />
        <LifecycleProgressBar percent={percent} />
        <StageMiniStatus stages={stages} currentStageKey={current?.stage_key} />

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {stat("Validation", <StageStatusBadge status={statusOf(stages, "VALIDATION") as any} />)}
          {stat("Reconciliation", <StageStatusBadge status={statusOf(stages, "RECONCILIATION") as any} />)}
          {stat("Sign-off", <Chip tone={signoffStatus === "approved" ? "ok" : signoffStatus === "rejected" ? "err" : signoffStatus === "sent" ? "info" : "zinc"} dot>{signoffStatus}</Chip>)}
          {stat("Artifacts", artifacts.length)}
          {stat("Pending approvals", approvals)}
          {stat("Stages done", `${done}/${stages.length}`)}
        </div>

        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <span className="text-[11px] uppercase tracking-wide text-ink-3">Recent activity</span>
            <Link href={`/projects/${projectKey}/audit`} className="text-[12px] text-helix-700 hover:underline">Full timeline →</Link>
          </div>
          <MigrationTimeline transitions={transitions} max={6} />
        </div>
      </div>
    </Card>
  );
}
