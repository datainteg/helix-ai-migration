"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { ProjectShell } from "@/components/layout/ProjectShell";
import { Card, LoadingState, ErrorBanner, Button } from "@/components/ui";
import { useProjectKey } from "@/lib/projects/useProjectKey";
import { useAuth } from "@/lib/auth-context";
import { useRegisterCrumbLabel } from "@/lib/breadcrumbs";
import * as api from "@/lib/lifecycle/api";
import type { MigrationArtifact, MigrationArtifactVersion } from "@/lib/lifecycle/api";
import { ArtifactViewer } from "@/components/artifacts/ArtifactViewer";
import { ArtifactEditor, DownloadButton } from "@/components/artifacts/ArtifactEditor";
import { ArtifactVersionList } from "@/components/artifacts/ArtifactVersionList";
import { ArtifactReviewPanel } from "@/components/artifacts/ArtifactReviewPanel";
import { ArtifactCommentThread } from "@/components/artifacts/ArtifactCommentThread";

export default function ArtifactReviewPage() {
  const params = useParams<{ id: string; artifactId: string }>();
  const projectParam = String(params.id);
  const artifactId = String(params.artifactId);
  const { key, name } = useProjectKey(projectParam);
  const { can } = useAuth();
  useRegisterCrumbLabel(projectParam, name);

  const canWrite = can("project:write");
  const canApprove = can("agent:approve");

  const [artifact, setArtifact] = useState<MigrationArtifact | null>(null);
  const [versions, setVersions] = useState<MigrationArtifactVersion[]>([]);
  const [selected, setSelected] = useState<MigrationArtifactVersion | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setErr(null);
    try {
      const [art, vers] = await Promise.all([api.getMigrationArtifact(artifactId), api.getArtifactVersions(artifactId)]);
      setArtifact(art); setVersions(vers);
      setSelected((prev) => vers.find((v) => v.id === prev?.id) || vers.find((v) => v.id === art.current_version_id) || vers[0] || null);
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  }, [artifactId]);
  useEffect(() => { load(); }, [load]);

  function startEdit() { setDraft(selected?.content_markdown || ""); setEditing(true); }
  async function saveNewVersion() {
    setBusy(true); setErr(null);
    try {
      await api.createArtifactVersion(artifactId, draft, "User edit", selected?.id);
      setEditing(false);
      await load();
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  return (
    <ProjectShell projectId={key} projectName={name || "Project"}>
      <div className="flex items-center justify-between">
        <Link href={`/projects/${key}/lifecycle`} className="inline-flex items-center gap-1.5 text-[12.5px] text-ink-3 hover:text-ink-1">
          <ArrowLeft className="h-3.5 w-3.5" /> Back to lifecycle
        </Link>
        {versions.length >= 2 && (
          <Link href={`/projects/${key}/artifacts/${artifactId}/compare?from=${versions[1].version_number}&to=${versions[0].version_number}`}
            className="text-[12.5px] text-helix-700 hover:underline">Compare versions →</Link>
        )}
      </div>
      {err && <ErrorBanner message={err} onDismiss={() => setErr(null)} />}

      {loading ? (
        <LoadingState label="Loading artifact…" />
      ) : !artifact ? (
        <ErrorBanner message="Artifact not found." />
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[200px_1fr_300px]">
          {/* Left: versions */}
          <Card title="Versions" padding="sm">
            <ArtifactVersionList versions={versions} currentVersionId={artifact.current_version_id}
              selectedVersionId={selected?.id || null} onSelect={(v) => { setSelected(v); setEditing(false); }} />
          </Card>

          {/* Center: viewer / editor */}
          <Card
            title={artifact.title}
            eyebrow={`v${selected?.version_number ?? "—"} · ${artifact.artifact_type}`}
            actions={
              <div className="flex items-center gap-2">
                <DownloadButton filename={artifact.artifact_type} content={selected?.content_markdown || ""} />
                {canWrite && !editing && <Button size="sm" variant="outline" onClick={startEdit}>Edit Artifact</Button>}
                {editing && <>
                  <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
                  <Button size="sm" disabled={busy} onClick={saveNewVersion}>{busy ? "Saving…" : "Save as New Version"}</Button>
                </>}
              </div>
            }
          >
            {editing ? <ArtifactEditor value={draft} onChange={setDraft} /> : <ArtifactViewer markdown={selected?.content_markdown} />}
          </Card>

          {/* Right: review + comments */}
          <div className="space-y-6">
            <Card title="Review">
              <ArtifactReviewPanel artifact={artifact} versionId={selected?.id || null} canWrite={canWrite} canApprove={canApprove} onChanged={load} />
            </Card>
            <Card title="Comments">
              <ArtifactCommentThread artifactId={artifactId} versionId={selected?.id} canComment={canWrite || canApprove} />
            </Card>
          </div>
        </div>
      )}
    </ProjectShell>
  );
}
