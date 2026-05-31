"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Send, FileCheck2 } from "lucide-react";
import { ProjectShell } from "@/components/layout/ProjectShell";
import { Card, Button, Chip, EmptyState, LoadingState, ErrorBanner, StatusBadge } from "@/components/ui";
import type { ChipTone } from "@/components/ui";
import { useProjectKey } from "@/lib/projects/useProjectKey";
import { useAuth } from "@/lib/auth-context";
import { useRegisterCrumbLabel } from "@/lib/breadcrumbs";
import * as api from "@/lib/signoff/api";
import type { Signoff } from "@/lib/signoff/api";

const TONE: Record<string, ChipTone> = { draft: "zinc", sent: "info", approved: "ok", rejected: "err" };

export default function SignoffPage() {
  const projectParam = String(useParams<{ id: string }>().id);
  const { id, key, name } = useProjectKey(projectParam);
  const { can } = useAuth();
  useRegisterCrumbLabel(projectParam, name);
  const canWrite = can("project:write");
  const canApprove = can("agent:approve");

  const [items, setItems] = useState<Signoff[]>([]);
  const [sel, setSel] = useState<Signoff | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [recipient, setRecipient] = useState(""); const [subject, setSubject] = useState(""); const [body, setBody] = useState("");

  const pick = (s: Signoff | null) => {
    setSel(s); setRecipient(s?.recipient_email || ""); setSubject(s?.subject || ""); setBody(s?.body || "");
  };

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const list = await api.listSignoffs(id);
      setItems(list);
      setSel((prev) => { const n = list.find((x) => x.id === prev?.id) || list[0] || null; pick(n); return n; });
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

  const isDraft = sel?.status === "draft";

  return (
    <ProjectShell projectId={key} projectName={name || "Project"}>
      {err && <ErrorBanner message={err} onDismiss={() => setErr(null)} />}

      <Card title="Business sign-off" description="Generate a sign-off email draft from the approved recon report, review/edit it, then send. Email is never auto-sent."
        actions={canWrite && <Button size="sm" disabled={!!busy} onClick={() => act("draft", () => api.createSignoffDraft(id))}><FileCheck2 className="h-4 w-4" /> New draft</Button>}>
        {loading ? <LoadingState label="Loading…" /> : items.length === 0 ? (
          <EmptyState title="No sign-off yet" description="Create a draft once the reconciliation report is approved." />
        ) : (
          <div className="flex flex-wrap gap-2">
            {items.map((s) => (
              <button key={s.id} onClick={() => pick(s)} className={`flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-[12.5px] ${sel?.id === s.id ? "border-helix-400 bg-app-2" : "border-hx hover:bg-app-2"}`}>
                <Chip tone={TONE[s.status] || "default"} dot>{s.status}</Chip>
                <span className="text-ink-2">{s.recipient_email || "no recipient"}</span>
              </button>
            ))}
          </div>
        )}
      </Card>

      {sel && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_300px]">
          <Card title="Email draft" actions={<StatusBadge status={sel.status} />}>
            <div className="space-y-3 text-[12.5px]">
              <label className="block text-ink-2">Recipient
                <input value={recipient} onChange={(e) => setRecipient(e.target.value)} disabled={!isDraft || !canWrite}
                  className="mt-1 w-full rounded-md border border-hx bg-app px-3 py-2 text-[13px] text-ink-1 disabled:opacity-60 focus:border-helix-400 focus:outline-none" placeholder="reviewer@company.com" />
              </label>
              <label className="block text-ink-2">Subject
                <input value={subject} onChange={(e) => setSubject(e.target.value)} disabled={!isDraft || !canWrite}
                  className="mt-1 w-full rounded-md border border-hx bg-app px-3 py-2 text-[13px] text-ink-1 disabled:opacity-60 focus:border-helix-400 focus:outline-none" />
              </label>
              <label className="block text-ink-2">Body (HTML)
                <textarea value={body} onChange={(e) => setBody(e.target.value)} disabled={!isDraft || !canWrite} rows={10}
                  className="mt-1 w-full rounded-md border border-hx bg-app px-3 py-2 font-mono text-[12px] text-ink-1 disabled:opacity-60 focus:border-helix-400 focus:outline-none" />
              </label>
              {isDraft && canWrite && (
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" disabled={!!busy} onClick={() => act("save", () => api.updateSignoff(sel.id, { recipient_email: recipient, subject, body }))}>Save draft</Button>
                  <Button size="sm" disabled={!!busy || !recipient.trim()} onClick={() => act("send", async () => { await api.updateSignoff(sel.id, { recipient_email: recipient, subject, body }); await api.sendSignoff(sel.id); })}>
                    <Send className="h-3.5 w-3.5" /> {busy === "send" ? "Sending…" : "Save & Send"}
                  </Button>
                </div>
              )}
            </div>
          </Card>

          <div className="space-y-6">
            <Card title="Preview">
              <div className="rounded-md border border-hx bg-app p-3 text-[13px] text-ink-1" dangerouslySetInnerHTML={{ __html: body || "<p class='text-ink-3'>Empty</p>" }} />
            </Card>
            <Card title="Attachments (linked)">
              {sel.attachment_paths.length === 0 ? <p className="text-[12px] text-ink-3">None.</p> : (
                <ul className="space-y-1 text-[12px] text-ink-2">{sel.attachment_paths.map((p, i) => <li key={i} className="truncate font-mono">{p}</li>)}</ul>
              )}
            </Card>
            {canApprove && sel.status === "sent" && (
              <Card title="Record decision">
                <div className="flex gap-2">
                  <Button size="sm" disabled={!!busy} onClick={() => act("approve", () => api.markSignoffApproved(sel.id))}>Mark approved</Button>
                  <Button size="sm" variant="danger" disabled={!!busy} onClick={() => act("reject", () => api.markSignoffRejected(sel.id))}>Mark rejected</Button>
                </div>
              </Card>
            )}
            <Card title="Audit">
              <dl className="space-y-2 text-[12px]">
                <div className="flex justify-between"><dt className="text-ink-3">Created</dt><dd className="text-ink-1">{sel.created_at?.slice(0, 16)?.replace("T", " ") || "—"}</dd></div>
                <div className="flex justify-between"><dt className="text-ink-3">Sent</dt><dd className="text-ink-1">{sel.sent_at?.slice(0, 16)?.replace("T", " ") || "—"}</dd></div>
                <div className="flex justify-between"><dt className="text-ink-3">Decided</dt><dd className="text-ink-1">{sel.approved_at?.slice(0, 16)?.replace("T", " ") || "—"}</dd></div>
              </dl>
            </Card>
          </div>
        </div>
      )}
    </ProjectShell>
  );
}
