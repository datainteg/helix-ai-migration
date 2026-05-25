import { FEATURE_LAYERS } from "@/data/site-content";
import { SectionHeader } from "@/components/layout/SectionHeader";

export function Architecture() {
  return (
    <section className="py-16 md:py-24 container-tight">
      <SectionHeader
        eyebrow="Architecture"
        title="Four layers, one self-hosted stack."
        description="Each layer is a clear boundary — operators, developers, data, and governance — wired through one API."
      />
      <div className="mt-10 space-y-4">
        {FEATURE_LAYERS.map((layer) => (
          <div
            key={layer.name}
            className="bg-surface border border-zinc-200 rounded-xl shadow-soft overflow-hidden"
          >
            <div className="flex flex-col md:flex-row md:items-stretch">
              <div
                className="md:w-[260px] shrink-0 px-6 py-5 flex flex-col justify-center border-b md:border-b-0 md:border-r border-zinc-200"
                style={{
                  background: `linear-gradient(135deg, ${layer.color}10, ${layer.color}05)`,
                  borderLeft: `3px solid ${layer.color}`,
                }}
              >
                <div
                  className="eyebrow"
                  style={{ color: layer.color }}
                >
                  Layer
                </div>
                <div className="mt-1 text-[16px] font-semibold text-ink tracking-tight">{layer.name}</div>
              </div>
              <div className="flex-1 px-6 py-5 flex flex-wrap items-center gap-2.5">
                {layer.items.map((item) => (
                  <span
                    key={item}
                    className="inline-flex items-center px-3 h-8 rounded-md bg-zinc-50 border border-zinc-200 text-[12.5px] font-medium text-ink-2"
                    style={{ borderColor: `${layer.color}33` }}
                  >
                    {item}
                  </span>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
