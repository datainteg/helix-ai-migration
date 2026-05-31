"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ProjectShell } from "@/components/layout/ProjectShell";
import { Card, Button, Chip, EmptyState, LoadingState, ErrorBanner, MarkdownView } from "@/components/ui";
import type { ChipTone } from "@/components/ui";
import { useProjectKey } from "@/lib/projects/useProjectKey";
import { useAuth } from "@/lib/auth-context";
import { useRegisterCrumbLabel } from "@/lib/breadcrumbs";
import * as api from "@/lib/validation-evidence/api";
import type { ValidationEvidence } from "@/lib/validation-evidence/api";

const TONE: Record<string, ChipTone> = { uploaded: "zinc", under_review: "info", accepted: "ok", rejected: "err", changes_required: "warn" };

export default function ValidationReviewPage() {
  const projectParam = String(useParams<{ id: string }>().id);
  const { id, key, name } = useProjectKey(projectParam);
  const { can } = useAuth();
  useRegisterCrumbLabel(projectParam, name);
  const canWrite = can("project:write");
  const canApprove = can("agent:approve");

  const [rows, setRows] = useState<ValidationEvidence[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

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

  const accepted = rows.filter((r) => r.status === "accepted").length;

  return (
    <ProjectShell projectId={key} projectName={name || "Project"}>
      <div className="flex items-center justify-between">
        <Link href={`/projects/${key}/validation/evidence`} className="text-[12.5px] text-ink-3 hover:text-ink-1">← Evidence</Link>
        <span className="text-[12px] text-ink-3">{accepted} accepted · validation approvable {accepted > 0 ? "✓" : "—"}</span>
      </div>
      {err && <ErrorBanner message={err} onDismiss={() => setErr(null)} />}

      <Card title="QA review" description="The QA agent reviews uploaded evidence (coverage, failed tests, gaps, data-quality risks, deployment readiness). Accept ≥1 item to unlock VALIDATION-stage approval.">
        {loading ? <LoadingState label="Loading…" /> : rows.length === 0 ? (
          <EmptyState title="No evidence" description="Upload validation evidence first." />
        ) : (
          <div className="space-y-2">
            {rows.map((e) => (
              <div key={e.id} className="rounded-md border border-hx bg-app-2/40">
                <div className="flex items-center justify-between gap-2 px-3 py-2">
                  <button onClick={() => setOpen(open === e.id ? null : e.id)} className="flex items-center gap-2 text-left">
                    <Chip tone={TONE[e.status] || "default"} dot>{e.status}</Chip>
                    <span className="text-[13px] text-ink-1">{e.title}</span>
                    <span className="text-[11px] text-ink-3">{e.reviewed_by_agent ? `· QA: ${e.reviewed_by_agent}` : ""}</span>
                  </button>
                  <div className="flex gap-1.5">
                    {canWrite && <Button size="sm" variant="outline" disabled={!!busy} onClick={() => act(e.id, () => api.qaReviewEvidence(e.id))}>{e.reviewed_by_agent ? "Re-run QA" : "QA Review"}</Button>}
                    {canApprove && e.status !== "accepted" && <Button size="sm" disabled={!!busy} onClick={() => act(e.id, () => api.acceptEvidence(e.id))}>Accept</Button>}
                    {canApprove && e.status !== "rejected" && <Button size="sm" variant="danger" disabled={!!busy} onClick={() => act(e.id, () => api.rejectEvidence(e.id, "Rejected in QA review"))}>Reject</Button>}
                  </div>
                </div>
                {open === e.id && (
                  <div className="border-t border-hx p-3 text-[13px]">
                    {e.description && <p className="mb-2 text-ink-2">{e.description}</p>}
                    {e.review_summary ? <MarkdownView text={e.review_summary} className="hx-md" /> : <p className="text-ink-3">No QA review yet — run QA Review.</p>}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </ProjectShell>
  );
}
