"use client";

import { Download, Play, AlertTriangle } from "lucide-react";
import { AppShell } from "@/components/layout";
import {
  Card,
  Button,
  MetricCard,
  Donut,
  StatusBadge,
  DemoBanner,
} from "@/components/ui";
import { formatDate, formatTime, formatNumber } from "@/lib/utils";

interface ReconRun {
  id: string;
  table: string;
  source: string;
  target: string;
  sourceCount: number;
  targetCount: number;
  mismatched: number;
  score: number;
  status: string;
  startedAt: string;
}

export default function ReconciliationPage() {
  // TODO: hydrate via API once recon endpoint is wired.
  const reconRuns: ReconRun[] = [];
  const mismatchCategories: { label: string; value: number; color: string }[] = [];

  return (
    <AppShell
      title="Reconciliation Center"
      subtitle="Compare source and target outcomes with row-level reconciliation insights and anomaly analysis."
      crumbs={[{ label: "Reconciliation" }]}
      actions={
        <>
          <Button variant="outline"><Download className="h-4 w-4" /> Export Report</Button>
          <Button
            disabled
            title="Reconciliation API not yet enabled"
          >
            <Play className="h-4 w-4" /> Run Reconciliation
          </Button>
        </>
      }
    >
      <DemoBanner message="Reconciliation API not yet enabled — see Settings → Reconciliation. All numbers below are sample placeholders." />
      <div className="rounded-xl bg-warn-soft border border-hx px-4 py-2.5 mt-4 mb-5 text-[12.5px] text-warn flex items-start gap-2">
        <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
        <span>
          <strong>Metadata-only mode:</strong> row counts and aggregates are reconciled — source rows are not copied.
          Enable full reconciliation per project for row-by-row matching.
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <MetricCard label="Reconciliation Score" value="0%" sparkColor="#10B981" />
        <MetricCard label="Matched Records" value="0" sparkColor="#6366F1" />
        <MetricCard label="Mismatched" value="0%" sparkColor="#F59E0B" />
        <MetricCard label="Missing" value="0" sparkColor="#DC2626" />
        <MetricCard label="Average Row Score" value="0%" sparkColor="#06B6D4" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-6">
        <Card className="lg:col-span-2" title="Reconciliation Trend" description="Mismatch counts over time">
          <p className="text-[12.5px] text-ink-4 py-12 text-center">No trend data yet.</p>
        </Card>

        <Card title="Mismatch Categories" description="0 total mismatches">
          {mismatchCategories.length > 0 ? (
            <Donut data={mismatchCategories} size={200} thickness={28} centerLabel="0" centerSub="Mismatches" />
          ) : (
            <p className="text-[12.5px] text-ink-4 py-12 text-center">No mismatch data yet.</p>
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-4">
        <Card title="Top Anomalies" description="Highest impact mismatch sources">
          <p className="text-[12.5px] text-ink-4 py-6 text-center">No anomalies yet.</p>
        </Card>

        <Card className="lg:col-span-2" title="Reconciliation Jobs" description="Run history across tables" padding="none">
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead className="bg-app-2 text-[11.5px] uppercase tracking-wider text-ink-4">
                <tr>
                  <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Table</th>
                  <th className="px-4 py-2.5 text-right font-medium border-b border-hx">Source</th>
                  <th className="px-4 py-2.5 text-right font-medium border-b border-hx">Target</th>
                  <th className="px-4 py-2.5 text-right font-medium border-b border-hx">Mismatches</th>
                  <th className="px-4 py-2.5 text-right font-medium border-b border-hx">Score</th>
                  <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Status</th>
                  <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Started</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hx">
                {reconRuns.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-[12.5px] text-ink-4">No reconciliation runs yet.</td>
                  </tr>
                ) : (
                  reconRuns.map((r) => (
                    <tr key={r.id} className="hover:bg-surface-hi">
                      <td className="px-4 py-3 font-medium text-ink font-mono text-[12.5px]">{r.table}</td>
                      <td className="px-4 py-3 text-right font-mono text-[12px] text-ink-2">{formatNumber(r.sourceCount)}</td>
                      <td className="px-4 py-3 text-right font-mono text-[12px] text-ink-2">{formatNumber(r.targetCount)}</td>
                      <td className="px-4 py-3 text-right font-mono text-[12px] text-warn">{r.mismatched}</td>
                      <td className="px-4 py-3 text-right font-mono text-[12px] font-semibold text-ok">{r.score.toFixed(2)}%</td>
                      <td className="px-4 py-3"><StatusBadge status={r.status} /></td>
                      <td className="px-4 py-3 text-ink-3 text-[12px]">{formatDate(r.startedAt)} · {formatTime(r.startedAt)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
