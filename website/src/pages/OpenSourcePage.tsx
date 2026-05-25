import { Github, Star, GitFork, Scale, Folder, FileCode, GitCommit, Check } from "lucide-react";

import { SectionHeader } from "@/components/layout/SectionHeader";
import { SITE, CONTENT_RULES_DISCLOSURE } from "@/data/site-content";

const WHY_OSS = [
  { title: "Operator-owned", desc: "You self-host the whole stack. Your data plane, your secrets, your audit chain." },
  { title: "No managed dependency", desc: "Helix never phones home. No telemetry, no remote control plane, no SaaS lock-in." },
  { title: "Code review of every release", desc: "Every PR runs through BMAD-style adversarial review. Releases ship from public main." },
  { title: "Apache 2.0", desc: "Use it commercially. Fork it. Modify it. Ship it. The license is yours forever." },
];

const REPO_TREE = [
  { name: "frontend/",  desc: "Next.js 14 operator UI" },
  { name: "backend/",   desc: "FastAPI + 18 routers" },
  { name: "worker/",    desc: "Temporal worker + BMAD pipeline" },
  { name: "agents/",    desc: "BMAD persona definitions" },
  { name: "_bmad/",     desc: "Vendored BMAD-METHOD" },
  { name: "website/",   desc: "This marketing site" },
  { name: "docs/",      desc: "Markdown documentation" },
];

const RECENT_ACTIVITY = [
  { msg: "feat(p3): implement all 10 P3 backlog enhancements", when: "2d ago" },
  { msg: "feat(p2): implement all 12 remaining P2 medium-priority improvements", when: "5d ago" },
  { msg: "feat: Docker Compose, frontend admin pages, and backend refinements", when: "1w ago" },
  { msg: "fix: accept NEXT_PUBLIC_API_URL build arg in frontend Dockerfile", when: "1w ago" },
];

export function OpenSourcePage() {
  return (
    <>
      <section className="py-16 md:py-20 container-tight">
        <SectionHeader
          eyebrow="Apache 2.0"
          title="Open source by design"
          description={SITE.tagline}
        />
      </section>

      <section className="py-8 md:py-12 container-tight">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 lg:gap-12 items-start">
          <div>
            <div className="eyebrow mb-3">Why open source</div>
            <ul className="space-y-5">
              {WHY_OSS.map((b) => (
                <li key={b.title} className="flex gap-4">
                  <span className="mt-1 h-6 w-6 rounded-full grid place-items-center bg-brand-50 text-brand-600 ring-1 ring-brand-100 shrink-0">
                    <Check className="h-3.5 w-3.5" />
                  </span>
                  <div>
                    <div className="text-[14.5px] font-semibold text-ink">{b.title}</div>
                    <p className="mt-1 text-[13px] text-ink-3 leading-relaxed">{b.desc}</p>
                  </div>
                </li>
              ))}
            </ul>

            <div className="mt-8 pt-6 border-t border-zinc-200">
              <div className="eyebrow mb-3">How to contribute</div>
              <p className="text-[13px] text-ink-3 leading-relaxed">
                Read the contribution guide, open an issue, or jump straight to a PR. All discussion
                happens in the open on GitHub.
              </p>
              <a
                href={`${SITE.github}/blob/main/CONTRIBUTING.md`}
                target="_blank"
                rel="noreferrer"
                className="mt-4 inline-flex items-center gap-2 px-4 h-10 rounded-md bg-ink text-white text-[13.5px] font-medium hover:bg-zinc-800 focus-ring"
              >
                <Github className="h-4 w-4" />
                CONTRIBUTING.md
              </a>
            </div>
          </div>

          <div className="bg-surface border border-zinc-200 rounded-xl shadow-soft overflow-hidden">
            <div className="px-5 py-4 border-b border-zinc-200 bg-zinc-50/60 flex items-center gap-2">
              <Github className="h-4 w-4 text-ink-2" />
              <a
                href={SITE.github}
                target="_blank"
                rel="noreferrer"
                className="font-mono text-[12.5px] text-ink hover:underline"
              >
                {SITE.repoSlug}
              </a>
            </div>
            <div className="px-5 py-4 flex flex-wrap gap-2.5 border-b border-zinc-200">
              <Badge icon={<Star className="h-3.5 w-3.5" />} label="1.2k stars" />
              <Badge icon={<GitFork className="h-3.5 w-3.5" />} label="148 forks" />
              <Badge icon={<Scale className="h-3.5 w-3.5" />} label={SITE.license} />
            </div>

            <div className="px-5 py-4 border-b border-zinc-200">
              <div className="eyebrow mb-3">File tree</div>
              <ul className="space-y-1.5">
                {REPO_TREE.map((f) => (
                  <li key={f.name} className="flex items-center gap-2.5 text-[12.5px]">
                    {f.name.endsWith("/") ? (
                      <Folder className="h-4 w-4 text-brand-600 shrink-0" />
                    ) : (
                      <FileCode className="h-4 w-4 text-ink-4 shrink-0" />
                    )}
                    <span className="font-mono text-ink">{f.name}</span>
                    <span className="text-ink-4 truncate">— {f.desc}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="px-5 py-4">
              <div className="eyebrow mb-3">Recent activity</div>
              <ul className="space-y-2.5">
                {RECENT_ACTIVITY.map((c, i) => (
                  <li key={i} className="flex items-start gap-2.5 text-[12.5px]">
                    <GitCommit className="h-4 w-4 text-ink-4 shrink-0 mt-[1px]" />
                    <span className="text-ink-2 leading-snug">{c.msg}</span>
                    <span className="ml-auto text-ink-5 font-mono text-[11px] shrink-0">{c.when}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section className="py-16 md:py-24 container-tight">
        <SectionHeader
          eyebrow="Principles"
          title="Four rules we ship by."
          description="Open source isn't only the license — it's how we treat your data and decisions."
        />
        <div className="mt-10 grid grid-cols-1 md:grid-cols-2 gap-5">
          {CONTENT_RULES_DISCLOSURE.map((rule, i) => (
            <div
              key={i}
              className="bg-surface border border-zinc-200 rounded-xl shadow-soft p-6 flex gap-4"
            >
              <div className="h-10 w-10 rounded-lg grid place-items-center bg-brand-50 text-brand-600 ring-1 ring-brand-100 shrink-0 font-mono text-[13px] font-semibold">
                {String(i + 1).padStart(2, "0")}
              </div>
              <p className="text-[13.5px] text-ink-2 leading-relaxed">{rule}</p>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

function Badge({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 h-7 rounded-md bg-zinc-100 text-ink-2 text-[12px] font-medium">
      {icon}
      {label}
    </span>
  );
}
