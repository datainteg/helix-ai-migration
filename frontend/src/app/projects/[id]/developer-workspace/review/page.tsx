"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ProjectShell } from "@/components/layout/ProjectShell";
import { Card, Button, Chip, EmptyState, LoadingState, ErrorBanner } from "@/components/ui";
import type { ChipTone } from "@/components/ui";
import { useProjectKey } from "@/lib/projects/useProjectKey";
import { useAuth } from "@/lib/auth-context";
import { useRegisterCrumbLabel } from "@/lib/breadcrumbs";
import * as api from "@/lib/workspaces/api";
import type { GeneratedCode } from "@/lib/workspaces/api";
import { CodeBlock } from "../CodeBlock";

const CODE_TONE: Record<string, ChipTone> = { draft: "zinc", reviewed: "info", approved: "ok", rejected: "err" };

export default function CodeReviewQueuePage() {
  const projectParam = String(useParams<{ id: string }>().id);
  const { id, key, name } = useProjectKey(projectParam);
  const { can } = useAuth();
  useRegisterCrumbLabel(projectParam, name);
  const canWrite = can("project:write");
  const canApprove = can("agent:approve");

  const [files, setFiles] = useState<GeneratedCode[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    try { setFiles(await api.listGeneratedCode(id)); }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  }, [id]);
  useEffect(() => { load(); }, [load]);

  async function act(label: string, fn: () => Promise<unknown>) {
    setBusy(label); setErr(null);
    try { await fn(); await load(); }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(null); }
  }

  const pending = files.filter((f) => f.status === "draft" || f.status === "reviewed");
  const decided = files.filter((f) => f.status === "approved" || f.status === "rejected");

  const row = (f: GeneratedCode) => (
    <div key={f.id} className="rounded-md border border-hx bg-app-2/40">
      <div className="flex items-center justify-between gap-2 px-3 py-2">
        <button onClick={() => setOpen(open === f.id ? null : f.id)} className="flex items-center gap-2 text-left">
          <Chip tone={CODE_TONE[f.status] || "default"} dot>{f.status}</Chip>
          <span className="font-mono text-[12.5px] text-ink-1">{f.file_name}</span>
          <span className="text-[11px] text-ink-3">{f.file_type} · {f.generated_by_agent || "—"}</span>
        </button>
        <div className="flex gap-1.5">
          {canWrite && f.status === "draft" && <Button size="sm" variant="outline" disabled={!!busy} onClick={() => act(f.id, () => api.reviewGeneratedCode(f.id, "reviewed"))}>Reviewed</Button>}
          {canApprove && (f.status === "draft" || f.status === "reviewed") && <Button size="sm" disabled={!!busy} onClick={() => act(f.id, () => api.approveGeneratedCode(f.id))}>Approve</Button>}
          {canWrite && (f.status === "draft" || f.status === "reviewed") && <Button size="sm" variant="danger" disabled={!!busy} onClick={() => act(f.id, () => api.reviewGeneratedCode(f.id, "rejected"))}>Reject</Button>}
        </div>
      </div>
      {open === f.id && <div className="border-t border-hx p-3"><CodeBlock code={f.content || ""} language={f.language || undefined} filename={f.file_name} maxHeight={360} /></div>}
    </div>
  );

  return (
    <ProjectShell projectId={key} projectName={name || "Project"}>
      <div className="flex items-center justify-between">
        <Link href={`/projects/${key}/developer-workspace/code`} className="text-[12.5px] text-ink-3 hover:text-ink-1">← Generated code</Link>
      </div>
      {err && <ErrorBanner message={err} onDismiss={() => setErr(null)} />}

      {loading ? <LoadingState label="Loading review queue…" /> : files.length === 0 ? (
        <Card><EmptyState title="Nothing to review" description="No generated code yet. Generate code first." /></Card>
      ) : (
        <>
          <Card title={`Pending review (${pending.length})`}>
            {pending.length === 0 ? <p className="text-[12.5px] text-ink-3">All caught up.</p> : <div className="space-y-2">{pending.map(row)}</div>}
          </Card>
          <Card title={`Decided (${decided.length})`}>
            {decided.length === 0 ? <p className="text-[12.5px] text-ink-3">None yet.</p> : <div className="space-y-2">{decided.map(row)}</div>}
          </Card>
        </>
      )}
    </ProjectShell>
  );
}
