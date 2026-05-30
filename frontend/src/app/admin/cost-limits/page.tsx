"use client";

/**
 * /admin/cost-limits — LLM spend governance.
 *
 * Tabs:
 *  - Overview     org-wide caps + spend trend + run-rate forecast + provider/agent bars
 *  - Per-agent    per-agent budgets (BudgetsTab scope="agent")
 *  - Per-project  per-project budgets (BudgetsTab scope="project")
 *  - Usage        per-agent token/cost breakdown + CSV export
 *
 * Every number is from a real endpoint (/usage/llm, /usage/llm/daily,
 * /usage/cost-limit, /usage/budgets). No fabricated data — clean empty states.
 */

import { useEffect, useState } from "react";
import { Save, RefreshCw, AlertTriangle, ShieldCheck, Info, Download, TrendingUp } from "lucide-react";

import { AppShell } from "@/components/layout";
import { Card, Button, Chip, ErrorBanner, LoadingState, Sparkline, ProgressBar, EmptyState, Tabs, Donut, MetricCell, Table, THead, TBody, TR, TH, TD } from "@/components/ui";
import { AgentIcon } from "@/components/icons";
import { useAuth } from "@/lib/auth-context";
import {
  fetchCostLimit, fetchUsageSummary, fetchDailyCost, updateCostLimit, downloadUsageCsv,
  type CostLimit, type DailyCostPoint, type UsageSummary,
} from "@/lib/usage/api";
import { BudgetsTab } from "./BudgetsTab";

const fmtUsd = (v: number) => (v >= 1000 ? `$${(v / 1000).toFixed(2)}k` : `$${v.toFixed(2)}`);
const BAR_COLORS = ["#4F46E5", "#06B6D4", "#7C3AED", "#0EA5E9", "#DB2777", "#16A34A", "#EA580C", "#64748B"];

type TabId = "overview" | "agents" | "projects" | "usage";

export default function CostLimitsPage() {
  const { token } = useAuth();
  const [tab, setTab] = useState<TabId>("overview");
  const [loading, setLoading] = useState(true);
  const [limit, setLimit] = useState<CostLimit | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [dailyCost, setDailyCost] = useState<DailyCostPoint[] | null>(null);
  const [daily, setDaily] = useState("0");
  const [monthly, setMonthly] = useState("0");
  const [enforcement, setEnforcement] = useState<"hard" | "soft">("hard");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");

  const refresh = async () => {
    if (!token) return;
    setLoading(true);
    try {
      const [l, u, d] = await Promise.all([
        fetchCostLimit(token),
        fetchUsageSummary(token, 30),
        fetchDailyCost(token, 30).catch(() => null),
      ]);
      setLimit(l); setUsage(u); setDailyCost(d);
      setDaily(String(l.daily_usd_cap)); setMonthly(String(l.monthly_usd_cap)); setEnforcement(l.enforcement);
      setErr("");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void refresh(); }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    const dn = Number(daily), mn = Number(monthly);
    if (!Number.isFinite(dn) || dn < 0 || !Number.isFinite(mn) || mn < 0) { setErr("Caps must be non-negative numbers."); return; }
    setSaving(true); setErr(""); setOk("");
    try {
      const updated = await updateCostLimit(token, { daily_usd_cap: dn, monthly_usd_cap: mn, enforcement });
      setLimit(updated); setOk("Cost limits saved.");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  };

  const spend = usage?.total_cost_usd ?? 0;
  const monthlyCap = limit?.monthly_usd_cap ?? 0;
  const monthlyPct = monthlyCap > 0 ? Math.min(100, (spend / monthlyCap) * 100) : 0;
  const hasRealSeries = !!dailyCost && dailyCost.length > 1;

  // Run-rate forecast: project month-end spend from the daily series.
  const forecast = (() => {
    if (!dailyCost || dailyCost.length === 0) return null;
    const now = new Date();
    const dayOfMonth = now.getUTCDate();
    const daysInMonth = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 0)).getUTCDate();
    // Sum spend within the current calendar month from the daily points.
    const monthKey = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, "0")}`;
    const mtd = dailyCost.filter((p) => p.date.startsWith(monthKey)).reduce((s, p) => s + p.cost_usd, 0);
    if (mtd <= 0 || dayOfMonth === 0) return null;
    const projected = (mtd / dayOfMonth) * daysInMonth;
    return { mtd, projected, daysInMonth, dayOfMonth };
  })();

  const TABS = [
    { id: "overview", label: "Overview" },
    { id: "agents", label: "Per-agent budgets" },
    { id: "projects", label: "Per-project budgets" },
    { id: "usage", label: "Usage" },
  ];

  return (
    <AppShell
      title="Cost Limits"
      subtitle="Govern LLM spend: org-wide caps, per-agent and per-project budgets, and usage analytics. Hard caps refuse new workflows; soft caps warn only."
      crumbs={["Cost Limits"]}
      actions={<Button variant="outline" onClick={() => void refresh()}><RefreshCw className="h-3.5 w-3.5" /> Refresh</Button>}
    >
      {err && <ErrorBanner message={err} onDismiss={() => setErr("")} />}
      {ok && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-[8px] border border-hx-2 bg-[var(--con-ok-soft,#ecfdf5)] text-[12.5px] text-ink-2">
          <ShieldCheck className="h-4 w-4 text-[var(--con-ok)]" /> {ok}
        </div>
      )}

      <Tabs tabs={TABS} value={tab} onChange={(v) => setTab(v as TabId)} variant="pill" />

      {loading ? (
        <LoadingState label="Loading cost configuration…" />
      ) : tab === "overview" ? (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 bg-surface border border-hx rounded-[10px] divide-y sm:divide-y-0 sm:divide-x divide-[var(--con-line)] overflow-hidden">
            <MetricCell big label="SPEND · 30 DAYS" value={fmtUsd(spend)} hint={`${((usage?.input_tokens ?? 0) + (usage?.output_tokens ?? 0)).toLocaleString()} tokens`} />
            <MetricCell big label="MONTHLY CAP" value={monthlyCap > 0 ? fmtUsd(monthlyCap) : "Off"} hint={monthlyCap > 0 ? `${monthlyPct.toFixed(0)}% used` : "no monthly cap set"} accent={monthlyCap > 0 && monthlyPct >= 100 ? "var(--con-err)" : monthlyCap > 0 && monthlyPct >= 80 ? "var(--con-warn)" : undefined} />
            <MetricCell big label="ENFORCEMENT" value={(limit?.enforcement ?? enforcement) === "hard" ? "Hard" : "Soft"} hint={(limit?.enforcement ?? enforcement) === "hard" ? "refuses over-cap runs" : "warns only"} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.1fr] gap-4">
            <Card title="Org spend caps" description="Daily and monthly ceilings, and how Helix reacts when they're hit.">
              <form onSubmit={submit} className="space-y-4">
                <CapField label="Daily USD cap" value={daily} onChange={setDaily} help="Resets each day. 0 disables the daily cap." />
                <CapField label="Monthly USD cap" value={monthly} onChange={setMonthly} help="Resets each calendar month. 0 disables the monthly cap." />
                <label className="flex flex-col gap-1.5">
                  <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">Enforcement</span>
                  <select value={enforcement} onChange={(e) => setEnforcement(e.target.value as "hard" | "soft")} className="w-full sm:w-56 h-9 px-2.5 text-[13px] rounded-[8px] border border-hx bg-surface focus-ring">
                    <option value="hard">Hard — refuse new workflows over the cap</option>
                    <option value="soft">Soft — allow, but log a warning</option>
                  </select>
                </label>
                <div className="flex items-start gap-2 text-[11.5px] text-ink-4">
                  <Info className="h-3.5 w-3.5 mt-0.5 flex-shrink-0" />
                  <span>Org caps apply to all LLM calls — BMAD agents, migrations, and the Ask Helix Help agent. Set per-agent/project limits in the other tabs.</span>
                </div>
                <div className="pt-1"><Button type="submit" disabled={saving}><Save className="h-3.5 w-3.5" /> {saving ? "Saving…" : "Save caps"}</Button></div>
              </form>
            </Card>

            <Card title="Spend trend" description="LLM cost over the last 30 days">
              {spend <= 0 ? (
                <EmptyState title="No spend recorded yet" description="Once agents and migrations make LLM calls, cost will be tracked here." />
              ) : (
                <div className="space-y-4">
                  <div className="flex items-baseline gap-3">
                    <span className="font-mono tabular-nums text-[34px] tracking-[-0.02em] leading-none">{fmtUsd(spend)}</span>
                    <span className="text-[12px] text-ink-3">30-day total</span>
                  </div>
                  {hasRealSeries ? (
                    <Sparkline data={dailyCost!.map((p) => p.cost_usd)} width={320} height={40} color="var(--con-brand)" />
                  ) : (
                    <p className="text-[11.5px] text-ink-4">Per-day breakdown isn’t available yet — showing the 30-day total above.</p>
                  )}
                  {monthlyCap > 0 && (
                    <div className="space-y-1.5">
                      <div className="flex justify-between text-[12px] text-ink-3"><span>Monthly cap usage</span><span className="font-mono">{fmtUsd(spend)} / {fmtUsd(monthlyCap)}</span></div>
                      <ProgressBar value={monthlyPct} />
                    </div>
                  )}
                  {forecast && (
                    <div className="flex items-start gap-2 px-3 py-2 rounded-[8px] border border-hx-2 bg-surface-hi text-[12px] text-ink-2">
                      <TrendingUp className="h-4 w-4 mt-0.5 flex-shrink-0 text-[var(--con-brand)]" />
                      <span>
                        Projected month-end spend <span className="font-mono font-medium">{fmtUsd(forecast.projected)}</span>{" "}
                        (run-rate from {fmtUsd(forecast.mtd)} over {forecast.dayOfMonth}/{forecast.daysInMonth} days)
                        {monthlyCap > 0 && forecast.projected > monthlyCap && <span className="text-[var(--con-err)] font-medium"> — over cap</span>}.
                      </span>
                    </div>
                  )}
                  {limit && (limit.daily_usd_cap > 0 || limit.monthly_usd_cap > 0) && usage && <CapWarn limit={limit} usage={usage} />}
                </div>
              )}
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card title="Spend by provider" description="Where the cost is going (30 days)">
              <Breakdown rows={(usage?.by_provider ?? []).map((r) => ({ label: r.provider, cost: r.cost_usd }))} total={spend} />
            </Card>
            <Card title="Spend by agent" description="Which agents cost the most (30 days)">
              <Breakdown rows={(usage?.by_agent ?? []).map((r) => ({ label: r.agent, cost: r.cost_usd }))} total={spend} />
            </Card>
          </div>
        </>
      ) : tab === "agents" ? (
        <BudgetsTab scope="agent" usage={usage} token={token} />
      ) : tab === "projects" ? (
        <BudgetsTab scope="project" usage={usage} token={token} />
      ) : (
        <UsageTab usage={usage} />
      )}
    </AppShell>
  );
}

function UsageTab({ usage }: { usage: UsageSummary | null }) {
  const spend = usage?.total_cost_usd ?? 0;
  const agents = (usage?.by_agent ?? []).slice().sort((a, b) => b.cost_usd - a.cost_usd);
  const donut = agents.slice(0, 8).map((a, i) => ({ label: a.agent, value: a.cost_usd, color: BAR_COLORS[i % BAR_COLORS.length] }));

  return (
    <>
      <Card
        title="Per-agent usage"
        description="Real token + cost consumption over the last 30 days"
        actions={<Button size="sm" variant="outline" onClick={() => void downloadUsageCsv(30)}><Download className="h-3.5 w-3.5" /> Export CSV</Button>}
      >
        {spend <= 0 ? (
          <EmptyState title="No usage yet" description="Per-agent token and cost data appears here after the first LLM calls." />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-5 items-start">
            <div className="grid place-items-center">
              <Donut data={donut} size={180} thickness={22} centerLabel="30d cost" centerValue={`$${spend.toFixed(2)}`} />
            </div>
            <Table>
              <THead>
                <TR hover={false}><TH>Agent</TH><TH>Cost</TH><TH>Input tok</TH><TH>Output tok</TH><TH>Calls</TH></TR>
              </THead>
              <TBody>
                {agents.map((a) => (
                  <TR key={a.agent}>
                    <TD><div className="flex items-center gap-2"><AgentIcon name={a.agent} size={20} /><span className="font-medium text-ink truncate max-w-[200px]" title={a.agent}>{a.agent}</span></div></TD>
                    <TD className="font-mono tabular-nums">${a.cost_usd.toFixed(4)}</TD>
                    <TD className="font-mono tabular-nums text-ink-3">{a.input_tokens.toLocaleString()}</TD>
                    <TD className="font-mono tabular-nums text-ink-3">{a.output_tokens.toLocaleString()}</TD>
                    <TD className="font-mono tabular-nums text-ink-3">{a.call_count}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </div>
        )}
      </Card>
    </>
  );
}

function CapField({ label, value, onChange, help }: { label: string; value: string; onChange: (v: string) => void; help: string }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">{label}</span>
      <div className="relative w-full sm:w-56">
        <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-4 text-[13px]">$</span>
        <input type="number" step="0.01" min="0" value={value} onChange={(e) => onChange(e.target.value)} className="w-full h-9 pl-6 pr-2.5 text-[13px] rounded-[8px] border border-hx bg-surface focus-ring font-mono" />
      </div>
      <span className="text-[11.5px] text-ink-4">{help}</span>
    </label>
  );
}

function Breakdown({ rows, total }: { rows: { label: string; cost: number }[]; total: number }) {
  const sorted = rows.filter((r) => r.cost > 0).sort((a, b) => b.cost - a.cost);
  if (sorted.length === 0) return <p className="text-[12.5px] text-ink-4">No spend recorded in this window.</p>;
  const max = sorted[0].cost || 1;
  return (
    <div className="space-y-2.5">
      {sorted.map((r) => {
        const pctOfTotal = total > 0 ? (r.cost / total) * 100 : 0;
        return (
          <div key={r.label} className="space-y-1">
            <div className="flex justify-between text-[12.5px]">
              <span className="text-ink-2 truncate">{r.label}</span>
              <span className="font-mono text-ink-3 tabular-nums">{fmtUsd(r.cost)} <span className="text-ink-4">· {pctOfTotal.toFixed(0)}%</span></span>
            </div>
            <div className="h-1.5 rounded-full bg-app-2 overflow-hidden"><div className="h-full rounded-full" style={{ width: `${(r.cost / max) * 100}%`, background: "var(--con-brand)" }} /></div>
          </div>
        );
      })}
    </div>
  );
}

function CapWarn({ limit, usage }: { limit: CostLimit; usage: UsageSummary }) {
  const monthlyPct = limit.monthly_usd_cap > 0 ? (usage.total_cost_usd / limit.monthly_usd_cap) * 100 : 0;
  const overMonthly = limit.monthly_usd_cap > 0 && usage.total_cost_usd >= limit.monthly_usd_cap;
  if (!overMonthly && monthlyPct < 80) return null;
  return (
    <div className={`flex items-start gap-2 px-3 py-2 rounded-[8px] border border-hx-2 ${overMonthly ? "bg-[var(--con-err-soft,#fef2f2)]" : "bg-[var(--con-warn-soft,#fffbeb)]"} text-ink-2`}>
      <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
      <span className="text-[12.5px]">
        {overMonthly ? `Monthly cap reached. New workflows will ${limit.enforcement === "hard" ? "be refused" : "log a warning"} until the cap resets.` : `You're at ${monthlyPct.toFixed(0)}% of the monthly cap.`}
      </span>
    </div>
  );
}
