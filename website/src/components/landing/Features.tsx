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
    <section className="py-16 md:py-24 container-tight">
      <SectionHeader
        eyebrow="What ships today"
        title="Everything you need to run a migration with AI in the loop."
        description="Nine end-to-end capabilities, all open source, all in one self-hosted stack."
      />
      <div className="mt-10 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {FEATURES.map((f) => {
          const Icon = ICON_MAP[f.icon] ?? Sparkles;
          return (
            <div
              key={f.title}
              className="group bg-surface border border-zinc-200 rounded-xl shadow-soft p-6 transition-all hover:-translate-y-0.5 hover:shadow-md"
            >
              <div className="h-10 w-10 rounded-lg grid place-items-center bg-brand-50 text-brand-600 ring-1 ring-brand-100">
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
