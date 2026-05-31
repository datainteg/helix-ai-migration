"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ProjectShell } from "@/components/layout/ProjectShell";
import { Card, Button, Chip, EmptyState, LoadingState, ErrorBanner, Table, THead, TBody, TR, TH, TD } from "@/components/ui";
import type { ChipTone } from "@/components/ui";
import { useProjectKey } from "@/lib/projects/useProjectKey";
import { useAuth } from "@/lib/auth-context";
import { useRegisterCrumbLabel } from "@/lib/breadcrumbs";
import * as api from "@/lib/validation-evidence/api";
import type { ValidationEvidence } from "@/lib/validation-evidence/api";

const TONE: Record<string, ChipTone> = { uploaded: "zinc", under_review: "info", accepted: "ok", rejected: "err", changes_required: "warn" };
const TYPES = ["summary", "test_result", "json", "log", "screenshot"];

export default function ValidationEvidencePage() {
  const projectParam = String(useParams<{ id: string }>().id);
  const { id, key, name } = useProjectKey(projectParam);
  const { can } = useAuth();
  useRegisterCrumbLabel(projectParam, name);
  const canWrite = can("project:write");
  const canApprove = can("agent:approve");

  const [rows, setRows] = useState<ValidationEvidence[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // upload form
  const [title, setTitle] = useState("");
  const [etype, setEtype] = useState("summary");
  const [desc, setDesc] = useState("");
  const [cjson, setCjson] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    try { setRows(await api.listEvidence(id)); }
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

  async function submit() {
    if (!title.trim()) { setErr("Title is required."); return; }
    await act("upload", async () => {
      await api.uploadEvidence(id, { title: title.trim(), evidence_type: etype, description: desc || undefined, content_json: cjson || undefined, file });
      setTitle(""); setDesc(""); setCjson(""); setFile(null);
    });
  }

  return (
    <ProjectShell projectId={key} projectName={name || "Project"}>
      <div className="flex items-center justify-between">
        <Link href={`/projects/${key}/validation`} className="text-[12.5px] text-ink-3 hover:text-ink-1">← Validation</Link>
        <Link href={`/projects/${key}/validation/review`} className="text-[12.5px] text-helix-700 hover:underline">QA review →</Link>
      </div>
      {err && <ErrorBanner message={err} onDismiss={() => setErr(null)} />}

      {canWrite && (
        <Card title="Upload validation evidence" description="Run tests in your own environment and upload the results — Helix stores test results/metadata only, never production rows.">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <label className="text-[12px] text-ink-2">Title
              <input value={title} onChange={(e) => setTitle(e.target.value)} className="mt-1 w-full rounded-md border border-hx bg-app px-3 py-2 text-[13px] text-ink-1 focus:border-helix-400 focus:outline-none" />
            </label>
            <label className="text-[12px] text-ink-2">Type
              <select value={etype} onChange={(e) => setEtype(e.target.value)} className="mt-1 w-full rounded-md border border-hx bg-app px-3 py-2 text-[13px] text-ink-1 focus:border-helix-400 focus:outline-none">
                {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </label>
            <label className="text-[12px] text-ink-2 md:col-span-2">Summary / developer notes (markdown)
              <textarea value={desc} onChange={(e) => setDesc(e.target.value)} rows={3} className="mt-1 w-full rounded-md border border-hx bg-app px-3 py-2 text-[13px] text-ink-1 focus:border-helix-400 focus:outline-none" />
            </label>
            <label className="text-[12px] text-ink-2 md:col-span-2">Result JSON (optional)
              <textarea value={cjson} onChange={(e) => setCjson(e.target.value)} rows={2} placeholder='{"passed": 120, "failed": 0}' className="mt-1 w-full rounded-md border border-hx bg-app px-3 py-2 font-mono text-[12px] text-ink-1 focus:border-helix-400 focus:outline-none" />
            </label>
            <label className="text-[12px] text-ink-2">Attachment (optional)
              <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} className="mt-1 block w-full text-[12px] text-ink-2" />
            </label>
          </div>
          <div className="mt-3 flex justify-end">
            <Button disabled={busy === "upload"} onClick={submit}>{busy === "upload" ? "Uploading…" : "Upload evidence"}</Button>
          </div>
        </Card>
      )}

      <Card title="Evidence">
        {loading ? <LoadingState label="Loading evidence…" /> : rows.length === 0 ? (
          <EmptyState title="No evidence yet" description="Upload your validation test results to begin QA review." />
        ) : (
          <Table>
            <THead><TR><TH>Title</TH><TH>Type</TH><TH>Status</TH><TH>QA</TH><TH>Actions</TH></TR></THead>
            <TBody>
              {rows.map((e) => (
                <TR key={e.id}>
                  <TD><span className="text-ink-1">{e.title}</span>{e.review_summary && <p className="mt-0.5 max-w-[360px] truncate text-[11px] text-ink-3">{e.review_summary}</p>}</TD>
                  <TD><Chip tone="zinc" mono>{e.evidence_type}</Chip></TD>
                  <TD><Chip tone={TONE[e.status] || "default"} dot>{e.status}</Chip></TD>
                  <TD className="text-[11px] text-ink-3">{e.reviewed_by_agent || "—"}</TD>
                  <TD>
                    <div className="flex flex-wrap gap-1.5">
                      {canWrite && <Button size="sm" variant="outline" disabled={!!busy} onClick={() => act(e.id, () => api.qaReviewEvidence(e.id))}>QA Review</Button>}
                      {canApprove && e.status !== "accepted" && <Button size="sm" disabled={!!busy} onClick={() => act(e.id, () => api.acceptEvidence(e.id))}>Accept</Button>}
                      {canApprove && e.status !== "rejected" && <Button size="sm" variant="danger" disabled={!!busy} onClick={() => act(e.id, () => api.rejectEvidence(e.id, "Rejected from evidence table"))}>Reject</Button>}
                    </div>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </Card>
    </ProjectShell>
  );
}
