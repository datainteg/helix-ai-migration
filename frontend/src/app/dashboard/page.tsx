"use client";

/**
 * /dashboard — Dashboard (Operations Overview).
 *
 * Metric strip + LLM spend from /dashboard/stats + /usage/llm. Live sections
 * (recent agent activity, validation outcomes, runs needing attention) come
 * from real aggregate endpoints. Sections without a backing endpoint are not
 * shown rather than rendered as fake/empty filler — no placeholder data.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { Download, Plus } from "lucide-react";

import { useAuth } from "@/lib/auth-context";
import {
  fetchDashboardStats, fetchDashboardActivity, fetchValidationBreakdown,
  type DashboardStats, type ActivityItem, type ValidationBreakdown,
} from "@/lib/dashboard/api";
import { fetchUsageSummary, type UsageSummary } from "@/lib/usage/api";

import { AppShell } from "@/components/layout";
import {
  Button, Card, MetricCell, EmptyState, ErrorBanner, SkeletonMetricRow, StatusBadge,
} from "@/components/ui";

const STATUS_TONE: Record<string, string> = {
  running: "info", started: "info", in_progress: "info",
  pending: "warn", awaiting_approval: "warn",
  completed: "ok", approved: "ok",
  failed: "err", rejected: "err", expired: "err",
};
const ATTENTION = new Set(["failed", "rejected", "expired", "pending", "awaiting_approval"]);

function relTime(iso: string | null): string {
  if (!iso) return "";
  const t = new Date(iso.replace(" ", "T")).getTime();
  if (Number.isNaN(t)) return "";
  const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export default function DashboardPage() {
  const { token } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [activity, setActivity] = useState<ActivityItem[] | null>(null);
  const [vbreak, setVbreak] = useState<ValidationBreakdown | null>(null);
  const [loadError, setLoadError] = useState<string>("");

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    fetchDashboardStats(token).then((s) => { if (!cancelled) setStats(s); })
      .catch((e: unknown) => { if (!cancelled) { setStats(null); setLoadError((e instanceof Error ? e.message : null) ?? "Failed to load dashboard stats"); } });
    fetchUsageSummary(token, 30).then((u) => { if (!cancelled) setUsage(u); })
      .catch(() => { if (!cancelled) setUsage(null); });
    fetchDashboardActivity(token, 12).then((a) => { if (!cancelled) setActivity(a); })
      .catch(() => { if (!cancelled) setActivity([]); });
    fetchValidationBreakdown(token).then((v) => { if (!cancelled) setVbreak(v); })
      .catch(() => { if (!cancelled) setVbreak(null); });
    return () => { cancelled = true; };
  }, [token]);

  const fmtPct = (v: number | null) => (v === null ? "—" : `${v.toFixed(1)}%`);
  const fmtUsd = (v: number) => (v >= 1000 ? `$${(v / 1000).toFixed(1)}k` : `$${v.toFixed(2)}`);

  const exportCsv = () => {
    if (!stats) return;
    const rows: [string, string | number][] = [
      ["Active projects", stats.activeProjects],
      ["Archived projects", stats.archivedProjects],
      ["Workflows running", stats.workflowsRunning],
      ["Workflows pending", stats.workflowsPending],
      ["Workflows completed", stats.workflowsCompleted],
      ["Workflows failed", stats.workflowsFailed],
      ["Validation pass rate %", stats.validationPassRate ?? ""],
      ["Recon score %", stats.reconScore ?? ""],
      ["LLM spend 30d USD", usage?.total_cost_usd ?? ""],
    ];
    const csv = "metric,value\n" + rows.map(([k, v]) => `"${k}",${v}`).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url; a.download = "helix-dashboard.csv";
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  };

  const attention = (activity ?? []).filter((a) => ATTENTION.has(a.status.toLowerCase()));

  return (
    <AppShell
      eyebrow="MIGRATION COMMAND CENTER"
      title="Operations overview"
      metric={stats ? `${stats.activeProjects} active · ${stats.workflowsPending} awaiting · ${stats.workflowsRunning} running` : undefined}
      description="Live operational view of all enterprise migrations, validations, and recon outcomes."
      crumbs={["Dashboard"]}
      actions={
        <>
          <Button variant="outline" onClick={exportCsv} disabled={!stats}>
            <Download className="h-3.5 w-3.5" /> Export
          </Button>
          <Link href="/projects/new">
            <Button variant="primary"><Plus className="h-3.5 w-3.5" /> New migration</Button>
          </Link>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {loadError && <ErrorBanner message={loadError} onDismiss={() => setLoadError("")} />}

        {/* Metric strip */}
        {!stats && !loadError ? (
          <SkeletonMetricRow cells={5} />
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 bg-surface border border-hx rounded-[10px] divide-y lg:divide-y-0 lg:divide-x divide-[var(--con-line)] overflow-hidden">
            <MetricCell big label="ACTIVE PROJECTS" value={stats ? String(stats.activeProjects) : "—"} hint={stats ? `${stats.archivedProjects} archived` : "loading…"} />
            <MetricCell big label="VALIDATION PASS" value={stats ? fmtPct(stats.validationPassRate) : "—"} hint={stats?.validationPassRate === null ? "no runs yet" : "across all results"} />
            <MetricCell big label="RECON SCORE" value={stats ? fmtPct(stats.reconScore) : "—"} hint={stats?.reconScore === null ? "no recon runs" : "clean / total"} />
            <MetricCell big label="PENDING APPROVAL" value={stats ? String(stats.workflowsPending) : "—"} hint={stats ? "awaiting human review" : "loading…"} accent={stats && stats.workflowsPending > 0 ? "var(--con-warn)" : undefined} />
            <MetricCell big label="FAILED" value={stats ? String(stats.workflowsFailed) : "—"} hint={stats ? "rejected + expired" : "loading…"} accent={stats && stats.workflowsFailed > 0 ? "var(--con-err)" : undefined} />
          </div>
        )}

        {/* LLM spend row */}
        <div className="grid grid-cols-1 sm:grid-cols-4 bg-surface border border-hx rounded-[10px] divide-y sm:divide-y-0 sm:divide-x divide-[var(--con-line)] overflow-hidden">
          <MetricCell label="LLM SPEND · 30D" value={usage ? fmtUsd(usage.total_cost_usd) : "—"} hint={usage ? `${(usage.input_tokens + usage.output_tokens).toLocaleString()} tokens` : "loading…"} />
          <MetricCell label="TOP PROVIDER" value={usage && usage.by_provider.length > 0 ? usage.by_provider.slice().sort((a, b) => b.cost_usd - a.cost_usd)[0].provider : "—"} hint={usage && usage.by_provider.length > 0 ? fmtUsd(usage.by_provider.slice().sort((a, b) => b.cost_usd - a.cost_usd)[0].cost_usd) : ""} />
          <MetricCell label="TOP AGENT" value={usage && usage.by_agent.length > 0 ? usage.by_agent.slice().sort((a, b) => b.cost_usd - a.cost_usd)[0].agent : "—"} hint={usage && usage.by_agent.length > 0 ? fmtUsd(usage.by_agent.slice().sort((a, b) => b.cost_usd - a.cost_usd)[0].cost_usd) : ""} />
          <MetricCell label="INPUT / OUTPUT" value={usage ? `${Math.round(usage.input_tokens / 1000)}K / ${Math.round(usage.output_tokens / 1000)}K` : "—"} hint="tokens · 30d window" />
        </div>

        {/* Agent activity + Validation outcomes */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Card title="Agent activity" eyebrow="RECENT RUNS" description="Latest workflow runs across the org" className="lg:col-span-2" bodyClassName="p-0">
            {activity === null ? (
              <div className="p-4 text-[12.5px] text-ink-4">Loading…</div>
            ) : activity.length === 0 ? (
              <div className="p-4"><EmptyState title="No activity yet" description="Runs appear here as BMAD/migration workflows start." /></div>
            ) : (
              <ul className="divide-y divide-hx">
                {activity.map((a) => (
                  <li key={a.workflow_id} className="flex items-center gap-3 px-4 py-2.5">
                    <StatusBadge status={a.status} />
                    <Link href={`/projects/${a.project_id}`} className="flex-1 min-w-0 group">
                      <div className="text-[12.5px] font-medium text-ink truncate group-hover:underline">{a.project_name || a.project_id}</div>
                      <div className="text-[11px] text-ink-4 font-mono truncate">{a.kind} · {a.workflow_id}</div>
                    </Link>
                    <span className="text-[11px] text-ink-4 whitespace-nowrap">{relTime(a.created_at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card title="Validation outcomes" eyebrow="ALL RESULTS" description="Pass / fail / warning breakdown">
            {!vbreak || vbreak.total === 0 ? (
              <EmptyState title="No validation runs yet" description="Outcomes appear here after your first validation run." />
            ) : (
              <div className="space-y-2.5">
                {Object.entries(vbreak.by_status).sort((a, b) => b[1] - a[1]).map(([status, count]) => {
                  const pct = (count / vbreak.total) * 100;
                  const tone = STATUS_TONE[status.toLowerCase()] ?? "default";
                  const color = tone === "ok" ? "var(--con-ok)" : tone === "err" ? "var(--con-err)" : tone === "warn" ? "var(--con-warn)" : "var(--con-ink-4)";
                  return (
                    <div key={status} className="space-y-1">
                      <div className="flex justify-between text-[12.5px]"><span className="text-ink-2 capitalize">{status}</span><span className="font-mono text-ink-3">{count} · {pct.toFixed(0)}%</span></div>
                      <div className="h-1.5 rounded-full bg-app-2 overflow-hidden"><div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} /></div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </div>

        {/* Runs requiring attention */}
        <Card
          title="Runs requiring attention"
          description="Failed, rejected, or awaiting approval"
          actions={<Link href="/agents"><Button variant="ghost" size="sm">View all</Button></Link>}
          bodyClassName="p-0"
        >
          {activity === null ? (
            <div className="p-4 text-[12.5px] text-ink-4">Loading…</div>
          ) : attention.length === 0 ? (
            <div className="p-4"><EmptyState title="Nothing needs attention" description="No failed or pending-approval runs right now." /></div>
          ) : (
            <ul className="divide-y divide-hx">
              {attention.map((a) => (
                <li key={a.workflow_id} className="flex items-center gap-3 px-4 py-2.5">
                  <StatusBadge status={a.status} />
                  <Link href={`/projects/${a.project_id}`} className="flex-1 min-w-0 group">
                    <span className="text-[12.5px] font-medium text-ink truncate group-hover:underline">{a.project_name || a.project_id}</span>
                  </Link>
                  <span className="text-[11px] text-ink-4 whitespace-nowrap">{relTime(a.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
