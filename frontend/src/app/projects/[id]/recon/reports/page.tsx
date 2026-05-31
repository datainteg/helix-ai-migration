"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { FileText, Code2, FileBarChart } from "lucide-react";
import { ProjectShell } from "@/components/layout/ProjectShell";
import { Card, Button, Chip, EmptyState, LoadingState, ErrorBanner, StatusBadge } from "@/components/ui";
import { useProjectKey } from "@/lib/projects/useProjectKey";
import { useAuth } from "@/lib/auth-context";
import { useRegisterCrumbLabel } from "@/lib/breadcrumbs";
import * as api from "@/lib/recon/api";
import type { ReconReport } from "@/lib/recon/api";

export default function ReconReportsPage() {
  const projectParam = String(useParams<{ id: string }>().id);
  const { id, key, name } = useProjectKey(projectParam);
  const { can } = useAuth();
  useRegisterCrumbLabel(projectParam, name);
  const canWrite = can("project:write");

  const [reports, setReports] = useState<ReconReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    try { setReports(await api.listReconReports(id)); }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  }, [id]);
  useEffect(() => { load(); }, [load]);

  async function act(label: string, fn: () => Promise<unknown>, ok?: string) {
    setBusy(label); setErr(null); setNote(null);
    try { await fn(); if (ok) setNote(ok); await load(); }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(null); }
  }

  return (
    <ProjectShell projectId={key} projectName={name || "Project"}>
      <div className="flex items-center justify-between">
        <Link href={`/projects/${key}/recon`} className="text-[12.5px] text-ink-3 hover:text-ink-1">← Recon</Link>
      </div>
      {err && <ErrorBanner message={err} onDismiss={() => setErr(null)} />}
      {note && <div className="rounded-md border border-[var(--con-ok)]/40 bg-[var(--con-ok)]/10 px-3 py-2 text-[12.5px] text-ink-1">{note}</div>}

      {canWrite && (
        <Card title="Recon Agent" description="Generate a recon plan, draft recon code (SQL/Python — draft, never executed by Helix), and a business-ready report from your approved context.">
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" disabled={!!busy} onClick={() => act("plan", () => api.generateReconPlan(id), "Recon plan generated — review it on the Lifecycle → Reconciliation stage.")}>
              <FileText className="h-4 w-4" /> {busy === "plan" ? "Generating…" : "Generate Plan"}
            </Button>
            <Button variant="outline" disabled={!!busy} onClick={() => act("code", () => api.generateReconCode(id), "Draft recon code generated — review it in the Developer Workspace.")}>
              <Code2 className="h-4 w-4" /> {busy === "code" ? "Generating…" : "Generate Code"}
            </Button>
            <Button disabled={!!busy} onClick={() => act("report", () => api.generateReconReport(id))}>
              <FileBarChart className="h-4 w-4" /> {busy === "report" ? "Generating…" : "Generate Report"}
            </Button>
          </div>
        </Card>
      )}

      <Card title="Reports">
        {loading ? <LoadingState label="Loading reports…" /> : reports.length === 0 ? (
          <EmptyState title="No recon reports yet" description="Generate a business-ready reconciliation report to begin sign-off." />
        ) : (
          <ul className="space-y-2">
            {reports.map((r) => (
              <li key={r.id}>
                <Link href={`/projects/${key}/recon/reports/${r.id}`} className="flex items-center justify-between rounded-md border border-hx bg-app-2/40 px-3 py-2.5 hover:bg-app-2">
                  <div className="flex items-center gap-2">
                    <FileBarChart className="h-4 w-4 text-ink-3" />
                    <span className="text-[13px] text-ink-1">Reconciliation report</span>
                    <Chip tone="zinc" mono>{r.report_type}</Chip>
                    {r.has_pdf && <Chip tone="info" mono>PDF</Chip>}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] text-ink-3">{r.created_at?.slice(0, 16)?.replace("T", " ")}</span>
                    <StatusBadge status={r.status} />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </ProjectShell>
  );
}
