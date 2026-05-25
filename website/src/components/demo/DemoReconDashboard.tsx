import { Shield, GitCompareArrows, Activity, Clock } from "lucide-react";
import { DemoShell } from "./DemoShell";
import { DEMO_RECON_RUNS } from "@/data/demo-data";

const card = "bg-surface border border-zinc-200 rounded-xl shadow-soft p-5";

function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    pass: "bg-emerald-50 text-emerald-700",
    warn: "bg-amber-50 text-amber-700",
    fail: "bg-rose-50 text-rose-700",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium ${map[status] || "bg-zinc-100 text-ink-3"}`}>
      {status}
    </span>
  );
}

function fmt(n: number) {
  return n.toLocaleString("en-US");
}

export function DemoReconDashboard() {
  const overallParity =
    DEMO_RECON_RUNS.reduce((s, r) => s + r.parity, 0) / DEMO_RECON_RUNS.length;
  const latest = DEMO_RECON_RUNS[0];

  return (
    <DemoShell title="Reconciliation dashboard" description="Source vs target parity, run history, and signed metadata reports.">
      {/* Metric strip */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5">
        <Metric icon={GitCompareArrows} k={String(DEMO_RECON_RUNS.length)} v="Recon runs"   sub="across active projects" />
        <Metric icon={Activity}         k={`${overallParity.toFixed(4)}%`} v="Overall parity" sub="weighted average" />
        <Metric icon={Clock}            k={latest.ranAt}                   v="Latest run"   sub={latest.scope} />
      </div>

      {/* Recon table */}
      <div className={`${card} p-0 overflow-hidden mb-5`}>
        <div className="px-5 py-3 border-b border-zinc-200">
          <h3 className="text-[14px] font-semibold text-ink">Recon runs</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-[12.5px]">
            <thead className="bg-surface-subtle text-ink-3">
              <tr>
                <th className="text-left font-medium px-5 py-2.5">Scope</th>
                <th className="text-right font-medium px-3 py-2.5">Source count</th>
                <th className="text-right font-medium px-3 py-2.5">Target count</th>
                <th className="text-right font-medium px-3 py-2.5">Diff</th>
                <th className="text-right font-medium px-3 py-2.5">Parity</th>
                <th className="text-left font-medium px-3 py-2.5">Status</th>
                <th className="text-left font-medium px-3 py-2.5">Ran at</th>
              </tr>
            </thead>
            <tbody>
              {DEMO_RECON_RUNS.map((r) => (
                <tr key={r.id} className="border-b border-zinc-200 last:border-0 hover:bg-surface-muted">
                  <td className="px-5 py-2.5">
                    <div className="font-mono text-ink font-medium">{r.scope}</div>
                    <div className="text-[11px] text-ink-4 font-mono">{r.id}</div>
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-ink-2">{fmt(r.sourceCount)}</td>
                  <td className="px-3 py-2.5 text-right font-mono text-ink-2">{fmt(r.targetCount)}</td>
                  <td className="px-3 py-2.5 text-right font-mono text-ink-2">{r.diff === 0 ? "—" : fmt(r.diff)}</td>
                  <td className="px-3 py-2.5 text-right font-mono text-ink">{r.parity.toFixed(5)}%</td>
                  <td className="px-3 py-2.5"><StatusPill status={r.status} /></td>
                  <td className="px-3 py-2.5 text-ink-3">{r.ranAt}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Amber callout */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 flex gap-4">
        <div className="h-10 w-10 rounded-md bg-amber-100 text-amber-700 grid place-items-center shrink-0">
          <Shield className="h-5 w-5" />
        </div>
        <div>
          <h4 className="text-[14px] font-semibold text-amber-900">Metadata-only by design</h4>
          <p className="text-[12.5px] text-amber-900/85 mt-1 leading-relaxed">
            Recon stores metadata + summaries only. <strong>No source or target row-level
            data is persisted to Helix.</strong> Counts, checksums, and diff signatures are
            recorded; the underlying rows stay in your warehouse.
          </p>
        </div>
      </div>
    </DemoShell>
  );
}

function Metric({ icon: Icon, k, v, sub }: { icon: any; k: string; v: string; sub?: string }) {
  return (
    <div className={card}>
      <div className="flex items-center gap-3">
        <div className="h-8 w-8 rounded-md bg-brand-50 text-brand-600 grid place-items-center">
          <Icon className="h-4 w-4" />
        </div>
        <div>
          <div className="text-[20px] font-semibold text-ink tracking-tight">{k}</div>
          <div className="text-[12px] text-ink-3">{v}</div>
          {sub && <div className="text-[11px] text-ink-4 mt-0.5">{sub}</div>}
        </div>
      </div>
    </div>
  );
}
