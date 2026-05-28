"use client";

/**
 * /dashboard — Migration Command Center.
 *
 * Visual layout ported from the Figma `tsx-redesign` source. Demo data is
 * embedded inline; replace each block with a `useQuery` call as backend
 * endpoints land. Sections marked TODO: hydrate.
 */

import Link from "next/link";
import dynamic from "next/dynamic";
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
  StatusBadge,
  ProgressBar,
  Avatar,
  Tabs,
  Chip,
  DemoBanner,
  ErrorBanner,
  Skeleton,
  SkeletonMetricRow,
} from "@/components/ui";
import { AppIcon, AgentIcon, LLMIcon } from "@/components/icons";

// UI-037 — the SVG chart bundles are heavy and below the fold on first paint, so
// lazy-load them client-side. A sized Skeleton holds the layout to avoid CLS.
const AreaChart = dynamic(() => import("@/components/ui/AreaChart").then((m) => m.AreaChart), {
  ssr: false,
  loading: () => <Skeleton className="h-[220px] w-full" />,
});
const Donut = dynamic(() => import("@/components/ui/Donut").then((m) => m.Donut), {
  ssr: false,
  loading: () => <Skeleton className="h-[132px] w-[132px] rounded-full" />,
});
const Sparkline = dynamic(() => import("@/components/ui/Sparkline").then((m) => m.Sparkline), {
  ssr: false,
  loading: () => <Skeleton className="h-5 w-[70px]" />,
});

// ─── Demo data — TODO: hydrate from API ────────────────────────────

const TREND_DATA = [
  { label: "Apr 27", a: 12, b: 8 },
  { label: "Apr 30", a: 18, b: 10 },
  { label: "May 03", a: 22, b: 14 },
  { label: "May 06", a: 19, b: 12 },
  { label: "May 09", a: 27, b: 17 },
  { label: "May 12", a: 31, b: 22 },
  { label: "May 15", a: 28, b: 19 },
  { label: "May 18", a: 38, b: 24 },
  { label: "May 21", a: 42, b: 27 },
  { label: "May 24", a: 51, b: 31 },
];

const AGENT_EVENTS = [
  { t: "12:42:08", agent: "Amelia",  kind: "ok",   msg: "Code review · risk LOW · 3 suggestions",   tag: "P-1042" },
  { t: "12:41:52", agent: "Amelia",  kind: "info", msg: "Generated migrate.py · 412 lines",          tag: "P-1042" },
  { t: "12:41:08", agent: "Winston", kind: "ok",   msg: "Architecture readiness · PASS (16/16)",     tag: "P-1042" },
  { t: "12:39:21", agent: "Sally",   kind: "info", msg: "UX spec · 12 views, 4 modals",              tag: "P-1042" },
  { t: "12:38:55", agent: "John",    kind: "info", msg: "PRD complete · 8 epics, 31 stories",        tag: "P-1042" },
  { t: "12:37:02", agent: "Mary",    kind: "info", msg: "Product brief · 4 personas identified",     tag: "P-1042" },
  { t: "12:36:14", agent: "System",  kind: "info", msg: "Workflow bmad-a8f3c2 started",              tag: "P-1042" },
  { t: "12:34:47", agent: "Amelia",  kind: "warn", msg: "QA tests · 2 flaky cases, retrying",        tag: "P-1038" },
  { t: "12:33:18", agent: "Human",   kind: "ok",   msg: "Approved planning chain by @priya",         tag: "P-1038" },
] as const;

const AGENT_ROSTER = [
  { name: "Mary",    role: "Business Analyst",      provider: "Anthropic",  model: "claude-3.7-sonnet", success: 98.4, runs: 1247, trend: [97, 98, 97.5, 98.4] },
  { name: "John",    role: "Product Manager",       provider: "Anthropic",  model: "claude-3.7-sonnet", success: 96.1, runs: 982,  trend: [94, 95, 96, 96.1] },
  { name: "Sally",   role: "UX Designer",           provider: "OpenAI",     model: "gpt-4o",            success: 92.8, runs: 814,  trend: [90, 91, 92, 92.8] },
  { name: "Winston", role: "Solutions Architect",   provider: "Anthropic",  model: "claude-3.7-sonnet", success: 95.3, runs: 1102, trend: [93, 94, 95, 95.3] },
  { name: "Amelia",  role: "Senior Engineer",       provider: "DeepSeek",   model: "deepseek-v3",       success: 91.2, runs: 1641, trend: [88, 89, 90, 91.2] },
  { name: "Paige",   role: "Tech Writer",           provider: "OpenAI",     model: "gpt-4o-mini",       success: 99.0, runs: 654,  trend: [98, 98.5, 99, 99] },
];

const PROJECTS_AT_RISK = [
  { id: "P-1042", name: "Oracle GL → Snowflake",      source: "oracle",    target: "snowflake",  status: "running",   risk: 78, valid: 64, recon: 71, owner: "Priya Shah",     updated: "2m ago" },
  { id: "P-1038", name: "SAS Marketing → Databricks", source: "sas",       target: "databricks", status: "awaiting",  risk: 71, valid: 89, recon: 92, owner: "Daniel Park",    updated: "14m ago" },
  { id: "P-1031", name: "SQL Server CRM → Postgres",  source: "sqlserver", target: "postgres",   status: "failed",    risk: 92, valid: 41, recon: 38, owner: "Mei Lin",        updated: "1h ago" },
  { id: "P-1025", name: "DataStage Finance → DBT",    source: "datastage", target: "dbt",        status: "running",   risk: 58, valid: 78, recon: 84, owner: "Tomás Ribeiro",  updated: "3h ago" },
  { id: "P-1019", name: "Salesforce → S3 Lake",       source: "salesforce", target: "s3",        status: "running",   risk: 44, valid: 96, recon: 88, owner: "Avery Johnson",  updated: "5h ago" },
];

const CONNECTOR_HEALTH = [
  { name: "PostgreSQL", count: 8, status: "ok",   latency: "12ms" },
  { name: "Snowflake",  count: 5, status: "ok",   latency: "28ms" },
  { name: "Oracle",     count: 4, status: "warn", latency: "184ms" },
  { name: "SQL Server", count: 6, status: "ok",   latency: "22ms" },
  { name: "S3",         count: 3, status: "ok",   latency: "8ms" },
  { name: "Databricks", count: 2, status: "ok",   latency: "45ms" },
];

const RISK_GRID = [
  [1, 4, 7],
  [2, 6, 3],
  [5, 2, 1],
];

const fmt = {
  n: (v: number) => new Intl.NumberFormat("en-US").format(v),
};

export default function DashboardPage() {
  const [trendRange, setTrendRange] = useState("30");
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
      metric="24 active · 6 awaiting · 3 at risk"
      description="Live operational view of all enterprise migrations, validations, and recon outcomes across DataInteg Inc."
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
        {stats?.hasAnyData ? null : (
          <DemoBanner message="Charts and tables below are sample. Once you create a project and run a workflow, the metric strip + workflow tiles populate from real data." />
        )}
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
            description="Tables migrated per day · last 30 days"
            actions={
              <Tabs
                tabs={[
                  { id: "7", label: "7d" },
                  { id: "30", label: "30d" },
                  { id: "90", label: "90d" },
                ]}
                value={trendRange}
                onChange={setTrendRange}
              />
            }
            className="col-span-2"
          >
            <div className="flex items-baseline gap-4 mb-1">
              <div className="font-mono tabular-nums text-[30px] font-medium tracking-editorial">1,247</div>
              <div className="font-mono text-[12px] text-ok">▲ 18.4%</div>
              <div className="ml-auto flex gap-3.5 text-[11.5px] text-ink-4">
                <span className="inline-flex items-center gap-1.5">
                  <span className="inline-block w-3.5 h-[2px] bg-ink" /> Completed
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="inline-block w-3.5 border-t-[1.5px] border-dashed border-[var(--con-brand)]" /> In progress
                </span>
              </div>
            </div>
            <div className="w-full overflow-x-auto">
              <AreaChart data={TREND_DATA} width={760} height={220} />
            </div>
          </Card>

          <Card title="Validation outcomes" eyebrow="LAST 24 H" description="Across 2,341 validation runs">
            <div className="flex items-center gap-4 py-2">
              <Donut
                size={132}
                thickness={14}
                centerValue="92.4%"
                centerLabel="PASS RATE"
                data={[
                  { label: "Passed",   value: 1862, color: "var(--con-ok)" },
                  { label: "Warnings", value: 312,  color: "var(--con-warn)" },
                  { label: "Failed",   value: 167,  color: "var(--con-err)" },
                ]}
              />
              <div className="flex-1 flex flex-col gap-2.5">
                {[
                  { label: "Passed",   value: 1862, color: "var(--con-ok)",   pct: 79.5 },
                  { label: "Warnings", value: 312,  color: "var(--con-warn)", pct: 13.3 },
                  { label: "Failed",   value: 167,  color: "var(--con-err)",  pct: 7.1 },
                ].map((r) => (
                  <div key={r.label} className="flex items-center gap-2.5">
                    <span className="w-2 h-2 rounded-sm" style={{ background: r.color }} />
                    <span className="text-[12px] text-ink-2 flex-1">{r.label}</span>
                    <span className="font-mono tabular-nums text-[12.5px] font-medium">{fmt.n(r.value)}</span>
                    <span className="font-mono text-[11px] text-ink-3 w-10 text-right">{r.pct}%</span>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        </div>

        {/* Live feed + Risk matrix */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Card
            title="Agent activity"
            eyebrow="LIVE STREAM"
            description="Realtime events from running BMAD workflows"
            actions={
              <>
                <Chip tone="ok" dot pulse>Live</Chip>
                <Button variant="ghost" size="sm">All projects</Button>
              </>
            }
            className="col-span-2"
            bodyClassName="p-0"
          >
            <div className="max-h-[360px] overflow-y-auto border-t border-hx">
              {AGENT_EVENTS.map((e, i) => {
                const kindColor =
                  e.kind === "ok"   ? "var(--con-ok)" :
                  e.kind === "warn" ? "var(--con-warn)" :
                                      "var(--con-ink-3)";
                return (
                  <div
                    key={i}
                    className="grid items-center gap-3 px-[18px] py-2.5 border-b border-hx last:border-b-0 text-[12px]"
                    style={{ gridTemplateColumns: "72px 80px 1fr 60px" }}
                  >
                    <span className="font-mono text-[11px] text-ink-4">{e.t}</span>
                    <span className="inline-flex items-center gap-1.5 text-[11.5px] text-ink-2">
                      <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: kindColor }} />
                      <AgentIcon name={e.agent} size={16} />
                      {e.agent}
                    </span>
                    <span className="text-ink-2">{e.msg}</span>
                    <span className="font-mono text-[11px] text-ink-4 text-right">{e.tag}</span>
                  </div>
                );
              })}
            </div>
          </Card>

          <Card title="Risk matrix" eyebrow="LIKELIHOOD × IMPACT" description="Projects plotted by AI risk model">
            <div className="grid grid-cols-[40px_1fr] gap-2 py-1">
              <div className="flex flex-col justify-around pt-1">
                {["High", "Med", "Low"].map((l) => (
                  <span key={l} className="font-mono text-[10px] text-ink-4 tracking-[0.05em]">{l}</span>
                ))}
              </div>
              <div>
                <div className="grid grid-cols-3 gap-1">
                  {RISK_GRID.flat().map((v, i) => {
                    const bg =
                      v === 0 ? "var(--con-bg-2)" :
                      v <= 2  ? "#EFF6E5" :
                      v <= 4  ? "#FEF3C7" :
                      v <= 6  ? "#FED7AA" : "#FECACA";
                    const fg =
                      v >= 5 ? "var(--con-err)" :
                      v >= 3 ? "var(--con-warn)" :
                      v > 0  ? "var(--con-ok)"  : "var(--con-ink-5)";
                    return (
                      <div
                        key={i}
                        className="h-12 rounded grid place-items-center font-mono text-[13px] font-medium"
                        style={{ background: bg, color: fg }}
                      >
                        {v || "·"}
                      </div>
                    );
                  })}
                </div>
                <div className="grid grid-cols-3 gap-1 mt-1.5">
                  {["Low", "Med", "High"].map((l) => (
                    <span key={l} className="font-mono text-[10px] text-ink-4 text-center tracking-[0.05em]">{l}</span>
                  ))}
                </div>
              </div>
            </div>
            <div className="eyebrow text-[9.5px] mt-3.5">Impact ↑ · Likelihood →</div>
          </Card>
        </div>

        {/* Projects at risk */}
        <Card
          title="Projects requiring attention"
          description="Sorted by risk score · 5 of 24 projects"
          actions={
            <Link href="/projects">
              <Button variant="ghost" size="sm">View all</Button>
            </Link>
          }
          bodyClassName="p-0"
        >
          <div className="overflow-x-auto border-t border-hx">
            <table className="w-full border-collapse text-[12.5px]">
              <thead>
                <tr className="bg-surface-hi">
                  {["", "Project", "Source → Target", "Owner", "Risk", "Validation", "Recon", "Status", "Updated"].map((h, i) => (
                    <th
                      key={i}
                      className="px-3.5 py-2.5 font-medium text-ink-4 text-[10.5px] uppercase tracking-[0.08em] font-mono text-left border-b border-hx"
                      style={i === 0 ? { width: 4 } : undefined}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {PROJECTS_AT_RISK.map((p) => {
                  const riskColor =
                    p.risk >= 80 ? "var(--con-err)" :
                    p.risk >= 60 ? "var(--con-warn)" :
                    p.risk >= 40 ? "var(--con-info)" : "var(--con-ok)";
                  return (
                    <tr key={p.id} className="border-b border-hx last:border-b-0 cursor-pointer hover:bg-surface-hi">
                      <td className="p-0" style={{ width: 4 }}>
                        <div className="w-[3px] h-[42px]" style={{ background: riskColor }} />
                      </td>
                      <td className="px-3.5 py-3">
                        <Link href={`/projects/${p.id}`} className="block">
                          <div className="flex flex-col gap-0.5">
                            <span className="font-medium text-ink">{p.name}</span>
                            <span className="font-mono text-[11px] text-ink-3">{p.id}</span>
                          </div>
                        </Link>
                      </td>
                      <td className="px-3.5 py-3">
                        <span className="font-mono text-[11.5px] text-ink-3">
                          {p.source} → {p.target}
                        </span>
                      </td>
                      <td className="px-3.5 py-3">
                        <div className="flex items-center gap-1.5">
                          <Avatar name={p.owner} size={20} />
                          <span className="text-ink-2 text-[12px]">{p.owner}</span>
                        </div>
                      </td>
                      <td className="px-3.5 py-3 min-w-[100px]">
                        <div className="flex items-center gap-2">
                          <span className="font-mono tabular-nums font-medium" style={{ color: riskColor }}>{p.risk}</span>
                          <div className="flex-1 max-w-[60px]">
                            <ProgressBar value={p.risk} tone={p.risk >= 80 ? "err" : p.risk >= 60 ? "warn" : "ink"} height={3} />
                          </div>
                        </div>
                      </td>
                      <td className="px-3.5 py-3 w-[110px]">
                        <div className="flex items-center gap-2">
                          <span className="font-mono tabular-nums text-[11.5px] text-ink-2 min-w-[30px]">{p.valid}%</span>
                          <ProgressBar value={p.valid} tone={p.valid >= 80 ? "ok" : "warn"} height={3} />
                        </div>
                      </td>
                      <td className="px-3.5 py-3 w-[110px]">
                        <div className="flex items-center gap-2">
                          <span className="font-mono tabular-nums text-[11.5px] text-ink-2 min-w-[30px]">{p.recon}%</span>
                          <ProgressBar value={p.recon} tone="ink" height={3} />
                        </div>
                      </td>
                      <td className="px-3.5 py-3"><StatusBadge status={p.status} /></td>
                      <td className="px-3.5 py-3 text-ink-4 text-[11.5px]">{p.updated}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Agent roster + connector health */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Card title="Agent roster" eyebrow="BMAD CREW" description="Per-agent reliability and routing" className="col-span-2" bodyClassName="p-0">
            <div className="border-t border-hx">
              <table className="w-full border-collapse text-[12.5px]">
                <thead>
                  <tr className="bg-surface-hi">
                    {["Agent", "Role", "Routing", "Success", "Runs", "Trend"].map((h, i) => (
                      <th
                        key={h}
                        className={`px-[18px] py-2 font-medium text-ink-4 text-[10.5px] uppercase tracking-[0.08em] font-mono ${i >= 3 ? "text-right" : "text-left"} border-b border-hx`}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {AGENT_ROSTER.map((a) => (
                    <tr key={a.name} className="border-b border-hx last:border-b-0">
                      <td className="px-[18px] py-2.5">
                        <div className="flex items-center gap-2.5">
                          <AgentIcon name={a.name} size={22} />
                          <span className="font-medium">{a.name}</span>
                        </div>
                      </td>
                      <td className="px-[18px] py-2.5 text-ink-3">{a.role}</td>
                      <td className="px-[18px] py-2.5">
                        <div className="inline-flex items-center gap-1.5 font-mono text-[11.5px] text-ink-2">
                          <LLMIcon provider={a.provider} size={14} />
                          {a.provider} · {a.model}
                        </div>
                      </td>
                      <td className="px-[18px] py-2.5 text-right">
                        <span
                          className="font-mono tabular-nums font-medium"
                          style={{ color: a.success > 95 ? "var(--con-ok)" : "var(--con-ink-2)" }}
                        >
                          {a.success.toFixed(1)}%
                        </span>
                      </td>
                      <td className="px-[18px] py-2.5 text-right font-mono tabular-nums text-ink-3">{fmt.n(a.runs)}</td>
                      <td className="px-[18px] py-2.5 text-right">
                        <div className="inline-block"><Sparkline data={a.trend} width={70} height={20} /></div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card title="Connector fleet" eyebrow="18 ACTIVE" description="Average response latency · last 5 min">
            <div className="flex flex-col">
              {CONNECTOR_HEALTH.map((c) => (
                <div
                  key={c.name}
                  className="grid items-center gap-3 py-1.5 border-b border-hx last:border-b-0 text-[12.5px]"
                  style={{ gridTemplateColumns: "20px 1fr auto auto" }}
                >
                  <AppIcon name={c.name} size={16} />
                  <span className="text-ink-2">{c.name}</span>
                  <span className="font-mono text-[11px] text-ink-4">×{c.count}</span>
                  <div className="flex items-center gap-1.5">
                    <span
                      className="w-1.5 h-1.5 rounded-full"
                      style={{ background: c.status === "ok" ? "var(--con-ok)" : "var(--con-warn)" }}
                    />
                    <span className="font-mono tabular-nums text-[11.5px] text-ink-2 min-w-[50px] text-right">{c.latency}</span>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
