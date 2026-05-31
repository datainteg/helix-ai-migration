"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Sparkles, Play, Square, RefreshCw, Download } from "lucide-react";
import { ProjectShell } from "@/components/layout/ProjectShell";
import { Card, Button, Chip, EmptyState, LoadingState, ErrorBanner, StatusBadge } from "@/components/ui";
import type { ChipTone } from "@/components/ui";
import { useProjectKey } from "@/lib/projects/useProjectKey";
import { useAuth } from "@/lib/auth-context";
import { useRegisterCrumbLabel } from "@/lib/breadcrumbs";
import * as api from "@/lib/workspaces/api";
import type { Workspace, GeneratedCode } from "@/lib/workspaces/api";
import { CodeBlock } from "../CodeBlock";

const CODE_TONE: Record<string, ChipTone> = { draft: "zinc", reviewed: "info", approved: "ok", rejected: "err" };

function download(name: string, content: string) {
  const blob = new Blob([content], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}

export default function GeneratedCodePage() {
  const projectParam = String(useParams<{ id: string }>().id);
  const { id, key, name } = useProjectKey(projectParam);
  const { can } = useAuth();
  useRegisterCrumbLabel(projectParam, name);
  const canWrite = can("project:write");
  const canApprove = can("agent:approve");

  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [files, setFiles] = useState<GeneratedCode[]>([]);
  const [sel, setSel] = useState<GeneratedCode | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const [ws, fs] = await Promise.all([api.listWorkspaces(id), api.listGeneratedCode(id)]);
      setWorkspaces(ws); setFiles(fs);
      setSel((p) => fs.find((f) => f.id === p?.id) || fs[0] || null);
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  }, [id]);
  useEffect(() => { load(); }, [load]);

  async function act(label: string, fn: () => Promise<unknown>) {
    setBusy(label); setErr(null);
    try { await fn(); await load(); }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(null); }
  }

  return (
    <ProjectShell projectId={key} projectName={name || "Project"}>
      <div className="flex items-center justify-between">
        <Link href={`/projects/${key}/developer-workspace`} className="text-[12.5px] text-ink-3 hover:text-ink-1">← Workspace</Link>
        <Link href={`/projects/${key}/developer-workspace/review`} className="text-[12.5px] text-helix-700 hover:underline">Review queue →</Link>
      </div>
      {err && <ErrorBanner message={err} onDismiss={() => setErr(null)} />}

      {/* Workspaces bar */}
      <Card title="Workspaces" description="Generated code is draft until reviewed & approved — it is never executed by Helix."
        actions={canWrite && (
          <div className="flex gap-2">
            <Button size="sm" variant="outline" disabled={!!busy} onClick={() => act("create", () => api.createWorkspace(id, "artifact_only"))}>New workspace</Button>
            <Button size="sm" disabled={!!busy} onClick={() => act("gen", () => api.generateCode(id))}>
              <Sparkles className="h-4 w-4" /> {busy === "gen" ? "Generating…" : "Generate Code"}
            </Button>
          </div>
        )}>
        {workspaces.length === 0 ? (
          <p className="text-[12.5px] text-ink-3">No workspaces yet. Create one, then generate code with Amelia.</p>
        ) : (
          <ul className="space-y-1.5">
            {workspaces.map((w) => (
              <li key={w.id} className="flex items-center justify-between rounded-md border border-hx bg-app-2/40 px-3 py-2">
                <div className="flex items-center gap-2 text-[13px]">
                  <span className="font-mono text-ink-1">{w.workspace_alias}</span>
                  <Chip tone="zinc" mono>{w.workspace_type}</Chip>
                  <StatusBadge status={w.status} />
                  {w.workspace_url && <a href={w.workspace_url} target="_blank" rel="noreferrer" className="text-[12px] text-helix-700 hover:underline">open IDE</a>}
                </div>
                {canWrite && (
                  <div className="flex gap-1.5">
                    {w.status !== "running" ? (
                      <Button size="sm" variant="ghost" disabled={!!busy} onClick={() => act("start", () => api.startWorkspace(w.id))}><Play className="h-3.5 w-3.5" /></Button>
                    ) : (
                      <Button size="sm" variant="ghost" disabled={!!busy} onClick={() => act("stop", () => api.stopWorkspace(w.id))}><Square className="h-3.5 w-3.5" /></Button>
                    )}
                    <Button size="sm" variant="ghost" disabled={!!busy} onClick={() => act("sync", () => api.syncWorkspace(w.id))}><RefreshCw className="h-3.5 w-3.5" /></Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* Generated code */}
      {loading ? <LoadingState label="Loading generated code…" /> : files.length === 0 ? (
        <Card><EmptyState title="No generated code yet" description="Use “Generate Code” to have Amelia draft migration code from your approved architecture & plan." /></Card>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[260px_1fr_240px]">
          <Card title="Files" padding="sm">
            <ul className="space-y-1">
              {files.map((f) => (
                <li key={f.id}>
                  <button onClick={() => setSel(f)} className={`w-full rounded-md border px-2.5 py-2 text-left ${sel?.id === f.id ? "border-helix-400 bg-app-2" : "border-hx hover:bg-app-2"}`}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate font-mono text-[12.5px] text-ink-1">{f.file_name}</span>
                      <Chip tone={CODE_TONE[f.status] || "default"} dot>{f.status}</Chip>
                    </div>
                    <span className="text-[11px] text-ink-3">{f.file_type || "code"} · {f.generated_by_agent || "—"}</span>
                  </button>
                </li>
              ))}
            </ul>
          </Card>

          <Card title={sel?.file_name || "—"} eyebrow={sel ? `${sel.file_type} · ${sel.language || ""}` : undefined}
            actions={sel && <Button size="sm" variant="ghost" onClick={() => download(sel.file_name, sel.content || "")}><Download className="h-3.5 w-3.5" /> Download</Button>}>
            {sel ? <CodeBlock code={sel.content || ""} language={sel.language || undefined} filename={sel.file_name} /> : <p className="text-[13px] text-ink-3">Select a file.</p>}
          </Card>

          <div className="space-y-6">
            <Card title="Review">
              {sel ? (
                <div className="space-y-3 text-[12.5px]">
                  <div className="flex items-center justify-between"><span className="text-ink-3">Status</span><Chip tone={CODE_TONE[sel.status] || "default"} dot>{sel.status}</Chip></div>
                  <div className="flex items-center justify-between"><span className="text-ink-3">Reviewer</span><span className="font-mono text-ink-1">{sel.reviewed_by_user_id ? sel.reviewed_by_user_id.slice(0, 8) : "—"}</span></div>
                  <div className="flex flex-col gap-2 pt-1">
                    {canWrite && sel.status === "draft" && (
                      <Button size="sm" variant="outline" disabled={!!busy} onClick={() => act("review", () => api.reviewGeneratedCode(sel.id, "reviewed"))}>Mark Reviewed</Button>
                    )}
                    {canApprove && (sel.status === "draft" || sel.status === "reviewed") && (
                      <Button size="sm" disabled={!!busy} onClick={() => act("approve", () => api.approveGeneratedCode(sel.id))}>Approve</Button>
                    )}
                    {canWrite && sel.status !== "rejected" && sel.status !== "approved" && (
                      <Button size="sm" variant="danger" disabled={!!busy} onClick={() => act("reject", () => api.reviewGeneratedCode(sel.id, "rejected"))}>Reject</Button>
                    )}
                  </div>
                </div>
              ) : <p className="text-[12.5px] text-ink-3">Select a file to review.</p>}
            </Card>
          </div>
        </div>
      )}
    </ProjectShell>
  );
}
