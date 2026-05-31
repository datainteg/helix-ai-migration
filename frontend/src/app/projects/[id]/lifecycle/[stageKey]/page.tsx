"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { ProjectShell } from "@/components/layout/ProjectShell";
import { Card, LoadingState, ErrorBanner, EmptyState } from "@/components/ui";
import { useProjectKey } from "@/lib/projects/useProjectKey";
import { useAuth } from "@/lib/auth-context";
import { useRegisterCrumbLabel } from "@/lib/breadcrumbs";
import * as api from "@/lib/lifecycle/api";
import type { MigrationStage, MigrationArtifact, MigrationArtifactVersion } from "@/lib/lifecycle/api";
import { StageStatusBadge } from "@/components/lifecycle/StageStatusBadge";
import { StageActionPanel } from "@/components/lifecycle/StageActionPanel";
import { StageContextSummary } from "@/components/lifecycle/StageContextSummary";
import { StageApprovalPanel } from "@/components/lifecycle/StageApprovalPanel";
import { agentLabel } from "@/components/lifecycle/labels";
import { ArtifactViewer } from "@/components/artifacts/ArtifactViewer";
import { ArtifactVersionList } from "@/components/artifacts/ArtifactVersionList";
import { ArtifactCommentThread } from "@/components/artifacts/ArtifactCommentThread";

export default function StageDetailPage() {
  const params = useParams<{ id: string; stageKey: string }>();
  const projectParam = String(params.id);
  const stageKey = String(params.stageKey);
  const { id, key, name } = useProjectKey(projectParam);
  const { can } = useAuth();
  useRegisterCrumbLabel(projectParam, name);

  const canWrite = can("project:write");
  const canApprove = can("agent:approve");

  const [stage, setStage] = useState<MigrationStage | null>(null);
  const [artifact, setArtifact] = useState<MigrationArtifact | null>(null);
  const [versions, setVersions] = useState<MigrationArtifactVersion[]>([]);
  const [approved, setApproved] = useState<MigrationArtifact[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setErr(null);
    try {
      const [stages, all] = await Promise.all([api.getLifecycle(id), api.listMigrationArtifacts(id)]);
      const st = stages.find((s) => s.stage_key === stageKey) || null;
      setStage(st);
      setApproved(all.filter((a) => a.status === "approved"));
      if (st?.current_artifact_id) {
        const [art, vers] = await Promise.all([
          api.getMigrationArtifact(st.current_artifact_id),
          api.getArtifactVersions(st.current_artifact_id),
        ]);
        setArtifact(art); setVersions(vers);
      } else { setArtifact(null); setVersions([]); }
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  }, [id, stageKey]);
  useEffect(() => { load(); }, [load]);

  const currentVersion = versions.find((v) => v.id === artifact?.current_version_id) || versions[0];

  return (
    <ProjectShell projectId={key} projectName={name || "Project"}>
      <Link href={`/projects/${key}/lifecycle`} className="inline-flex items-center gap-1.5 text-[12.5px] text-ink-3 hover:text-ink-1">
        <ArrowLeft className="h-3.5 w-3.5" /> Back to lifecycle
      </Link>
      {err && <ErrorBanner message={err} onDismiss={() => setErr(null)} />}

      {loading ? (
        <LoadingState label="Loading stage…" />
      ) : !stage ? (
        <EmptyState title="Stage not found" description={`No stage "${stageKey}" on this project.`} />
      ) : (
        <>
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] tabular-nums text-ink-3">#{stage.stage_order}</span>
                  <h2 className="text-[16px] font-semibold text-ink-1">{stage.stage_name}</h2>
                  {stage.is_optional && <span className="text-[10px] uppercase tracking-wide text-ink-3">optional</span>}
                </div>
                <p className="mt-1 text-[12.5px] text-ink-3">{agentLabel(stage.assigned_agent)}</p>
              </div>
              <StageStatusBadge status={stage.status} />
            </div>
            <div className="mt-4">
              <StageActionPanel projectId={id} projectKey={key} stage={stage} canWrite={canWrite} canApprove={canApprove} onChanged={load} />
            </div>
          </Card>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
            <div className="space-y-6">
              <Card title="Generated artifact" description={artifact ? artifact.title : undefined}
                actions={artifact ? <Link href={`/projects/${key}/artifacts/${artifact.id}/review`} className="text-[12.5px] text-helix-700 hover:underline">Open in review →</Link> : undefined}>
                {artifact ? <ArtifactViewer markdown={currentVersion?.content_markdown} />
                  : <EmptyState title="No artifact yet" description="Run the agent to generate this stage's artifact." />}
              </Card>
              {artifact && (
                <Card title="Comments">
                  <ArtifactCommentThread artifactId={artifact.id} versionId={currentVersion?.id} canComment={canWrite || canApprove} />
                </Card>
              )}
            </div>

            <div className="space-y-6">
              <Card title="Input context"><StageContextSummary stage={stage} approvedArtifacts={approved} /></Card>
              <Card title="Status & approval"><StageApprovalPanel stage={stage} /></Card>
              {versions.length > 0 && (
                <Card title="Version history">
                  <ArtifactVersionList versions={versions} currentVersionId={artifact?.current_version_id || null}
                    selectedVersionId={currentVersion?.id || null} onSelect={() => { if (artifact) window.location.href = `/projects/${key}/artifacts/${artifact.id}/review`; }} />
                </Card>
              )}
            </div>
          </div>
        </>
      )}
    </ProjectShell>
  );
}
