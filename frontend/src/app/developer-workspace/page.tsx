"use client";

import React, { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Folder,
  X,
  GitBranch,
  Upload,
  Sparkles,
  Check,
  RefreshCw,
} from "lucide-react";

import { AppShell } from "@/components/layout";
import { AgentIcon } from "@/components/icons";
import { Button, Chip, Kbd, Tabs, DemoBanner, SearchInput } from "@/components/ui";

// TODO: hydrate from API
interface ArtifactFile {
  kind: "file";
  label: string;
  version: string;
  ext: string;
  active: boolean;
  ai?: "ok" | "warn";
  suggestions?: number;
}

interface ArtifactFolder {
  kind: "folder";
  label: string;
  expanded?: boolean;
  children: ArtifactFile[];
}

const ARTIFACT_TREE: ArtifactFolder[] = [
  {
    kind: "folder",
    label: "plan",
    children: [
      { kind: "file", label: "plan_v3.md", version: "v3", ext: "md", active: false, ai: "ok" },
      { kind: "file", label: "epics.md", version: "v2", ext: "md", active: false },
      { kind: "file", label: "story_1.md", version: "v1", ext: "md", active: false, ai: "ok" },
    ],
  },
  {
    kind: "folder",
    label: "ddl",
    children: [
      { kind: "file", label: "snowflake_ddl.sql", version: "v2", ext: "sql", active: false, ai: "ok" },
      { kind: "file", label: "schemas.sql", version: "v1", ext: "sql", active: false },
    ],
  },
  {
    kind: "folder",
    label: "migration",
    expanded: true,
    children: [
      { kind: "file", label: "migrate.py", version: "v3", ext: "py", active: true, ai: "warn", suggestions: 3 },
      { kind: "file", label: "utils.py", version: "v2", ext: "py", active: false, ai: "ok" },
      { kind: "file", label: "session.py", version: "v2", ext: "py", active: false },
    ],
  },
  {
    kind: "folder",
    label: "validation",
    children: [
      { kind: "file", label: "validate.sql", version: "v2", ext: "sql", active: false, ai: "ok" },
      { kind: "file", label: "checks.yaml", version: "v1", ext: "yml", active: false },
    ],
  },
  {
    kind: "folder",
    label: "notebooks",
    children: [
      { kind: "file", label: "exploration.ipynb", version: "v1", ext: "ipynb", active: false },
    ],
  },
];

interface VersionEntry {
  v: string;
  agent: string;
  date: string;
  msg: string;
  current?: boolean;
}

const VERSION_HISTORY: VersionEntry[] = [
  { v: "v3", agent: "Amelia", date: "12:42", msg: "Refactor to session pool", current: true },
  { v: "v2", agent: "Amelia", date: "12:18", msg: "Initial implementation" },
  { v: "v1", agent: "Winston", date: "11:54", msg: "Scaffolded from story_1" },
];

interface DiffLine {
  type: "ctx" | "add" | "rem";
  n: number;
  txt: string;
}

const DIFF_LINES: DiffLine[] = [
  { type: "ctx", n: 12, txt: "import logging" },
  { type: "ctx", n: 13, txt: "" },
  { type: "rem", n: 14, txt: "import pyodbc" },
  { type: "rem", n: 15, txt: "import pandas as pd" },
  { type: "add", n: 14, txt: "from helix.runtime import session, schemas" },
  { type: "add", n: 15, txt: "from helix.io import read_table, write_table" },
  { type: "ctx", n: 16, txt: "" },
  { type: "ctx", n: 17, txt: "log = logging.getLogger(__name__)" },
  { type: "ctx", n: 18, txt: "" },
  { type: "ctx", n: 19, txt: "def migrate_customers(batch_size: int = 5000) -> int:" },
  { type: "ctx", n: 20, txt: '    """Migrate CUSTOMER table from Oracle to Snowflake."""' },
  { type: "rem", n: 21, txt: "    conn = pyodbc.connect(DSN, autocommit=True)" },
  { type: "rem", n: 22, txt: '    df = pd.read_sql("SELECT * FROM HR.CUSTOMER", conn)' },
  { type: "add", n: 21, txt: '    src = session.source("oracle.hr")' },
  { type: "add", n: 22, txt: '    df = read_table(src, "CUSTOMER", schema=schemas.CUSTOMER_V2)' },
  { type: "ctx", n: 23, txt: "" },
  { type: "ctx", n: 24, txt: '    df = df.drop_duplicates(subset=["customer_id"])' },
  { type: "rem", n: 25, txt: "    df = df.where(pd.notnull(df), None)" },
  { type: "add", n: 25, txt: "    df = df.with_columns(updated_at=session.now())" },
  { type: "ctx", n: 26, txt: "" },
  { type: "ctx", n: 27, txt: '    tgt = session.target("snowflake.crm")' },
  { type: "rem", n: 28, txt: '    df.to_sql("customer", tgt.engine, if_exists="append")' },
  { type: "add", n: 28, txt: '    write_table(tgt, "customer", df, mode="upsert", key="customer_id")' },
  { type: "ctx", n: 29, txt: '    log.info("Migrated %d customers", len(df))' },
  { type: "ctx", n: 30, txt: "    return len(df)" },
];

interface AiReview {
  severity: "warn" | "ok" | "info";
  title: string;
  line: number;
  type: string;
  body: string;
  suggestion?: string;
}

const AI_REVIEWS: AiReview[] = [
  {
    severity: "warn",
    title: "Missing batch boundary",
    line: 22,
    type: "Performance",
    body: "read_table will materialize the full CUSTOMER table into memory. Consider streaming with batch_size to limit peak memory; this table is ~12M rows.",
    suggestion: 'df = read_table(src, "CUSTOMER", batch_size=batch_size)',
  },
  {
    severity: "ok",
    title: "Session pool migration",
    line: 21,
    type: "Architecture",
    body: "Removed raw pyodbc connection in favour of helix.session.source() — connection lifecycle and credentials are now managed by the runtime. Safe.",
  },
  {
    severity: "warn",
    title: "No explicit schema",
    line: 22,
    type: "Safety",
    body: "Add explicit schema=schemas.CUSTOMER_V2 so column drift in CUSTOMER is caught at read-time instead of at write. Currently passes but is fragile.",
  },
  {
    severity: "info",
    title: "Idempotent write",
    line: 28,
    type: "Architecture",
    body: 'Switching to write_table(mode="upsert", key=customer_id) makes this idempotent across retries — preferred pattern for Snowflake targets.',
  },
];

function ProjectSwitcher() {
  return (
    <button
      type="button"
      className="bg-surface flex items-center gap-2 text-ink-2 px-2.5 py-1.5 border border-hx-2 rounded-[7px] text-[12px]"
    >
      <span className="font-mono text-ink-4 text-[10.5px]">
        P-1042
      </span>
      <span className="text-ink font-medium">Oracle GL -&gt; Snowflake</span>
      <ChevronDown size={12} />
    </button>
  );
}

function Tree() {
  return (
    <div className="py-1 text-[12px]">
      {ARTIFACT_TREE.map((node, i) => (
        <div key={i}>
          <div className="flex items-center gap-1.5 px-3.5 py-[5px] text-ink-3 font-medium">
            <ChevronDown size={12} className="text-ink-4" />
            <Folder size={13} className="text-ink-4" />
            <span className="font-mono text-[11.5px]">
              {node.label}
            </span>
            <span className="font-mono text-ink-5 text-[10.5px] ml-auto">
              {node.children.length}
            </span>
          </div>
          {node.children.map((f, j) => {
            const aiColor =
              f.ai === "warn"
                ? "var(--con-warn)"
                : f.ai === "ok"
                  ? "var(--con-ok)"
                  : null;
            const extBg =
              f.ext === "py"
                ? "#FEF3C7"
                : f.ext === "sql"
                  ? "#DBEAFE"
                  : f.ext === "md"
                    ? "var(--con-bg-2)"
                    : f.ext === "yml"
                      ? "#DCFCE7"
                      : "var(--con-bg-2)";
            const extColor =
              f.ext === "py"
                ? "#92400E"
                : f.ext === "sql"
                  ? "#1E40AF"
                  : f.ext === "md"
                    ? "var(--con-ink-3)"
                    : f.ext === "yml"
                      ? "#166534"
                      : "var(--con-ink-3)";
            return (
              <div
                key={j}
                className={`flex items-center gap-1.5 cursor-pointer py-1 pr-3.5 pl-9 border-l-2 ${
                  f.active ? "bg-surface-hi border-ink" : "border-transparent"
                }`}
              >
                <span
                  className="font-mono uppercase font-semibold text-[9.5px] px-1 py-px rounded-[3px] tracking-[0.04em] w-7 text-center"
                  style={{ background: extBg, color: extColor }}
                >
                  {f.ext}
                </span>
                <span className={`font-mono flex-1 text-[11.5px] ${f.active ? "text-ink" : "text-ink-2"}`}>
                  {f.label}
                </span>
                {aiColor && (
                  <span
                    className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                    style={{ background: aiColor }}
                  />
                )}
                {f.suggestions !== undefined && (
                  <span className="font-mono text-warn text-[10px] flex-shrink-0">
                    {f.suggestions}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

function DiffPane() {
  const [diffTab, setDiffTab] = useState("diff");
  const lineColor = (t: DiffLine["type"]) =>
    t === "add"
      ? "rgba(21,128,61,0.06)"
      : t === "rem"
        ? "rgba(185,28,28,0.06)"
        : "transparent";
  const lineNumberColor = (t: DiffLine["type"]) =>
    t === "add"
      ? "var(--con-ok)"
      : t === "rem"
        ? "var(--con-err)"
        : "var(--con-ink-5)";

  return (
    <div className="flex flex-col bg-surface h-full">
      {/* Tabs */}
      <div className="flex items-stretch h-9 bg-surface-hi border-b border-hx">
        <div className="inline-flex items-center gap-2 bg-surface px-3.5 border-r border-hx border-b-2 border-b-ink -mb-px">
          <span
            className="font-mono font-semibold text-[9.5px] px-1 py-px rounded-[3px]"
            style={{ background: "#FEF3C7", color: "#92400E" }}
          >
            PY
          </span>
          <span className="font-mono text-[12px]">
            migrate.py
          </span>
          <span className="text-warn text-[10px]">
            ●
          </span>
          <X size={11} className="text-ink-4 ml-1" />
        </div>
        <div className="inline-flex items-center gap-2 text-ink-4 px-3.5 border-r border-hx">
          <span className="font-mono text-[11.5px]">
            utils.py
          </span>
          <X size={11} />
        </div>
        <div className="flex-1" />
        <div className="flex items-center gap-1.5 px-3">

          <Tabs
            tabs={[
              { id: "diff", label: "Diff" },
              { id: "code", label: "Code" },
              { id: "tree", label: "Notebook" },
            ]}
            value={diffTab}
            onChange={setDiffTab}
          />
        </div>
      </div>

      {/* Tab subbar */}
      <div className="flex flex-wrap items-center gap-x-3.5 gap-y-1 bg-surface border-b border-hx text-ink-3 px-4 py-2 text-[11.5px]">
        <span className="inline-flex items-center gap-1.5">
          <GitBranch size={12} className="text-ink-4" />
          <span className="font-mono">v3 ← v2</span>
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="font-mono text-ok">+9</span>
          <span className="font-mono text-err">−5</span>
          <span className="font-mono">lines</span>
        </span>
        <span className="inline-flex items-center gap-1.5">
          <AgentIcon name="Amelia" size={14} />
          <span>Amelia · 12:42</span>
        </span>
        <span className="flex-1" />
        <span className="font-mono text-ink-4 text-[11px]">
          SHA 8f3c2a · 412 lines
        </span>
      </div>

      {/* Diff body */}
      <div className="flex-1 overflow-y-auto bg-surface font-mono py-2.5 text-[12px] leading-[1.6]">
        {DIFF_LINES.map((l, i) => (
          <div
            key={i}
            className="grid grid-cols-[44px_22px_1fr] py-px"
            style={{ background: lineColor(l.type) }}
          >
            <span
              className="text-right pr-2.5 text-[11px]"
              style={{ color: lineNumberColor(l.type) }}
            >
              {l.n}
            </span>
            <span
              className="text-center font-semibold"
              style={{ color: lineNumberColor(l.type) }}
            >
              {l.type === "add" ? "+" : l.type === "rem" ? "−" : ""}
            </span>
            <span
              className="whitespace-pre"
              style={{
                color:
                  l.type === "ctx"
                    ? "var(--con-ink-2)"
                    : l.type === "add"
                      ? "var(--con-ok)"
                      : "var(--con-err)",
              }}
            >
              {l.txt}
            </span>
          </div>
        ))}
        <div className="text-ink-4 px-6 py-2.5 text-[11px]">
          — 386 more lines —
        </div>
      </div>

      {/* Bottom action bar */}
      <div className="flex flex-wrap items-center justify-between gap-y-2 bg-surface-hi border-t border-hx px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Chip tone="warn" dot>
            Pending approval
          </Chip>
          <span className="text-ink-3 text-[11.5px]">
            3 AI suggestions · 0 review comments
          </span>
        </div>
        <div className="flex gap-1.5">
          <Button variant="ghost" size="sm">
            <X size={12} /> Reject
          </Button>
          <Button variant="outline" size="sm">
            <RefreshCw size={12} /> Regenerate
          </Button>
          <Button variant="primary" size="sm">
            <Check size={12} /> Approve v3
          </Button>
        </div>
      </div>
    </div>
  );
}

function AiReviewPane() {
  return (
    <div className="flex flex-col bg-surface h-full">
      {/* Header */}
      <div className="border-b border-hx px-4 py-3">
        <div className="eyebrow flex items-center gap-1.5">
          <Sparkles size={11} className="text-[var(--con-brand)]" />
          AI REVIEW · CLAUDE 3.7
        </div>
        <div className="text-[14px] font-semibold mt-1">
          migrate.py
        </div>
        <div className="flex gap-3 mt-2 text-ink-3 text-[11px]">
          <span className="inline-flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-con-ok" />
            1 OK
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-con-warn" />
            2 Warning
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-con-info" />
            1 Info
          </span>
        </div>
      </div>

      {/* Reviews */}
      <div className="flex-1 overflow-y-auto">
        {AI_REVIEWS.map((r, i) => {
          const c =
            r.severity === "warn"
              ? "var(--con-warn)"
              : r.severity === "ok"
                ? "var(--con-ok)"
                : "var(--con-info)";
          return (
            <div
              key={i}
              className="px-4 py-3.5 border-b border-hx last:border-b-0"
            >
              <div className="flex items-start justify-between gap-2 mb-1.5">
                <div className="flex items-center gap-[7px] min-w-0">
                  <span
                    className="w-1.5 h-1.5 rounded-full mt-px flex-shrink-0"
                    style={{ background: c }}
                  />
                  <span className="text-ink text-[12.5px] font-medium">
                    {r.title}
                  </span>
                </div>
                <span className="font-mono text-ink-4 text-[10.5px]">
                  L{r.line}
                </span>
              </div>
              <div className="eyebrow text-[9px] mb-1.5">
                {r.type}
              </div>
              <p className="text-ink-2 m-0 text-[12px] leading-[1.55]">
                {r.body}
              </p>
              {r.suggestion && (
                <div className="bg-app border border-hx font-mono text-ok mt-2 px-2.5 py-2 rounded-md text-[11.5px]">
                  {r.suggestion}
                </div>
              )}
              <div className="flex gap-1.5 mt-2">
                <Button variant="outline" size="sm">
                  <Check size={11} /> Apply
                </Button>
                <Button variant="ghost" size="sm">
                  Dismiss
                </Button>
                <Button variant="ghost" size="sm">
                  <ChevronRight size={11} /> Jump to line
                </Button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer prompt */}
      <div className="border-t border-hx bg-surface-hi p-3.5">
        <div className="eyebrow mb-1.5">
          ASK HELIX ABOUT THIS FILE
        </div>
        <label className="relative flex items-center h-[34px] border border-hx rounded-[7px] pl-[30px] pr-2.5 bg-surface focus-within:ring-2 focus-within:ring-[var(--con-brand)] focus-within:ring-offset-1">
          <Sparkles size={13} aria-hidden className="absolute left-2.5 text-[var(--con-brand)]" />
          <input
            aria-label="Ask Helix about this migration step"
            placeholder="Explain this migration step…"
            className="bg-transparent border-0 outline-none w-full h-full text-ink text-[12.5px]"
          />
          <Kbd>↵</Kbd>
        </label>
      </div>
    </div>
  );
}

export default function WorkspacePage() {
  const [showLeftPane, setShowLeftPane] = useState(true);
  const [showRightPane, setShowRightPane] = useState(true);

  // Build responsive column template:
  // - Below md: only center pane visible (left/right are toggleable)
  // - md to <lg: left + center, optional right
  // - lg+: left + center + right
  const cols = [
    showLeftPane ? "260px" : null,
    "1fr",
    showRightPane ? "360px" : null,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <AppShell fullBleed>
      <div className="px-8 pt-3">
        <DemoBanner message="The IDE shows demo artifacts (migrate.py, ddl.sql, plan_v1.md). Upload or generate real artifacts to populate this workspace." />
      </div>
      {/* Custom page header (replaces PageHero for IDE layout) */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-hx px-8 pt-5 pb-3.5">
        <div className="flex items-center gap-4">
          <div>
            <div className="eyebrow">
              DEVELOPER WORKSPACE · MIGRATE.PY
            </div>
            <h1 className="mt-1 mb-0 text-[22px] font-medium tracking-[-0.02em]">
              Review &amp; approve
            </h1>
          </div>
          <span aria-hidden className="w-px h-7 bg-[var(--con-line-2)]" />
          <ProjectSwitcher />
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="md"
            className="md:hidden"
            aria-pressed={showLeftPane}
            aria-label={showLeftPane ? "Hide files" : "Show files"}
            onClick={() => setShowLeftPane((v) => !v)}
          >
            <Folder size={13} /> {showLeftPane ? "Hide files" : "Show files"}
          </Button>
          <Button
            variant="outline"
            size="md"
            className="lg:hidden"
            aria-pressed={showRightPane}
            aria-label={showRightPane ? "Hide review" : "Show review"}
            onClick={() => setShowRightPane((v) => !v)}
          >
            <Sparkles size={13} /> {showRightPane ? "Hide review" : "Show review"}
          </Button>
          <Button variant="outline" size="md">
            <Upload size={13} /> Upload artifact
          </Button>
          <Button variant="outline" size="md">
            <GitBranch size={13} /> History
          </Button>
          <Button variant="primary" size="md">
            <Sparkles size={13} /> Ask Helix
          </Button>
        </div>
      </div>

      {/* Three-pane workspace — wrapped in overflow-x-auto so the IDE
          degrades gracefully below ~1100px instead of clipping. */}
      <div className="overflow-x-auto border-b border-hx">
      <div
        className="grid"
        style={{
          gridTemplateColumns: cols,
          minWidth: showLeftPane && showRightPane ? 980 : 620,
          height: "calc(100vh - 44px - 81px)",
        }}
      >
        {/* LEFT: artifact explorer */}
        {showLeftPane && (
        <div className="flex flex-col bg-surface overflow-hidden min-w-0 border-r border-hx">
          <div className="border-b border-hx px-3.5 py-3">
            <div className="eyebrow mb-2">
              ARTIFACT EXPLORER
            </div>
            {/* UI-016/UI-026 — shared SearchInput primitive (aria-label + focus-ring). */}
            <SearchInput
              ariaLabel="Search files"
              placeholder="Search files…"
              className="h-7 text-[12px]"
            />
          </div>
          <div className="flex-1 overflow-y-auto">
            <Tree />
          </div>
          <div className="bg-surface-hi border-t border-hx px-3.5 py-3">
            <div className="eyebrow mb-2">
              VERSIONS · migrate.py
            </div>
            <div className="flex flex-col gap-px">
              {VERSION_HISTORY.map((v) => (
                <div
                  key={v.v}
                  className="grid grid-cols-[26px_1fr_auto] items-center gap-2 py-[5px] text-[11.5px]"
                >
                  <span
                    className={`font-mono font-semibold text-[9.5px] px-1 py-px rounded-[3px] text-center ${
                      v.current ? "text-white" : "text-ink-3"
                    }`}
                    style={{ background: v.current ? "var(--con-ink-1)" : "var(--con-bg-2)" }}
                  >
                    {v.v}
                  </span>
                  <div className="min-w-0">
                    <div className={`text-ink truncate text-[11.5px] ${v.current ? "font-medium" : "font-normal"}`}>
                      {v.msg}
                    </div>
                    <div className="font-mono text-ink-4 text-[10px]">
                      {v.agent} · {v.date}
                    </div>
                  </div>
                  <ChevronRight size={11} className="text-ink-4" />
                </div>
              ))}
            </div>
          </div>
        </div>
        )}

        {/* CENTER: diff — wrapped to allow shrinking */}
        <div className="min-w-0 overflow-hidden">
          <DiffPane />
        </div>

        {/* RIGHT: AI review */}
        {showRightPane && (
        <div className="bg-surface-hi overflow-hidden min-w-0 border-l border-hx">
          <AiReviewPane />
        </div>
        )}
      </div>
      </div>
    </AppShell>
  );
}
