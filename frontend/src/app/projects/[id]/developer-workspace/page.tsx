"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Upload, FileCode, History } from "lucide-react";
import { ProjectShell } from "@/components/layout/ProjectShell";
import { Card, Button, Chip, EmptyState, DemoBanner, LoadingState } from "@/components/ui";
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
  const fileList = hasReal
    ? artifacts!.map((a) => ({ id: a.id, label: a.filename }))
    : ["plan_v1.md", "ddl.sql", "migrate.py", "validate.sql", "notebook.ipynb"].map((f) => ({ id: f, label: f }));

  return (
    <ProjectShell projectId={String(id)} projectName="Untitled project" projectStatus="draft" subtitle="Three-pane IDE: artifact explorer · code/diff · AI review">
      {loading ? (
        <LoadingState label="Loading artifacts…" />
      ) : !hasReal ? (
        <div className="mb-4"><DemoBanner message="No artifacts yet for this project. Upload one or run a workflow — the explorer below is a sample preview." /></div>
      ) : null}
      <div className="grid grid-cols-12 gap-4">
        <Card className="col-span-12 lg:col-span-3" title="Artifacts" padding="sm">
          <ul className="space-y-1 text-[12.5px]">
            {fileList.map((f) => (
              <li
                key={f.id}
                onClick={() => hasReal && setSelectedId(f.id)}
                className={`px-2 py-1.5 rounded-md flex items-center gap-2 cursor-pointer ${f.id === selectedId ? "bg-helix-50 text-helix-700" : "text-ink-3 hover:bg-app-2"}`}
              >
                <FileCode className="h-3.5 w-3.5" />{f.label}
              </li>
            ))}
          </ul>
          <Button variant="outline" size="sm" className="w-full mt-3 justify-center"><Upload className="h-3.5 w-3.5" /> Upload</Button>
          <hr className="border-hx my-3" />
          <p className="text-[11.5px] text-ink-3 uppercase tracking-wider font-medium mb-2 flex items-center gap-1"><History className="h-3 w-3" /> Versions</p>
          {hasReal && versions.length > 0 ? (
            <ul className="space-y-1.5 text-[12px] text-ink-2">
              {versions.map((v, i) => (
                <li key={v.id} className="flex items-center justify-between">
                  <span className="font-mono">v{v.version ?? versions.length - i}</span>
                  {i === 0 ? <Chip tone="indigo">latest</Chip> : <span className="text-ink-4 text-[11px]">{v.created_at?.slice(0, 10) ?? ""}</span>}
                </li>
              ))}
            </ul>
          ) : (
            <ul className="space-y-1.5 text-[12px] text-ink-2">
              <li className="flex items-center justify-between"><span className="font-mono">v3 · current</span><Chip tone="indigo">latest</Chip></li>
              <li className="flex items-center justify-between"><span className="font-mono">v2</span><span className="text-ink-4 text-[11px]">2d ago</span></li>
              <li className="flex items-center justify-between"><span className="font-mono">v1</span><span className="text-ink-4 text-[11px]">5d ago</span></li>
            </ul>
          )}
        </Card>

        <div className="col-span-12 lg:col-span-6 space-y-4">
          <Card>
            <div className="flex gap-1 text-[12.5px] text-ink-3 border-b border-hx -mx-5 px-5 mb-4">
              {["Source", "Generated Draft", "Diff", "Notebook"].map((t, i) => (
                <button key={t} className={`px-3 py-2 border-b-2 -mb-px ${i === 0 ? "border-helix-500 text-helix-700 font-medium" : "border-transparent hover:text-ink"}`}>{t}</button>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-lg border border-hx bg-app-2 p-3 font-mono text-[11.5px] min-h-[300px]">
                <p className="text-ink-4 text-[10.5px] uppercase tracking-wider mb-2 font-sans">Original</p>
                <pre className="whitespace-pre-wrap text-ink-2">{`conn = pyodbc.connect(DSN)
df = pd.read_sql("SELECT * FROM …", conn)
df = df.drop_duplicates(subset=["id"])
`}</pre>
              </div>
              <div className="rounded-lg border border-amber-200 border-dashed bg-amber-50/30 p-3 font-mono text-[11.5px] min-h-[300px]">
                <p className="text-amber-700 text-[10.5px] uppercase tracking-wider mb-2 font-sans">Generated draft · not yet approved</p>
                <pre className="whitespace-pre-wrap text-ink-2">{`from helix.runtime import session
df = session.read_table("dim_customer")
df = df.dropDuplicates(["id"])
`}</pre>
              </div>
            </div>
          </Card>
        </div>

        <Card className="col-span-12 lg:col-span-3" title="AI Review" padding="sm">
          <EmptyState title="Awaiting analysis" description="Upload code to surface assumptions, risks, and security findings." />
        </Card>
      </div>
    </ProjectShell>
  );
}
