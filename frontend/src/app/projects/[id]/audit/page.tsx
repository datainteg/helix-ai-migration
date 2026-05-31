"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ProjectShell } from "@/components/layout/ProjectShell";
import { Card, LoadingState, ErrorBanner, EmptyState } from "@/components/ui";
import { useProjectKey } from "@/lib/projects/useProjectKey";
import { useRegisterCrumbLabel } from "@/lib/breadcrumbs";
import { getStageTransitions, type StageTransition } from "@/lib/lifecycle/api";
import { MigrationTimeline } from "@/components/lifecycle/console";

export default function ProjectAuditPage() {
  const projectParam = String(useParams<{ id: string }>().id);
  const { id, key, name } = useProjectKey(projectParam);
  useRegisterCrumbLabel(projectParam, name);
  const [rows, setRows] = useState<StageTransition[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getStageTransitions(id).then(setRows).catch((e) => { setErr(String(e.message || e)); setRows([]); });
  }, [id]);

  return (
    <ProjectShell projectId={key} projectName={name || "Project"} subtitle="Append-only lifecycle audit trail — every stage transition, who and when.">
      {err && <ErrorBanner message={err} onDismiss={() => setErr(null)} />}
      <Card title="Migration timeline">
        {rows === null ? <LoadingState label="Loading timeline…" />
          : rows.length === 0 ? <EmptyState title="No activity yet" description="Lifecycle transitions will appear here as the migration progresses." />
          : <MigrationTimeline transitions={rows} />}
      </Card>
    </ProjectShell>
  );
}
