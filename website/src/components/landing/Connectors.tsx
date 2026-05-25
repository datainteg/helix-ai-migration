import { CONNECTORS } from "@/data/site-content";
import { SectionHeader } from "@/components/layout/SectionHeader";

export function Connectors() {
  return (
    <section className="py-16 md:py-24 container-tight">
      <SectionHeader
        eyebrow="Connectors"
        title="Talk to your databases, warehouses, and lakehouses on day one."
        description="Seven sources out of the box plus a small Python adapter interface — add your own warehouse, legacy ETL, or SaaS in under a day."
      />
      <div className="mt-10 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {CONNECTORS.map((c) => (
          <div
            key={c.name}
            className="bg-surface border border-zinc-200 rounded-xl shadow-soft p-4 flex flex-col items-start gap-3 transition-transform hover:scale-[1.03] hover:shadow-md"
          >
            <div
              className="h-10 w-10 rounded-md grid place-items-center text-white text-[15px] font-semibold"
              style={{ background: c.color }}
            >
              {c.letter}
            </div>
            <div className="min-w-0">
              <div className="text-[13px] font-semibold text-ink truncate">{c.name}</div>
              <span className="mt-1 inline-flex items-center px-2 h-5 rounded text-[10.5px] font-medium text-ink-4 bg-zinc-100 capitalize">
                {c.category}
              </span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
