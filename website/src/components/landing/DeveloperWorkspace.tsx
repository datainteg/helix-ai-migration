import { FolderTree, GitCompareArrows, MessageSquareCode, NotebookPen } from "lucide-react";

import { SectionHeader } from "@/components/layout/SectionHeader";

const BULLETS = [
  {
    icon: FolderTree,
    title: "Artifact explorer",
    desc: "Every BMAD output (PRD, architecture, dev story, QA, docs) opens as a versioned markdown file.",
  },
  {
    icon: GitCompareArrows,
    title: "Diff viewer",
    desc: "Side-by-side before/after for every generated change. No black-box rewrites.",
  },
  {
    icon: MessageSquareCode,
    title: "Code review",
    desc: "Comment, approve, or kick back to the agent without leaving the workspace.",
  },
  {
    icon: NotebookPen,
    title: "Notebook drafts",
    desc: "Auto-generated Databricks / Jupyter notebooks queued for human review before execution.",
  },
];

export function DeveloperWorkspace() {
  return (
    <section className="py-16 md:py-24 container-tight">
      <SectionHeader
        eyebrow="Developer workspace"
        title="AI writes the draft. You ship the review."
        description="Helix never auto-merges generated code. Every artifact lands as a reviewable diff with full version history."
      />
      <div className="mt-10 grid grid-cols-1 md:grid-cols-2 gap-8 items-center">
        <DiffCard />
        <ul className="space-y-5">
          {BULLETS.map((b) => (
            <li key={b.title} className="flex gap-4">
              <div className="h-10 w-10 rounded-lg grid place-items-center bg-brand-50 text-brand-600 ring-1 ring-brand-100 shrink-0">
                <b.icon className="h-5 w-5" />
              </div>
              <div>
                <div className="text-[14.5px] font-semibold text-ink">{b.title}</div>
                <p className="mt-1 text-[12.5px] text-ink-3 leading-relaxed">{b.desc}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function DiffCard() {
  return (
    <div className="bg-surface border border-zinc-200 rounded-xl shadow-md overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-zinc-200 bg-zinc-50/70">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-zinc-300" />
            <span className="h-2.5 w-2.5 rounded-full bg-zinc-300" />
            <span className="h-2.5 w-2.5 rounded-full bg-zinc-300" />
          </div>
          <span className="ml-2 font-mono text-[11px] text-ink-4">migrate_gl_accounts.sql</span>
        </div>
        <span className="font-mono text-[10.5px] text-ink-4">+3 −2</span>
      </div>
      <div className="grid grid-cols-2 divide-x divide-zinc-200 font-mono text-[11.5px] leading-relaxed">
        <div>
          <div className="px-3 py-1.5 border-b border-zinc-200 bg-zinc-50/60 text-ink-4 text-[10.5px]">Before</div>
          <pre className="px-3 py-3 m-0 overflow-x-auto">
            <DiffRow type="ctx">SELECT account_id, name</DiffRow>
            <DiffRow type="del">  ,balance</DiffRow>
            <DiffRow type="del">FROM oracle.gl_accounts</DiffRow>
            <DiffRow type="ctx">WHERE active = 1</DiffRow>
          </pre>
        </div>
        <div>
          <div className="px-3 py-1.5 border-b border-zinc-200 bg-zinc-50/60 text-ink-4 text-[10.5px]">After</div>
          <pre className="px-3 py-3 m-0 overflow-x-auto">
            <DiffRow type="ctx">SELECT account_id, name</DiffRow>
            <DiffRow type="add">  ,CAST(balance AS DECIMAL(18,2))</DiffRow>
            <DiffRow type="add">  ,created_at::TIMESTAMP_NTZ</DiffRow>
            <DiffRow type="add">FROM snowflake.gl_accounts</DiffRow>
            <DiffRow type="ctx">WHERE active = TRUE</DiffRow>
          </pre>
        </div>
      </div>
    </div>
  );
}

function DiffRow({ type, children }: { type: "ctx" | "add" | "del"; children: React.ReactNode }) {
  const cls =
    type === "add"
      ? "bg-emerald-50 text-emerald-900"
      : type === "del"
      ? "bg-rose-50 text-rose-900"
      : "text-ink-3";
  const prefix = type === "add" ? "+" : type === "del" ? "−" : " ";
  return (
    <div className={`-mx-3 px-3 ${cls}`}>
      <span className="opacity-60 mr-2">{prefix}</span>
      {children}
    </div>
  );
}
