import { ShieldCheck, ListChecks, Percent } from "lucide-react";
import { DemoShell } from "./DemoShell";
import { DEMO_VALIDATIONS } from "@/data/demo-data";

const card = "bg-surface border border-zinc-200 rounded-xl shadow-soft p-5";

function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    pass: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    warn: "bg-amber-50 text-amber-700 ring-amber-200",
    fail: "bg-rose-50 text-rose-700 ring-rose-200",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium ring-1 ${map[status] || "bg-zinc-100 text-ink-3 ring-zinc-200"}`}>
      {status}
    </span>
  );
}

function CoverageBar({ pct }: { pct: number }) {
  const color = pct >= 99 ? "bg-emerald-500" : pct >= 90 ? "bg-amber-500" : "bg-rose-500";
  return (
    <div className="flex items-center gap-2 min-w-[100px]">
      <div className="flex-1 h-1.5 rounded-full bg-zinc-100 overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[11.5px] font-mono text-ink-3 w-9 text-right">{pct}%</span>
    </div>
  );
}

const CHECKS = [
  { title: "Row count parity",   desc: "Source vs target totals must match within tolerance." },
  { title: "Null value checks",  desc: "Required columns must be non-null in target rows." },
  { title: "Duplicate detection", desc: "Primary keys and unique indexes verified." },
  { title: "Schema parity",      desc: "Column names, types, and constraints align." },
  { title: "Business rules",     desc: "Domain invariants — AR ≤ Revenue, dates bounded, etc." },
];

export function DemoValidationCenter() {
  const passCount = DEMO_VALIDATIONS.filter((v) => v.status === "pass").length;
  const passRate = Math.round((passCount / DEMO_VALIDATIONS.length) * 100);
  const avgCoverage = Math.round(
    DEMO_VALIDATIONS.reduce((s, v) => s + v.coverage, 0) / DEMO_VALIDATIONS.length,
  );

  return (
    <DemoShell title="Validation center" description="Rules, runs, and coverage in one place.">
      {/* Metric strip */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5">
        <Metric icon={ListChecks}  k={String(DEMO_VALIDATIONS.length)} v="Total rules"  />
        <Metric icon={ShieldCheck} k={`${passRate}%`}                   v="Pass rate"    />
        <Metric icon={Percent}     k={`${avgCoverage}%`}                v="Avg coverage" />
      </div>

      {/* Table */}
      <div className={`${card} p-0 overflow-hidden mb-5`}>
        <div className="px-5 py-3 border-b border-zinc-200">
          <h3 className="text-[14px] font-semibold text-ink">Validation rules</h3>
        </div>
        <div className="overflow-x-auto scroll-fade-x">
          <table className="w-full text-[12.5px]">
            <thead className="bg-surface-subtle text-ink-3">
              <tr>
                <th className="text-left font-medium px-5 py-2.5">Rule</th>
                <th className="text-left font-medium px-3 py-2.5">Scope</th>
                <th className="text-left font-medium px-3 py-2.5">Status</th>
                <th className="text-left font-medium px-3 py-2.5">Last run</th>
                <th className="text-left font-medium px-3 py-2.5">Coverage</th>
              </tr>
            </thead>
            <tbody>
              {DEMO_VALIDATIONS.map((v) => (
                <tr key={v.id} className="border-b border-zinc-200 last:border-0 hover:bg-surface-muted">
                  <td className="px-5 py-2.5">
                    <div className="font-medium text-ink">{v.rule}</div>
                    <div className="text-[11px] text-ink-4 font-mono">{v.id}</div>
                  </td>
                  <td className="px-3 py-2.5 font-mono text-ink-2">{v.scope}</td>
                  <td className="px-3 py-2.5"><StatusPill status={v.status} /></td>
                  <td className="px-3 py-2.5 text-ink-3">{v.last}</td>
                  <td className="px-3 py-2.5"><CoverageBar pct={v.coverage} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* What gets checked */}
      <div className={card}>
        <h3 className="text-[14px] font-semibold text-ink mb-3">What gets checked</h3>
        <p className="text-[12.5px] text-ink-3 mb-4 leading-relaxed">
          Five rule families run after every migration step. Failed checks
          block promotion to recon; warnings surface for operator review.
        </p>
        <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {CHECKS.map((c) => (
            <li key={c.title} className="flex gap-3">
              <div className="h-7 w-7 rounded-md bg-brand-50 text-brand-600 grid place-items-center shrink-0">
                <ShieldCheck className="h-3.5 w-3.5" />
              </div>
              <div>
                <div className="text-[13px] font-medium text-ink">{c.title}</div>
                <div className="text-[12px] text-ink-3 mt-0.5">{c.desc}</div>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </DemoShell>
  );
}

function Metric({ icon: Icon, k, v }: { icon: any; k: string; v: string }) {
  return (
    <div className={card}>
      <div className="flex items-center gap-3">
        <div className="h-8 w-8 rounded-md bg-brand-50 text-brand-600 grid place-items-center">
          <Icon className="h-4 w-4" />
        </div>
        <div>
          <div className="text-[20px] font-semibold text-ink tracking-tight">{k}</div>
          <div className="text-[12px] text-ink-3">{v}</div>
        </div>
      </div>
    </div>
  );
}
