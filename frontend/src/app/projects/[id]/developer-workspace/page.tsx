"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Upload, FileCode, History } from "lucide-react";
import { ProjectShell } from "@/components/layout/ProjectShell";
import { Card, Button, Chip, EmptyState, LoadingState } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import { listProjectArtifacts, listArtifactVersions, type Artifact } from "@/lib/artifacts/api";

export default function ProjectDevWorkspacePage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();
  const [artifacts, setArtifacts] = useState<Artifact[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [versions, setVersions] = useState<Artifact[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token || !id) return;
    let cancelled = false;
    setLoading(true);
    listProjectArtifacts(token, String(id), 100)
      .then((rows) => {
        if (cancelled) return;
        setArtifacts(rows);
        if (rows.length > 0) setSelectedId(rows[0].id);
      })
      .catch(() => { if (!cancelled) setArtifacts([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [token, id]);

  useEffect(() => {
    if (!token || !selectedId) { setVersions([]); return; }
    let cancelled = false;
    listArtifactVersions(token, selectedId)
      .then((rows) => { if (!cancelled) setVersions(rows); })
      .catch(() => { if (!cancelled) setVersions([]); });
    return () => { cancelled = true; };
  }, [token, selectedId]);

  const hasReal = (artifacts?.length ?? 0) > 0;
  const fileList = hasReal ? artifacts!.map((a) => ({ id: a.id, label: a.filename })) : [];
  const selected = hasReal ? artifacts!.find((a) => a.id === selectedId) ?? null : null;

  return (
    <ProjectShell projectId={String(id)} projectName="Untitled project" projectStatus="draft" subtitle="Three-pane IDE: artifact explorer · code/diff · AI review">
      {loading ? <LoadingState label="Loading artifacts…" /> : null}
      <div className="grid grid-cols-12 gap-4">
        <Card className="col-span-12 lg:col-span-3" title="Artifacts" padding="sm">
          {fileList.length > 0 ? (
            <ul className="space-y-1 text-[12.5px]">
              {fileList.map((f) => (
                <li
                  key={f.id}
                  onClick={() => setSelectedId(f.id)}
                  className={`px-2 py-1.5 rounded-md flex items-center gap-2 cursor-pointer ${f.id === selectedId ? "bg-helix-50 text-helix-700" : "text-ink-3 hover:bg-app-2"}`}
                >
                  <FileCode className="h-3.5 w-3.5" />{f.label}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[12px] text-ink-3 py-2">No artifacts yet. Upload one to get started.</p>
          )}
          <Button variant="outline" size="sm" className="w-full mt-3 justify-center"><Upload className="h-3.5 w-3.5" /> Upload</Button>
          <hr className="border-hx my-3" />
          <p className="text-[11.5px] text-ink-3 uppercase tracking-wider font-medium mb-2 flex items-center gap-1"><History className="h-3 w-3" /> Versions</p>
          {versions.length > 0 ? (
            <ul className="space-y-1.5 text-[12px] text-ink-2">
              {versions.map((v, i) => (
                <li key={v.id} className="flex items-center justify-between">
                  <span className="font-mono">v{v.version ?? versions.length - i}</span>
                  {i === 0 ? <Chip tone="indigo">latest</Chip> : <span className="text-ink-4 text-[11px]">{v.created_at?.slice(0, 10) ?? ""}</span>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[12px] text-ink-3">No versions yet.</p>
          )}
        </Card>

        <div className="col-span-12 lg:col-span-6 space-y-4">
          <Card>
            {selected ? (
              <>
                <div className="flex items-center gap-2 text-[12.5px] border-b border-hx -mx-5 px-5 pb-3 mb-4">
                  <FileCode className="h-3.5 w-3.5 text-ink-3" />
                  <span className="font-medium text-ink">{selected.filename}</span>
                  {selected.file_type ? <Chip tone="zinc">{selected.file_type}</Chip> : null}
                  {selected.status ? <Chip tone="indigo">{selected.status}</Chip> : null}
                </div>
                <div className="rounded-lg border border-hx bg-app-2 p-4 min-h-[300px] grid place-items-center">
                  <EmptyState title="Preview not available" description="File content preview isn’t available for this artifact yet. Download or open it from the registry to inspect the code." />
                </div>
              </>
            ) : (
              <div className="min-h-[300px] grid place-items-center">
                <EmptyState
                  icon={<FileCode className="h-4 w-4" />}
                  title="Select an artifact to view"
                  description="Choose a file from the artifact explorer to inspect it here."
                />
              </div>
            )}
          </Card>
        </div>

        <Card className="col-span-12 lg:col-span-3" title="AI Review" padding="sm">
          <EmptyState title="Awaiting analysis" description="Upload code to surface assumptions, risks, and security findings." />
        </Card>
      </div>
    </ProjectShell>
  );
}
