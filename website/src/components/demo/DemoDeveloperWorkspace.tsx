import { useState } from "react";
import { FileCode, Notebook, ScrollText, FileJson, FileType, AlertTriangle, AlertCircle, Info, CheckCircle2 } from "lucide-react";
import { DemoShell } from "./DemoShell";
import { DEMO_ARTIFACTS, DEMO_DIFF_SAMPLE } from "@/data/demo-data";

const card = "bg-surface border border-zinc-200 rounded-xl shadow-soft p-5";

type Tab = "diff" | "notebook" | "review";

const REVIEW_FINDINGS = [
  { severity: "high",   message: "MERGE statement missing WHEN MATCHED clause — duplicates from re-runs.", line: "L 12" },
  { severity: "medium", message: "Connection not closed in exception path; use context manager.",          line: "L 38" },
  { severity: "low",    message: "Consider adding type hints to upsert(rows) for downstream agents.",     line: "L 4" },
  { severity: "info",   message: "Batch size of 5000 is good. Snowflake recommends 1k-10k for MERGE.",     line: "L 22" },
  { severity: "ok",     message: "Unit tests cover empty input and dedupe path.",                          line: "tests/" },
];

function ArtifactIcon({ kind }: { kind: string }) {
  const map: Record<string, any> = { code: FileCode, notebook: Notebook, config: FileJson, doc: FileType };
  const I = map[kind] || FileCode;
  return <I className="h-3.5 w-3.5 text-ink-3" />;
}

function KindChip({ kind }: { kind: string }) {
  const map: Record<string, string> = {
    code:     "bg-brand-50 text-brand-700",
    notebook: "bg-amber-50 text-amber-700",
    config:   "bg-emerald-50 text-emerald-700",
    doc:      "bg-zinc-100 text-ink-3",
  };
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${map[kind] || "bg-zinc-100 text-ink-3"}`}>
      {kind}
    </span>
  );
}

function SeverityIcon({ s }: { s: string }) {
  if (s === "high")   return <AlertCircle className="h-4 w-4 text-rose-600" />;
  if (s === "medium") return <AlertTriangle className="h-4 w-4 text-amber-600" />;
  if (s === "low")    return <Info className="h-4 w-4 text-cyan-500" />;
  if (s === "ok")     return <CheckCircle2 className="h-4 w-4 text-emerald-600" />;
  return <Info className="h-4 w-4 text-ink-4" />;
}

export function DemoDeveloperWorkspace() {
  const [tab, setTab] = useState<Tab>("diff");
  const [selected, setSelected] = useState(DEMO_ARTIFACTS[0].id);

  return (
    <DemoShell title="Developer workspace" description="Artifacts, diffs, notebooks, and adversarial review in one place.">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Artifact explorer */}
        <div className={`${card} p-0 overflow-hidden lg:col-span-4`}>
          <div className="px-5 py-3 border-b border-zinc-200">
            <h3 className="text-[14px] font-semibold text-ink">Artifacts</h3>
            <p className="text-[11.5px] text-ink-4 mt-0.5">{DEMO_ARTIFACTS.length} files · BMAD-a8f3c2</p>
          </div>
          <ul className="divide-y divide-zinc-200">
            {DEMO_ARTIFACTS.map((a) => {
              const active = selected === a.id;
              return (
                <li key={a.id}>
                  <button
                    onClick={() => setSelected(a.id)}
                    className={
                      "w-full text-left px-5 py-3 hover:bg-surface-muted transition-colors focus-ring " +
                      (active ? "bg-brand-50/40" : "")
                    }
                  >
                    <div className="flex items-center gap-2">
                      <ArtifactIcon kind={a.kind} />
                      <span className="font-mono text-[12.5px] text-ink truncate">{a.name}</span>
                      <KindChip kind={a.kind} />
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-ink-4 font-mono mt-1.5">
                      <span>{a.version} · {a.size}</span>
                      <span>{a.updated}</span>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>

        {/* Diff / notebook / review */}
        <div className={`${card} p-0 overflow-hidden lg:col-span-8`}>
          <div className="px-5 py-2.5 border-b border-zinc-200 flex items-center gap-1">
            {(["diff", "notebook", "review"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={
                  "px-3 py-1.5 rounded-md text-[12.5px] font-medium transition-colors focus-ring " +
                  (tab === t ? "bg-zinc-100 text-ink" : "text-ink-3 hover:text-ink hover:bg-zinc-100/70")
                }
              >
                {t === "diff" ? "Diff" : t === "notebook" ? "Notebook" : "Review"}
              </button>
            ))}
            <span className="ml-auto text-[11px] text-ink-4 font-mono">{DEMO_DIFF_SAMPLE.filename}</span>
          </div>

          <div className="p-0">
            {tab === "diff" && <DiffView />}
            {tab === "notebook" && <NotebookView />}
            {tab === "review" && <ReviewView />}
          </div>
        </div>
      </div>
    </DemoShell>
  );
}

function DiffView() {
  const before = DEMO_DIFF_SAMPLE.before.split("\n");
  const after  = DEMO_DIFF_SAMPLE.after.split("\n");
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-zinc-200">
      <div>
        <div className="px-4 py-2 bg-rose-50 text-rose-700 text-[11px] font-medium border-b border-zinc-200 font-mono">
          before · v2
        </div>
        <pre className="text-[12px] leading-5 font-mono">
          {before.map((line, i) => (
            <div key={i} className="flex bg-rose-50/40 hover:bg-rose-50/60">
              <span className="w-10 text-right pr-3 text-ink-5 select-none border-r border-rose-100">{i + 1}</span>
              <span className="pl-3 pr-4 text-ink-2 whitespace-pre">{line || " "}</span>
            </div>
          ))}
        </pre>
      </div>
      <div>
        <div className="px-4 py-2 bg-emerald-50 text-emerald-700 text-[11px] font-medium border-b border-zinc-200 font-mono">
          after · v3
        </div>
        <pre className="text-[12px] leading-5 font-mono">
          {after.map((line, i) => (
            <div key={i} className="flex bg-emerald-50/40 hover:bg-emerald-50/60">
              <span className="w-10 text-right pr-3 text-ink-5 select-none border-r border-emerald-100">{i + 1}</span>
              <span className="pl-3 pr-4 text-ink-2 whitespace-pre">{line || " "}</span>
            </div>
          ))}
        </pre>
      </div>
    </div>
  );
}

function NotebookView() {
  return (
    <div className="p-6 text-center">
      <div className="h-12 w-12 rounded-lg bg-brand-50 text-brand-600 grid place-items-center mx-auto">
        <Notebook className="h-6 w-6" />
      </div>
      <div className="mt-4 text-[14px] font-semibold text-ink">recon.ipynb</div>
      <div className="text-[12.5px] text-ink-3 mt-1">3 cells · Python · 218 lines</div>
      <div className="mt-5 text-[12px] text-ink-4 font-mono max-w-md mx-auto leading-relaxed">
        # Cell 1 — load source counts<br />
        # Cell 2 — load target counts<br />
        # Cell 3 — diff + signed summary
      </div>
      <button className="mt-5 inline-flex items-center px-3.5 py-1.5 rounded-md text-[12.5px] font-medium bg-ink text-white hover:bg-zinc-800 focus-ring">
        Open notebook
      </button>
    </div>
  );
}

function ReviewView() {
  return (
    <div className="p-5">
      <div className="flex items-center gap-2 mb-3">
        <ScrollText className="h-4 w-4 text-ink-3" />
        <h4 className="text-[13.5px] font-semibold text-ink">Adversarial review · {REVIEW_FINDINGS.length} findings</h4>
      </div>
      <ul className="divide-y divide-zinc-200">
        {REVIEW_FINDINGS.map((f, i) => (
          <li key={i} className="py-3 flex items-start gap-3">
            <SeverityIcon s={f.severity} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono text-ink-4 uppercase tracking-wide">{f.severity}</span>
                <span className="text-[11px] font-mono text-ink-5">{f.line}</span>
              </div>
              <div className="text-[12.5px] text-ink-2 mt-0.5">{f.message}</div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
