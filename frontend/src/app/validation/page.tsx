"use client";

/**
 * /validation — Validation Center.
 *
 * Visual layout ported from `Helix Figma Frontend/pages-validation.jsx`.
 * Demo data is inlined; replace each block with a `useQuery` call as backend
 * endpoints land.
 */

import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth-context";
import { fetchDashboardStats, type DashboardStats } from "@/lib/dashboard/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
import {
  AlertTriangle,
  Download,
  Plus,
  RefreshCw,
  Search,
} from "lucide-react";

import { AppShell } from "@/components/layout";
import {
  AreaChart,
  Avatar,
  Button,
  Card,
  Chip,
  EmptyState,
  StatusBadge,
  Tabs,
  DemoBanner,
  ErrorBanner,
} from "@/components/ui";

// ─── Demo data — TODO: hydrate from API ────────────────────────────

interface ValidationCheck {
  id: string;
  name: string;
  type: keyof typeof TYPE_LABELS;
  status: "passed" | "warning" | "failed";
  source: string;
  target: string;
  last: string;
  rows: string;
  owner: string;
}

const TYPE_LABELS = {
  row_count: "Row count",
  schema: "Schema",
  null: "Null check",
  duplicate: "Duplicates",
  distribution: "Distribution",
  business_rule: "Business rule",
} as const;

const VALIDATION_CHECKS: ValidationCheck[] = [
  { id: "VC-9241", name: "GL_LEDGER row count",         type: "row_count",     status: "passed",  source: "ORACLE.GL_LEDGER",  target: "SNOWFLAKE.GL.LEDGER",   last: "2m",  rows: "12,408,221", owner: "Priya Shah" },
  { id: "VC-9240", name: "GL_LEDGER schema parity",     type: "schema",        status: "passed",  source: "ORACLE.GL_LEDGER",  target: "SNOWFLAKE.GL.LEDGER",   last: "2m",  rows: "—",          owner: "Priya Shah" },
  { id: "VC-9239", name: "GL_TRANS null POSTING_DATE",  type: "null",          status: "warning", source: "ORACLE.GL_TRANS",   target: "—",                     last: "5m",  rows: "1,202 NULL", owner: "Daniel Park" },
  { id: "VC-9238", name: "GL_TRANS PK duplicates",      type: "duplicate",     status: "failed",  source: "ORACLE.GL_TRANS",   target: "—",                     last: "5m",  rows: "84 dup",     owner: "Daniel Park" },
  { id: "VC-9237", name: "CUSTOMER amount range",       type: "business_rule", status: "passed",  source: "SF.ACCOUNT",        target: "SNOWFLAKE.CRM.ACCOUNT", last: "12m", rows: "0 OOR",      owner: "Mei Lin" },
  { id: "VC-9236", name: "CUSTOMER status enum",        type: "business_rule", status: "passed",  source: "SF.ACCOUNT",        target: "SNOWFLAKE.CRM.ACCOUNT", last: "12m", rows: "0 inv",      owner: "Mei Lin" },
  { id: "VC-9235", name: "INVOICE amount distribution", type: "distribution",  status: "warning", source: "ORACLE.AR_INVOICE", target: "SNOWFLAKE.AR.INVOICE",  last: "21m", rows: "KS=0.14",    owner: "Tomás Ribeiro" },
  { id: "VC-9234", name: "INVOICE schema parity",       type: "schema",        status: "passed",  source: "ORACLE.AR_INVOICE", target: "SNOWFLAKE.AR.INVOICE",  last: "21m", rows: "—",          owner: "Tomás Ribeiro" },
  { id: "VC-9233", name: "PAYMENT row count",           type: "row_count",     status: "passed",  source: "ORACLE.AR_PAYMENT", target: "SNOWFLAKE.AR.PAYMENT",  last: "34m", rows: "2,184,401",  owner: "Avery Johnson" },
  { id: "VC-9232", name: "PAYMENT FK integrity",        type: "business_rule", status: "passed",  source: "ORACLE.AR_PAYMENT", target: "SNOWFLAKE.AR.PAYMENT",  last: "34m", rows: "0 orphans",  owner: "Avery Johnson" },
];

interface TypeBreakdown {
  t: keyof typeof TYPE_LABELS;
  p: number;
  w: number;
  f: number;
}

const TYPE_BREAKDOWN: TypeBreakdown[] = [
  { t: "row_count",     p: 18, w: 0, f: 0 },
  { t: "schema",        p: 22, w: 1, f: 0 },
  { t: "null",          p: 11, w: 3, f: 1 },
  { t: "duplicate",     p: 7,  w: 0, f: 2 },
  { t: "distribution",  p: 8,  w: 4, f: 0 },
  { t: "business_rule", p: 26, w: 2, f: 1 },
];

const RECON_TREND = [
  { label: "May 11", a: 91.4, b: 88 },
  { label: "May 12", a: 92.1, b: 89 },
  { label: "May 13", a: 92.8, b: 90 },
  { label: "May 14", a: 91.6, b: 88 },
  { label: "May 15", a: 93.2, b: 91 },
  { label: "May 16", a: 94.0, b: 92 },
  { label: "May 17", a: 94.7, b: 93 },
  { label: "May 18", a: 95.1, b: 93.5 },
  { label: "May 19", a: 95.4, b: 94 },
  { label: "May 20", a: 95.8, b: 94.5 },
  { label: "May 21", a: 96.0, b: 94.8 },
  { label: "May 22", a: 96.1, b: 95 },
  { label: "May 23", a: 96.3, b: 95.2 },
  { label: "May 24", a: 96.5, b: 95.5 },
];

export default function ValidationPage() {
  const { token } = useAuth();
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [hasProjects, setHasProjects] = useState<boolean | null>(null);
  const [orgStats, setOrgStats] = useState<DashboardStats | null>(null);
  const [loadError, setLoadError] = useState<string>("");

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    fetch(`${API_BASE}/api/v1/projects?limit=1`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : []))
      .then((rows: unknown[]) => { if (!cancelled) setHasProjects(rows.length > 0); })
      .catch((e: unknown) => { if (!cancelled) { setHasProjects(false); setLoadError((e instanceof Error ? e.message : null) ?? "Failed to load projects"); } });
    fetchDashboardStats(token)
      .then((s) => { if (!cancelled) setOrgStats(s); })
      .catch((e: unknown) => { if (!cancelled) { setOrgStats(null); setLoadError((e instanceof Error ? e.message : null) ?? "Failed to load dashboard stats"); } });
    return () => { cancelled = true; };
  }, [token]);

  const realPassRate = orgStats?.validationPassRate;
  const showRealHero = realPassRate !== null && realPassRate !== undefined;

  const total = VALIDATION_CHECKS.length;
  const passed = VALIDATION_CHECKS.filter((c) => c.status === "passed").length;
  const failed = VALIDATION_CHECKS.filter((c) => c.status === "failed").length;
  const warning = VALIDATION_CHECKS.filter((c) => c.status === "warning").length;

  const typeTabs = [
    { id: "all", label: "All", count: total },
    { id: "row_count", label: "Row count", count: VALIDATION_CHECKS.filter((c) => c.type === "row_count").length },
    { id: "schema", label: "Schema", count: VALIDATION_CHECKS.filter((c) => c.type === "schema").length },
    { id: "null", label: "Null", count: VALIDATION_CHECKS.filter((c) => c.type === "null").length },
    { id: "duplicate", label: "Duplicates", count: VALIDATION_CHECKS.filter((c) => c.type === "duplicate").length },
    { id: "distribution", label: "Distribution", count: VALIDATION_CHECKS.filter((c) => c.type === "distribution").length },
    { id: "business_rule", label: "Business rules", count: VALIDATION_CHECKS.filter((c) => c.type === "business_rule").length },
  ];

  const filtered = VALIDATION_CHECKS.filter(
    (c) =>
      (typeFilter === "all" || c.type === typeFilter) &&
      (statusFilter === "all" || c.status === statusFilter)
  );

  const summary: { l: string; v: number; pct: number; color: string }[] = [
    { l: "Passed", v: passed, pct: 70, color: "var(--con-ok)" },
    { l: "Warnings", v: warning, pct: 20, color: "var(--con-warn)" },
    { l: "Failed", v: failed, pct: 10, color: "var(--con-err)" },
  ];

  return (
    <AppShell
      eyebrow="DATA QUALITY · MIGRATION READINESS"
      title="Validation"
      metric={`${total} active rules · ${passed} passing · ${failed} failing`}
      description="Schema integrity, row counts, null checks, duplicates, distribution and business-rule validations across all migrations."
      actions={
        <>
          <Button variant="outline"><Download className="h-3.5 w-3.5" /> Export</Button>
          <Button variant="outline"><RefreshCw className="h-3.5 w-3.5" /> Run all</Button>
          <Button variant="primary"><Plus className="h-3.5 w-3.5" /> New rule</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {loadError && <ErrorBanner message={loadError} onDismiss={() => setLoadError("")} />}
        {hasProjects === false && (
          <DemoBanner message="No projects yet. Create one in /projects/new, attach validation rules with POST /projects/{id}/validation-rules, then runs land here." />
        )}
        {hasProjects === true && (
          <DemoBanner message="Pass-rate + distribution panels still show sample data. Per-project drill-in via the projects list populates real rule + run rows." />
        )}
        {/* Top: pass rate hero + distribution */}
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.4fr] gap-4">
          <Card padding="lg">
            <div className="eyebrow">{showRealHero ? "OVERALL PASS RATE" : "OVERALL PASS RATE · SAMPLE"}</div>
            <div className="flex items-baseline gap-3 mt-2">
              <span className="font-mono tabular-nums text-[56px] font-medium tracking-[-0.03em] leading-none">
                {showRealHero ? (realPassRate ?? 0).toFixed(1) : "92.4"}
              </span>
              <span className="text-[28px] text-ink-3 font-normal">%</span>
              {showRealHero ? (
                <span className="ml-auto text-[12px] font-mono text-ink-3">org-wide</span>
              ) : (
                <span className="ml-auto text-[12px] font-mono" style={{ color: "var(--con-ok)" }}>▲ 1.2% vs prev</span>
              )}
            </div>
            <div className="mt-[18px] grid grid-cols-3 gap-[14px]">
              {summary.map((s) => (
                <div key={s.l}>
                  <div className="eyebrow" style={{ fontSize: "9.5px" }}>{s.l}</div>
                  <div
                    className="font-mono tabular-nums text-[22px] font-medium mt-1 tracking-[-0.02em]"
                    style={{ color: s.color }}
                  >
                    {s.v}
                  </div>
                  <div className="mt-1.5 h-[3px] bg-app-2 rounded-sm overflow-hidden">
                    <div className="h-full" style={{ width: `${s.pct}%`, background: s.color }} />
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card
            title="Checks by type"
            eyebrow="LAST RUN WINDOW"
            description="Pass / fail / warning breakdown per validation category"
          >
            {hasProjects === true ? (
              <EmptyState
                title="No category data yet"
                description="Run a validation rule to populate the per-category breakdown."
              />
            ) : (
            <>
            <div className="flex flex-col gap-[9px] py-1">
              {TYPE_BREAKDOWN.map((row) => {
                const tot = row.p + row.w + row.f;
                return (
                  <div
                    key={row.t}
                    className="grid items-center text-[12px] gap-3"
                    style={{ gridTemplateColumns: "130px 1fr 60px" }}
                  >
                    <span className="text-ink-2">{TYPE_LABELS[row.t]}</span>
                    <div className="flex h-2 rounded overflow-hidden border border-hx">
                      <div style={{ width: `${(row.p / tot) * 100}%`, background: "var(--con-ok)" }} />
                      <div style={{ width: `${(row.w / tot) * 100}%`, background: "var(--con-warn)" }} />
                      <div style={{ width: `${(row.f / tot) * 100}%`, background: "var(--con-err)" }} />
                    </div>
                    <span className="font-mono tabular-nums text-[11.5px] text-ink-2 text-right">
                      {row.p} / {tot}
                    </span>
                  </div>
                );
              })}
            </div>
            <div className="mt-3.5 flex gap-4 text-[11px] text-ink-4">
              <span className="inline-flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-sm" style={{ background: "var(--con-ok)" }} /> Passed
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-sm" style={{ background: "var(--con-warn)" }} /> Warning
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-sm" style={{ background: "var(--con-err)" }} /> Failed
              </span>
            </div>
            </>
            )}
          </Card>
        </div>

        {/* Failing checks alert */}
        <div
          className="rounded-[10px] px-[18px] py-3 flex items-center gap-3.5 border"
          style={{ background: "var(--con-err-soft)", borderColor: "#FCA5A5" }}
        >
          <AlertTriangle className="h-4 w-4 flex-shrink-0" style={{ color: "var(--con-err)" }} />
          <div className="flex-1">
            <div className="text-[13px] font-medium" style={{ color: "var(--con-err)" }}>
              3 validation rules are failing across 2 active projects
            </div>
            <div className="text-[11.5px] text-ink-3 mt-0.5">
              Failed checks block downstream phases. Review and re-run, or escalate to the rule owner.
            </div>
          </div>
          <Button variant="outline" size="sm">View failing</Button>
          <Button variant="primary" size="sm">Re-run all</Button>
        </div>

        {/* Filter & table */}
        <Card padding="md" bodyClassName="p-0">
          <div className="px-[18px] py-3.5 flex items-center gap-3 border-b border-hx flex-wrap">
            <Tabs value={typeFilter} onChange={setTypeFilter} tabs={typeTabs} />
            <div className="flex-1" />
            <label className="relative inline-flex items-center" style={{ width: 220 }}>
              <Search className="h-3.5 w-3.5 absolute left-2.5 text-ink-4" />
              <input
                className="w-full h-[30px] rounded-[7px] border border-hx bg-surface pl-8 pr-3 text-[12.5px] focus-ring"
                placeholder="Search checks…"
              />
            </label>
            <Tabs
              value={statusFilter}
              onChange={setStatusFilter}
              tabs={[
                { id: "all", label: "All" },
                { id: "passed", label: "Passed" },
                { id: "warning", label: "Warning" },
                { id: "failed", label: "Failed" },
              ]}
            />
          </div>
          {hasProjects === true ? (
            <EmptyState
              title="No validation rules yet"
              description="Once you attach validation rules to a project, runs and their pass/fail results will land here."
              action={
                <Button variant="primary">
                  <Plus className="h-3.5 w-3.5" /> Create rule
                </Button>
              }
            />
          ) : (
          <table className="w-full border-collapse text-[12.5px]">
            <thead>
              <tr className="bg-surface-hi">
                {["", "Check", "Type", "Source → Target", "Result", "Owner", "Last run", "Status"].map((h, i) => (
                  <th
                    key={i}
                    className="text-left font-medium border-b border-hx font-mono"
                    style={{
                      padding: "9px 14px",
                      fontSize: "10.5px",
                      color: "var(--con-ink-4)",
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                      width: i === 0 ? 4 : undefined,
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((c, idx) => {
                const statusColor =
                  c.status === "passed"
                    ? "var(--con-ok)"
                    : c.status === "warning"
                      ? "var(--con-warn)"
                      : "var(--con-err)";
                return (
                  <tr
                    key={c.id}
                    style={{
                      borderBottom: idx === filtered.length - 1 ? "none" : "1px solid var(--con-line)",
                    }}
                  >
                    <td className="p-0" style={{ width: 4 }}>
                      <div style={{ width: 3, height: 40, background: statusColor }} />
                    </td>
                    <td className="px-3.5 py-[11px]">
                      <div className="flex flex-col gap-px">
                        <span className="font-medium text-ink">{c.name}</span>
                        <span className="font-mono text-[10.5px] text-ink-4">{c.id}</span>
                      </div>
                    </td>
                    <td className="px-3.5 py-[11px]">
                      <Chip tone="default">{TYPE_LABELS[c.type]}</Chip>
                    </td>
                    <td className="px-3.5 py-[11px]">
                      <div className="flex flex-col gap-px font-mono text-[11px] text-ink-3">
                        <span>{c.source}</span>
                        <span>→ {c.target}</span>
                      </div>
                    </td>
                    <td className="px-3.5 py-[11px]">
                      <span
                        className="font-mono tabular-nums text-[12px] font-medium"
                        style={{ color: statusColor }}
                      >
                        {c.rows}
                      </span>
                    </td>
                    <td className="px-3.5 py-[11px]">
                      <div className="flex items-center gap-[7px]">
                        <Avatar name={c.owner} size={18} />
                        <span className="text-[12px]">{c.owner}</span>
                      </div>
                    </td>
                    <td className="px-3.5 py-[11px] text-ink-4 font-mono text-[11.5px]">{c.last}</td>
                    <td className="px-3.5 py-[11px]">
                      <StatusBadge status={c.status} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          )}
        </Card>

        {/* Score trend */}
        <Card
          title="Recon score trend"
          description="Daily reconciliation score across all active projects · last 14 days"
        >
          <AreaChart width={1200} height={200} data={RECON_TREND} />
        </Card>
      </div>
    </AppShell>
  );
}
