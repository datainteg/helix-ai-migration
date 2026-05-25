import {
  Sparkles,
  Cpu,
  ShieldCheck,
  GitCompareArrows,
  TerminalSquare,
  Plug,
  LayoutDashboard,
  ShieldAlert,
  Package,
  type LucideIcon,
} from "lucide-react";

import { FEATURES } from "@/data/site-content";
import { SectionHeader } from "@/components/layout/SectionHeader";

const ICON_MAP: Record<string, LucideIcon> = {
  Sparkles,
  Cpu,
  ShieldCheck,
  GitCompareArrows,
  TerminalSquare,
  Plug,
  LayoutDashboard,
  ShieldAlert,
  Package,
};

export function Features() {
  return (
    <section className="py-16 md:py-24 container-tight section-fade-in">
      <SectionHeader
        eyebrow="What ships today"
        title="Everything you need to run a migration with AI in the loop."
        description="Nine end-to-end capabilities, all open source, all in one self-hosted stack."
      />
      <div className="mt-10 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {FEATURES.map((f, i) => {
          const Icon = ICON_MAP[f.icon] ?? Sparkles;
          const featured = i === 0;
          return (
            <div
              key={f.title}
              className={
                "group rounded-2xl p-6 transition-all hover:-translate-y-0.5 hover:shadow-md " +
                (featured
                  ? "bg-gradient-to-br from-brand-50 via-white to-cyan-50 border border-brand-200 shadow-md"
                  : "bg-surface border border-zinc-200 shadow-soft")
              }
            >
              <div className={"h-10 w-10 rounded-lg grid place-items-center ring-1 " + (featured ? "bg-white text-brand-700 ring-brand-200" : "bg-brand-50 text-brand-600 ring-brand-100")}>
                <Icon className="h-5 w-5" />
              </div>
              <h3 className="mt-4 text-[15px] font-semibold text-ink tracking-tight">{f.title}</h3>
              <p className="mt-2 text-[12.5px] text-ink-3 leading-relaxed">{f.desc}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
