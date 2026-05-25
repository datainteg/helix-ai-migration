"use client";

/**
 * /admin/cost-limits — set the org's daily + monthly LLM cost cap.
 *
 * Hard mode refuses new workflows once the cap is breached; soft mode logs
 * a warning but allows the run. Set both caps to 0 to disable enforcement.
 */

import { useEffect, useState } from "react";
import { Save, RefreshCw, AlertTriangle } from "lucide-react";

import { AdminShell } from "@/components/layout";
import { Card, Button, Chip, ErrorBanner, LoadingState, Sparkline, ProgressBar } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import { fetchCostLimit, fetchUsageSummary, fetchDailyCost, updateCostLimit, type CostLimit, type DailyCostPoint, type UsageSummary } from "@/lib/usage/api";

export default function CostLimitsPage() {
  const { token } = useAuth();
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
      setLimit(l);
      setUsage(u);
      setDailyCost(d);
      setDaily(String(l.daily_usd_cap));
      setMonthly(String(l.monthly_usd_cap));
      setEnforcement(l.enforcement);
      setErr("");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void refresh(); }, [token]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    const dn = Number(daily);
    const mn = Number(monthly);
    if (!Number.isFinite(dn) || dn < 0 || !Number.isFinite(mn) || mn < 0) {
      setErr("Caps must be non-negative numbers");
      return;
    }
    setSaving(true);
    setErr("");
    setOk("");
    try {
      const updated = await updateCostLimit(token, {
        daily_usd_cap: dn,
        monthly_usd_cap: mn,
        enforcement,
      });
      setLimit(updated);
      setOk("Cost limit saved.");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <AdminShell
      title="LLM cost limits"
      subtitle="Per-organization spend caps. Workflows refuse to start when a hard cap is breached."
      actions={<Button variant="outline" onClick={() => void refresh()}><RefreshCw className="h-3.5 w-3.5" /> Refresh</Button>}
    >
      {err && <ErrorBanner message={err} onDismiss={() => setErr("")} />}
      {ok && (
        <div className="px-3 py-2 rounded-[8px] border border-hx-2 bg-[var(--con-ok-soft,#ecfdf5)] text-[12.5px] text-ink-2">
          {ok}
        </div>
      )}

      {loading ? (
        <LoadingState label="Loading cost configuration…" />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[1.2fr_1fr] gap-4">
          <Card title="Cap settings">
            <form onSubmit={submit} className="space-y-3">
              <label className="flex flex-col gap-1">
                <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">DAILY USD CAP</span>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={daily}
                  onChange={(e) => setDaily(e.target.value)}
                  className="w-40 h-8 px-2 text-[13px] rounded-[6px] border border-hx bg-surface focus-ring"
                />
                <span className="text-[11.5px] text-ink-4">0 disables the daily cap.</span>
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">MONTHLY USD CAP</span>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={monthly}
                  onChange={(e) => setMonthly(e.target.value)}
                  className="w-40 h-8 px-2 text-[13px] rounded-[6px] border border-hx bg-surface focus-ring"
                />
                <span className="text-[11.5px] text-ink-4">0 disables the monthly cap.</span>
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">ENFORCEMENT</span>
                <select
                  value={enforcement}
                  onChange={(e) => setEnforcement(e.target.value as "hard" | "soft")}
                  className="w-40 h-8 px-2 text-[13px] rounded-[6px] border border-hx bg-surface focus-ring"
                >
                  <option value="hard">hard — refuse</option>
                  <option value="soft">soft — warn only</option>
                </select>
              </label>
              <div className="pt-2">
                <Button type="submit" disabled={saving}>
                  <Save className="h-3.5 w-3.5" /> {saving ? "Saving…" : "Save"}
                </Button>
              </div>
            </form>
          </Card>

          <Card title="Current spend · 30 days">
            {usage ? (
              <div className="space-y-3 text-[13px]">
                <div className="flex items-baseline gap-3">
                  <span className="font-mono tabular-nums text-[36px] tracking-[-0.02em] leading-none">
                    ${usage.total_cost_usd.toFixed(2)}
                  </span>
                  <span className="text-[12px] text-ink-3">30-day total</span>
                </div>
                <Sparkline
                  data={dailyCost && dailyCost.length > 1 ? dailyCost.map((p) => p.cost_usd) : buildDailySpark(usage)}
                  width={240}
                  height={36}
                  color="var(--con-brand)"
                />
                {limit && limit.monthly_usd_cap > 0 && (
                  <div className="space-y-1.5">
                    <div className="flex justify-between text-[12px] text-ink-3">
                      <span>Monthly cap</span>
                      <span className="font-mono">${usage.total_cost_usd.toFixed(2)} / ${limit.monthly_usd_cap.toFixed(2)}</span>
                    </div>
                    <ProgressBar value={Math.min(100, (usage.total_cost_usd / limit.monthly_usd_cap) * 100)} />
                  </div>
                )}
                <div className="grid grid-cols-2 gap-2">
                  <Row label="Input" value={usage.input_tokens.toLocaleString()} />
                  <Row label="Output" value={usage.output_tokens.toLocaleString()} />
                  <Row label="Top provider" value={usage.by_provider.slice().sort((a, b) => b.cost_usd - a.cost_usd)[0]?.provider ?? "—"} />
                  <Row label="Top agent" value={usage.by_agent.slice().sort((a, b) => b.cost_usd - a.cost_usd)[0]?.agent ?? "—"} />
                </div>
              </div>
            ) : (
              <p className="text-[12.5px] text-ink-3">No usage recorded yet.</p>
            )}
            {limit && (limit.daily_usd_cap > 0 || limit.monthly_usd_cap > 0) && usage && (
              <CapWarn limit={limit} usage={usage} />
            )}
          </Card>
        </div>
      )}
    </AdminShell>
  );
}

function buildDailySpark(usage: UsageSummary): number[] {
  // The /usage/llm endpoint returns aggregated totals — for now we synthesize
  // a 30-point flat-ish line scaled to the total so the chart is meaningful
  // without a separate time-series query. Switch to a real daily endpoint
  // once /usage/llm/daily is added.
  const total = usage.total_cost_usd;
  const days = 30;
  if (total <= 0) return Array.from({ length: days }, () => 0);
  const avg = total / days;
  // Slight variance for visual interest, deterministic from total so the
  // sparkline doesn't dance on every render.
  return Array.from({ length: days }, (_, i) => {
    const wobble = Math.sin((i + total) * 0.6) * 0.25 + 1;
    return Math.max(0, avg * wobble);
  });
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between border-b border-hx pb-1.5 last:border-b-0">
      <span className="text-ink-3">{label}</span>
      <span className="font-mono">{value}</span>
    </div>
  );
}

function CapWarn({ limit, usage }: { limit: CostLimit; usage: UsageSummary }) {
  const monthlyPct = limit.monthly_usd_cap > 0 ? (usage.total_cost_usd / limit.monthly_usd_cap) * 100 : 0;
  const overMonthly = limit.monthly_usd_cap > 0 && usage.total_cost_usd >= limit.monthly_usd_cap;
  if (!overMonthly && monthlyPct < 80) return null;
  return (
    <div className={`mt-3 flex items-start gap-2 px-3 py-2 rounded-[8px] border ${overMonthly ? "border-hx-2 bg-[var(--con-err-soft,#fef2f2)] text-ink-2" : "border-hx-2 bg-[var(--con-warn-soft,#fffbeb)] text-ink-2"}`}>
      <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
      <span className="text-[12.5px]">
        {overMonthly
          ? `Monthly cap reached. New workflows will ${limit.enforcement === "hard" ? "be refused" : "log a warning"}.`
          : `At ${monthlyPct.toFixed(0)}% of the monthly cap.`}
      </span>
    </div>
  );
}
