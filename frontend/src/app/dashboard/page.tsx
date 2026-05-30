"use client";

/**
 * /dashboard — Migration Command Center.
 *
 * The metric strip is hydrated from /api/v1/dashboard/stats and the LLM spend
 * row from /api/v1/usage/llm. Sections without a backing endpoint render a
 * clean empty state until real data lands; no placeholder/sample data is shown.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { Download, Plus } from "lucide-react";

import { useAuth } from "@/lib/auth-context";
import { fetchDashboardStats, type DashboardStats } from "@/lib/dashboard/api";
import { fetchUsageSummary, type UsageSummary } from "@/lib/usage/api";

import { AppShell } from "@/components/layout";
import {
  Button,
  Card,
  MetricCell,
  EmptyState,
  ErrorBanner,
  SkeletonMetricRow,
} from "@/components/ui";

export default function DashboardPage() {
  const { token } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [loadError, setLoadError] = useState<string>("");

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    fetchDashboardStats(token)
      .then((s) => { if (!cancelled) setStats(s); })
      .catch((e: unknown) => { if (!cancelled) { setStats(null); setLoadError((e instanceof Error ? e.message : null) ?? "Failed to load dashboard stats"); } });
    fetchUsageSummary(token, 30)
      .then((u) => { if (!cancelled) setUsage(u); })
      .catch((e: unknown) => { if (!cancelled) { setUsage(null); setLoadError((e instanceof Error ? e.message : null) ?? "Failed to load usage summary"); } });
    return () => { cancelled = true; };
  }, [token]);

  const fmtPct = (v: number | null) => (v === null ? "—" : `${v.toFixed(1)}%`);
  const fmtUsd = (v: number) =>
    v >= 1000 ? `$${(v / 1000).toFixed(1)}k` : `$${v.toFixed(2)}`;

  return (
    <AppShell
      eyebrow="MIGRATION COMMAND CENTER"
      title="Operations overview"
      metric={
        stats
          ? `${stats.activeProjects} active · ${stats.workflowsPending} awaiting · ${stats.workflowsRunning} running`
          : undefined
      }
      description="Live operational view of all enterprise migrations, validations, and recon outcomes."
      crumbs={["Command Center"]}
      actions={
        <>
          <Button variant="outline">
            <Download className="h-3.5 w-3.5" /> Export
          </Button>
          <Link href="/projects/new">
            <Button variant="primary">
              <Plus className="h-3.5 w-3.5" /> New migration
            </Button>
          </Link>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {loadError && <ErrorBanner message={loadError} onDismiss={() => setLoadError("")} />}
        {/* Metric strip — every value now comes from /api/v1/dashboard/stats.
            UI-046: a shaped skeleton holds the strip's footprint on first paint
            so values don't pop in with layout shift. */}
        {!stats && !loadError ? (
          <SkeletonMetricRow cells={5} />
        ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 bg-surface border border-hx rounded-[10px] divide-y lg:divide-y-0 lg:divide-x divide-[var(--con-line)] overflow-hidden">
          <MetricCell big label="ACTIVE PROJECTS"
            value={stats ? String(stats.activeProjects) : "—"}
            hint={stats ? `${stats.archivedProjects} archived` : "loading…"}
          />
          <MetricCell big label="VALIDATION PASS"
            value={stats ? fmtPct(stats.validationPassRate) : "—"}
            hint={stats?.validationPassRate === null ? "no runs yet" : "across all results"}
          />
          <MetricCell big label="RECON SCORE"
            value={stats ? fmtPct(stats.reconScore) : "—"}
            hint={stats?.reconScore === null ? "no recon runs" : "clean / total"}
          />
          <MetricCell big label="PENDING APPROVAL"
            value={stats ? String(stats.workflowsPending) : "—"}
            hint={stats ? "awaiting human review" : "loading…"}
            accent={stats && stats.workflowsPending > 0 ? "var(--con-warn)" : undefined}
          />
          <MetricCell big label="FAILED"
            value={stats ? String(stats.workflowsFailed) : "—"}
            hint={stats ? "rejected + expired" : "loading…"}
            accent={stats && stats.workflowsFailed > 0 ? "var(--con-err)" : undefined}
          />
        </div>
        )}

        {/* LLM spend row — real numbers from /api/v1/usage/llm. */}
        <div className="grid grid-cols-1 sm:grid-cols-4 bg-surface border border-hx rounded-[10px] divide-y sm:divide-y-0 sm:divide-x divide-[var(--con-line)] overflow-hidden">
          <MetricCell label="LLM SPEND · 30D"
            value={usage ? fmtUsd(usage.total_cost_usd) : "—"}
            hint={usage ? `${(usage.input_tokens + usage.output_tokens).toLocaleString()} tokens` : "loading…"}
          />
          <MetricCell label="TOP PROVIDER"
            value={usage && usage.by_provider.length > 0 ? usage.by_provider.slice().sort((a, b) => b.cost_usd - a.cost_usd)[0].provider : "—"}
            hint={usage && usage.by_provider.length > 0 ? fmtUsd(usage.by_provider.slice().sort((a, b) => b.cost_usd - a.cost_usd)[0].cost_usd) : ""}
          />
          <MetricCell label="TOP AGENT"
            value={usage && usage.by_agent.length > 0 ? usage.by_agent.slice().sort((a, b) => b.cost_usd - a.cost_usd)[0].agent : "—"}
            hint={usage && usage.by_agent.length > 0 ? fmtUsd(usage.by_agent.slice().sort((a, b) => b.cost_usd - a.cost_usd)[0].cost_usd) : ""}
          />
          <MetricCell label="INPUT / OUTPUT"
            value={usage ? `${Math.round(usage.input_tokens / 1000)}K / ${Math.round(usage.output_tokens / 1000)}K` : "—"}
            hint="tokens · 30d window"
          />
        </div>

        {/* Trend + Validation outcomes */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Card
            title="Migration throughput"
            description="Tables migrated per day"
            className="col-span-2"
          >
            <EmptyState
              title="No throughput data yet"
              description="Once migrations start running, daily throughput will be charted here."
            />
          </Card>

          <Card title="Validation outcomes" eyebrow="LAST 24 H" description="Pass / warning / fail breakdown">
            <EmptyState
              title="No validation runs yet"
              description="Validation outcomes appear here after your first run completes."
            />
          </Card>
        </div>

        {/* Live feed + Risk matrix */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Card
            title="Agent activity"
            eyebrow="LIVE STREAM"
            description="Realtime events from running BMAD workflows"
            className="col-span-2"
          >
            <EmptyState
              title="No activity yet"
              description="Events from running workflows will stream here in real time."
            />
          </Card>

          <Card title="Risk matrix" eyebrow="LIKELIHOOD × IMPACT" description="Projects plotted by AI risk model">
            <EmptyState
              title="No risk data yet"
              description="Projects will be plotted here once the risk model has scored them."
            />
          </Card>
        </div>

        {/* Projects at risk */}
        <Card
          title="Projects requiring attention"
          description="Sorted by risk score"
          actions={
            <Link href="/projects">
              <Button variant="ghost" size="sm">View all</Button>
            </Link>
          }
        >
          <EmptyState
            title="No projects at risk"
            description="Projects flagged by the risk model will be listed here."
          />
        </Card>

        {/* Agent roster + connector health */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Card title="Agent roster" eyebrow="BMAD CREW" description="Per-agent reliability and routing" className="col-span-2">
            <EmptyState
              title="No agent activity yet"
              description="Per-agent reliability and routing appear here once your crew starts running."
            />
          </Card>

          <Card title="Connector fleet" description="Average response latency">
            <EmptyState
              title="No connectors yet"
              description="Connector health and latency will be shown here once connectors are configured."
            />
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
