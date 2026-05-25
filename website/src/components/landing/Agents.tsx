import { ChevronRight } from "lucide-react";

import { AGENTS, PIPELINE_NODES } from "@/data/site-content";
import { SectionHeader } from "@/components/layout/SectionHeader";

const AGENT_COLORS = [
  "#4F46E5", // indigo  - Mary
  "#06B6D4", // cyan    - John
  "#DB2777", // pink    - Sally
  "#15803D", // green   - Winston
  "#B45309", // amber   - Amelia
  "#7C3AED", // violet  - Paige
];

export function Agents() {
  return (
    <section className="py-16 md:py-24 container-tight">
      <SectionHeader
        eyebrow="The brain"
        title="Six BMAD personas, one 13-step pipeline."
        description="Every node writes a real markdown artifact. Downstream agents read it as context. Humans approve at the gates."
      />

      <div className="mt-10 grid grid-cols-2 md:grid-cols-3 gap-5">
        {AGENTS.map((a, i) => {
          const color = AGENT_COLORS[i % AGENT_COLORS.length];
          return (
            <div
              key={a.name}
              className="bg-surface border border-zinc-200 rounded-xl shadow-soft p-5 transition-all hover:-translate-y-0.5 hover:shadow-md"
            >
              <div className="flex items-center gap-3">
                <div
                  className="h-11 w-11 rounded-full grid place-items-center text-white text-[15px] font-semibold"
                  style={{ background: color }}
                >
                  {a.name.charAt(0)}
                </div>
                <div>
                  <div className="text-[14.5px] font-semibold text-ink">{a.name}</div>
                  <div className="text-[12px] text-ink-4 font-mono">{a.role}</div>
                </div>
              </div>
              <p className="mt-3 text-[12.5px] text-ink-3 leading-relaxed">{a.skill}</p>
            </div>
          );
        })}
      </div>

      <div className="mt-12">
        <div className="eyebrow mb-4">The 13-step pipeline</div>
        <div className="bg-surface border border-zinc-200 rounded-xl shadow-soft p-5">
          <div className="flex flex-wrap items-center gap-y-3">
            {PIPELINE_NODES.map((node, i) => (
              <div key={node} className="flex items-center">
                <span className="inline-flex items-center px-3 h-8 rounded-md bg-zinc-50 border border-zinc-200 text-[12px] font-medium text-ink-2 whitespace-nowrap">
                  {node}
                </span>
                {i < PIPELINE_NODES.length - 1 && (
                  <ChevronRight className="h-4 w-4 mx-1.5 text-ink-5 shrink-0" />
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
