import { Check } from "lucide-react";

import { ROADMAP } from "@/data/site-content";
import { SectionHeader } from "@/components/layout/SectionHeader";

export function Roadmap() {
  return (
    <section className="py-16 md:py-24 container-tight">
      <SectionHeader
        eyebrow="Roadmap"
        title="What's shipping and what's next."
        description="Tracked in the open. Every quarter, in the repo."
      />
      <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {ROADMAP.map((col, i) => {
          const isNow = i === 0;
          return (
            <div
              key={col.quarter}
              className={
                "rounded-xl shadow-soft p-6 border " +
                (isNow
                  ? "bg-gradient-to-br from-brand-50 to-white border-brand-200 ring-1 ring-brand-100"
                  : "bg-surface border-zinc-200")
              }
            >
              <div
                className="eyebrow"
                style={{ color: isNow ? "#4F46E5" : undefined }}
              >
                {col.quarter}
              </div>
              <ul className="mt-4 space-y-2.5">
                {col.items.map((item) => (
                  <li key={item} className="flex items-start gap-2.5 text-[13px] text-ink-2">
                    <span
                      className={
                        "mt-[3px] h-4 w-4 rounded-full grid place-items-center shrink-0 " +
                        (isNow ? "bg-brand-100 text-brand-600" : "bg-zinc-100 text-ink-4")
                      }
                    >
                      {isNow ? <Check className="h-2.5 w-2.5" /> : <span className="h-1.5 w-1.5 rounded-full bg-current" />}
                    </span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </section>
  );
}
