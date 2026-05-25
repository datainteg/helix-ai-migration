import { ArrowRight, Calendar, GitBranch, KanbanSquare, Map } from "lucide-react";

import { Hero } from "@/components/landing/Hero";
import { Features } from "@/components/landing/Features";
import { Architecture } from "@/components/landing/Architecture";
import { FeatureMap } from "@/components/landing/FeatureMap";
import { Agents } from "@/components/landing/Agents";
import { Connectors } from "@/components/landing/Connectors";
import { ValidationRecon } from "@/components/landing/ValidationRecon";
import { DeveloperWorkspace } from "@/components/landing/DeveloperWorkspace";
import { DockerInstall } from "@/components/landing/DockerInstall";
import { Roadmap } from "@/components/landing/Roadmap";
import { CTA } from "@/components/landing/CTA";
import { SectionHeader } from "@/components/layout/SectionHeader";
import { PROBLEM_BLOCK, SOLUTION_BLOCK, STATIC_DEMO_URL } from "@/data/site-content";

const SPRINT_TEASER = [
  { icon: KanbanSquare, title: "Sprint board", desc: "Migration-specific kanban with risk + validation badges per card." },
  { icon: Map,          title: "Execution map", desc: "Per-sprint dependency graph from source schema to target load." },
  { icon: GitBranch,    title: "Dependency graph", desc: "See the blast radius of any artifact change before you ship it." },
  { icon: Calendar,     title: "Release calendar", desc: "Approval gates and cutover windows on one timeline." },
];

export function HomePage() {
  return (
    <>
      <Hero />

      <section className="py-16 md:py-24 container-tight">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-10 md:gap-14 items-start">
          <div>
            <div className="eyebrow mb-3">The problem</div>
            <h2 className="text-[24px] md:text-[30px] font-semibold tracking-tight text-ink leading-tight">
              {PROBLEM_BLOCK.title}
            </h2>
            <div className="mt-5 space-y-4">
              {PROBLEM_BLOCK.body.map((p, i) => (
                <p key={i} className="text-[14px] text-ink-3 leading-relaxed">{p}</p>
              ))}
            </div>
          </div>
          <div className="md:border-l md:border-zinc-200 md:pl-10">
            <div className="eyebrow mb-3" style={{ color: "#4F46E5" }}>The solution</div>
            <h2 className="text-[24px] md:text-[30px] font-semibold tracking-tight text-ink leading-tight">
              {SOLUTION_BLOCK.title}
            </h2>
            <div className="mt-5 space-y-4">
              {SOLUTION_BLOCK.body.map((p, i) => (
                <p key={i} className="text-[14px] text-ink-3 leading-relaxed">{p}</p>
              ))}
            </div>
          </div>
        </div>
      </section>

      <Features />
      <FeatureMap />
      <Architecture />
      <Agents />
      <Connectors />
      <ValidationRecon />
      <DeveloperWorkspace />

      <section className="py-16 md:py-24 container-tight">
        <div className="flex items-end justify-between gap-6 flex-wrap">
          <SectionHeader
            eyebrow="Sprint surface"
            title="Migration-aware sprint management, not a generic kanban."
            description="See the live console for the full execution map, dependency graph, and release calendar."
          />
          <a
            href={STATIC_DEMO_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 px-3 h-9 rounded-md text-ink-3 text-[13px] font-medium hover:text-ink hover:bg-zinc-100/70 focus-ring"
          >
            Open live console
            <ArrowRight className="h-4 w-4" />
          </a>
        </div>
        <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {SPRINT_TEASER.map((s) => (
            <div
              key={s.title}
              className="bg-surface border border-zinc-200 rounded-xl shadow-soft p-5 transition-all hover:-translate-y-0.5 hover:shadow-md"
            >
              <div className="h-10 w-10 rounded-lg grid place-items-center bg-brand-50 text-brand-600 ring-1 ring-brand-100">
                <s.icon className="h-5 w-5" />
              </div>
              <div className="mt-4 text-[14px] font-semibold text-ink">{s.title}</div>
              <p className="mt-1.5 text-[12.5px] text-ink-3 leading-relaxed">{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <DockerInstall />
      <Roadmap />
      <CTA />
    </>
  );
}
