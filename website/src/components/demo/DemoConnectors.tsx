import { useState } from "react";
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
