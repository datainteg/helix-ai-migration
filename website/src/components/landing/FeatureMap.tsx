import { ChevronRight } from "lucide-react";

import { FEATURE_MAP_CHAIN, FEATURE_LAYERS } from "@/data/site-content";
import { SectionHeader } from "@/components/layout/SectionHeader";

export function FeatureMap() {
  return (
    <section className="py-16 md:py-24 container-tight">
      <SectionHeader
        eyebrow="Feature map"
        title="One pipeline. Every capability mapped end-to-end."
        description="From requirement intake through to report export — and the four runtime layers that power each step."
      />

      <div className="mt-10">
        <div className="bg-surface border border-zinc-200 rounded-xl shadow-soft p-5 md:p-6">
          <div className="flex flex-wrap items-center gap-y-3">
            {FEATURE_MAP_CHAIN.map((step, i) => (
              <div key={step} className="flex items-center">
                <span
                  className={
                    "inline-flex items-center px-3 h-9 rounded-md text-[12.5px] font-medium whitespace-nowrap " +
                    (i === 0 || i === FEATURE_MAP_CHAIN.length - 1
                      ? "bg-brand-50 text-brand-700 border border-brand-200"
                      : "bg-zinc-50 text-ink-2 border border-zinc-200")
                  }
                >
                  {step}
                </span>
                {i < FEATURE_MAP_CHAIN.length - 1 && (
                  <ChevronRight className="h-4 w-4 mx-1.5 text-ink-5 shrink-0" />
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-10 space-y-4">
        <div className="eyebrow">Powered by four layers</div>
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
                <div className="eyebrow" style={{ color: layer.color }}>Layer</div>
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
