import { useState } from "react";
import { Plug, Activity, Zap, AlertCircle } from "lucide-react";

import { DemoShell } from "./DemoShell";
import { DEMO_CONNECTORS } from "@/data/demo-data";

const card = "bg-surface border border-zinc-200 rounded-xl shadow-soft p-5";

const CATEGORIES = ["All", "Database", "Warehouse", "Object", "File", "Custom"];

function StatusDot({ status }: { status: string }) {
  const color =
    status === "ok"
      ? "bg-emerald-500"
      : status === "warn"
      ? "bg-amber-500"
      : "bg-rose-500";
  return <span className={`inline-block h-2 w-2 rounded-full ${color} ring-2 ring-surface`} />;
}

function HeroStat({
  icon: Icon,
  label,
  value,
  tint,
}: {
  icon: typeof Plug;
  label: string;
  value: string;
  tint: "brand" | "cyan" | "emerald" | "amber";
}) {
  const bg = {
    brand:   "bg-gradient-to-br from-brand-50 to-cyan-50 ring-brand-100",
    cyan:    "bg-gradient-to-br from-cyan-50 to-emerald-50 ring-cyan-100",
    emerald: "bg-gradient-to-br from-emerald-50 to-cyan-50 ring-emerald-100",
    amber:   "bg-gradient-to-br from-amber-50 to-rose-50 ring-amber-100",
  }[tint];
  const fg = {
    brand:   "bg-brand-600",
    cyan:    "bg-cyan-500",
    emerald: "bg-emerald-500",
    amber:   "bg-amber-500",
  }[tint];
  return (
    <div className={`${bg} ring-1 rounded-2xl p-5 flex items-start justify-between`}>
      <div>
        <div className="eyebrow text-[10px] text-ink-3">{label}</div>
        <div className="text-[22px] font-semibold text-ink tracking-tight mt-1.5 leading-none">{value}</div>
      </div>
      <span className={`h-9 w-9 rounded-lg grid place-items-center text-white ${fg}`}>
        <Icon className="h-4 w-4" />
      </span>
    </div>
  );
}

function CategoryChip({ cat }: { cat: string }) {
  const map: Record<string, string> = {
    database:  "bg-brand-50 text-brand-700",
    warehouse: "bg-cyan-500/10 text-cyan-500",
    object:    "bg-amber-50 text-amber-700",
    file:      "bg-zinc-100 text-ink-3",
    custom:    "bg-emerald-50 text-emerald-700",
  };
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${map[cat] || "bg-zinc-100 text-ink-3"}`}>
      {cat}
    </span>
  );
}

export function DemoConnectors() {
  const [filter, setFilter] = useState("All");
  const filtered = DEMO_CONNECTORS.filter(
    (c) => filter === "All" || c.category === filter.toLowerCase(),
  );

  return (
    <DemoShell title="Connectors" description="Pluggable source and target adapters with encrypted credentials.">
      {/* Hero strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <HeroStat icon={Plug}        label="Total connectors"  value={String(DEMO_CONNECTORS.length)} tint="brand" />
        <HeroStat icon={Activity}    label="Active instances" value="29"                              tint="cyan" />
        <HeroStat icon={Zap}         label="p95 latency"      value="22ms"                            tint="emerald" />
        <HeroStat icon={AlertCircle} label="Failed (24h)"     value="0"                               tint="amber" />
      </div>

      {/* Filter tabs */}
      <div className="mb-5 flex flex-wrap gap-1.5 bg-surface border border-zinc-200 rounded-xl shadow-soft p-1.5 w-fit">
        {CATEGORIES.map((c) => (
          <button
            key={c}
            onClick={() => setFilter(c)}
            className={
              "px-3 py-1.5 rounded-md text-[12.5px] font-medium transition-colors focus-ring " +
              (filter === c
                ? "bg-ink text-white"
                : "text-ink-3 hover:text-ink hover:bg-zinc-100/70")
            }
          >
            {c}
          </button>
        ))}
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {filtered.map((c) => (
          <div key={c.name} className={`${card} transition-all hover:-translate-y-0.5 hover:shadow-md`}>
            <div className="flex items-start gap-3">
              <div className="h-12 w-12 rounded-lg bg-zinc-100 text-ink font-mono text-[18px] font-semibold grid place-items-center shrink-0">
                {c.name[0]}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <h4 className="text-[14px] font-semibold text-ink truncate">{c.name}</h4>
                  <StatusDot status={c.status} />
                </div>
                <div className="mt-1.5">
                  <CategoryChip cat={c.category} />
                </div>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3 text-[12px]">
              <div className="border-t border-zinc-200 pt-3">
                <div className="text-ink-4 text-[11px]">Instances</div>
                <div className="font-mono text-ink font-medium mt-0.5">{c.instances}</div>
              </div>
              <div className="border-t border-zinc-200 pt-3">
                <div className="text-ink-4 text-[11px]">p95</div>
                <div className="font-mono text-ink font-medium mt-0.5">{c.p95}</div>
              </div>
            </div>
            <div className="mt-3 text-[10.5px] text-ink-5 font-mono">by {c.authored}</div>
          </div>
        ))}
      </div>

      {filtered.length === 0 && (
        <div className={`${card} text-center py-12 text-ink-4 text-[13px]`}>
          No connectors in this category yet.
        </div>
      )}
    </DemoShell>
  );
}
