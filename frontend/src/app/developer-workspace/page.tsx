"use client";

import React, { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Folder,
  Search,
  X,
  GitBranch,
  Upload,
  Sparkles,
  Check,
  RefreshCw,
} from "lucide-react";

import { AppShell } from "@/components/layout";
import { AgentIcon } from "@/components/icons";
import { Button, Chip, Kbd, Tabs, DemoBanner } from "@/components/ui";

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
      className="bg-surface flex items-center text-ink-2"
      style={{
        gap: 8,
        padding: "6px 10px",
        border: "1px solid var(--con-line-2)",
        borderRadius: 7,
        fontSize: 12,
      }}
    >
      <span className="font-mono text-ink-4" style={{ fontSize: 10.5 }}>
        P-1042
      </span>
      <span className="text-ink font-medium">Oracle GL -&gt; Snowflake</span>
      <ChevronDown size={12} />
    </button>
  );
}

function Tree() {
  return (
    <div style={{ padding: "4px 0", fontSize: 12 }}>
      {ARTIFACT_TREE.map((node, i) => (
        <div key={i}>
          <div
            className="flex items-center text-ink-3 font-medium"
            style={{ gap: 6, padding: "5px 14px" }}
          >
            <ChevronDown size={12} className="text-ink-4" />
            <Folder size={13} className="text-ink-4" />
            <span className="font-mono" style={{ fontSize: 11.5 }}>
              {node.label}
            </span>
            <span
              className="font-mono text-ink-5"
              style={{ fontSize: 10.5, marginLeft: "auto" }}
            >
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
                className="flex items-center cursor-pointer"
                style={{
                  gap: 6,
                  padding: "4px 14px 4px 36px",
                  background: f.active ? "var(--con-surface-hi)" : "transparent",
                  borderLeft: f.active
                    ? "2px solid var(--con-ink-1)"
                    : "2px solid transparent",
                }}
              >
                <span
                  className="font-mono uppercase font-semibold"
                  style={{
                    fontSize: 9.5,
                    padding: "1px 4px",
                    borderRadius: 3,
                    background: extBg,
                    color: extColor,
                    letterSpacing: "0.04em",
                    width: 28,
                    textAlign: "center",
                  }}
                >
                  {f.ext}
                </span>
                <span
                  className="font-mono"
                  style={{
                    flex: 1,
                    color: f.active ? "var(--con-ink-1)" : "var(--con-ink-2)",
                    fontSize: 11.5,
                  }}
                >
                  {f.label}
                </span>
                {aiColor && (
                  <span
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: "50%",
                      background: aiColor,
                      flexShrink: 0,
                    }}
                  />
                )}
                {f.suggestions !== undefined && (
                  <span
                    className="font-mono text-warn"
                    style={{ fontSize: 10, flexShrink: 0 }}
                  >
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
    <div
      className="flex flex-col bg-surface"
      style={{ height: "100%" }}
    >
      {/* Tabs */}
      <div
        className="flex bg-surface-hi border-b border-hx"
        style={{ height: 36, alignItems: "stretch" }}
      >
        <div
          className="inline-flex items-center bg-surface"
          style={{
            gap: 8,
            padding: "0 14px",
            borderRight: "1px solid var(--con-line)",
            borderBottom: "2px solid var(--con-ink-1)",
            marginBottom: -1,
          }}
        >
          <span
            className="font-mono font-semibold"
            style={{
              fontSize: 9.5,
              padding: "1px 4px",
              borderRadius: 3,
              background: "#FEF3C7",
              color: "#92400E",
            }}
          >
            PY
          </span>
          <span className="font-mono" style={{ fontSize: 12 }}>
            migrate.py
          </span>
          <span className="text-warn" style={{ fontSize: 10 }}>
            ●
          </span>
          <X size={11} className="text-ink-4" style={{ marginLeft: 4 }} />
        </div>
        <div
          className="inline-flex items-center text-ink-4"
          style={{
            gap: 8,
            padding: "0 14px",
            borderRight: "1px solid var(--con-line)",
          }}
        >
          <span className="font-mono" style={{ fontSize: 11.5 }}>
            utils.py
          </span>
          <X size={11} />
        </div>
        <div className="flex-1" />
        <div
          className="flex items-center"
          style={{ padding: "0 12px", gap: 6 }}
        >
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
      <div
        className="flex items-center bg-surface border-b border-hx text-ink-3"
        style={{
          gap: 14,
          padding: "8px 16px",
          fontSize: 11.5,
        }}
      >
        <span className="inline-flex items-center" style={{ gap: 5 }}>
          <GitBranch size={12} className="text-ink-4" />
          <span className="font-mono">v3 ← v2</span>
        </span>
        <span className="inline-flex items-center" style={{ gap: 5 }}>
          <span className="font-mono text-ok">+9</span>
          <span className="font-mono text-err">−5</span>
          <span className="font-mono">lines</span>
        </span>
        <span className="inline-flex items-center" style={{ gap: 5 }}>
          <AgentIcon name="Amelia" size={14} />
          <span>Amelia · 12:42</span>
        </span>
        <span className="flex-1" />
        <span className="font-mono text-ink-4" style={{ fontSize: 11 }}>
          SHA 8f3c2a · 412 lines
        </span>
      </div>

      {/* Diff body */}
      <div
        className="flex-1 overflow-y-auto bg-surface font-mono"
        style={{
          padding: "10px 0",
          fontSize: 12,
          lineHeight: 1.6,
        }}
      >
        {DIFF_LINES.map((l, i) => (
          <div
            key={i}
            className="grid"
            style={{
              gridTemplateColumns: "44px 22px 1fr",
              background: lineColor(l.type),
              padding: "1px 0",
            }}
          >
            <span
              style={{
                textAlign: "right",
                padding: "0 10px 0 0",
                color: lineNumberColor(l.type),
                fontSize: 11,
              }}
            >
              {l.n}
            </span>
            <span
              style={{
                textAlign: "center",
                color: lineNumberColor(l.type),
                fontWeight: 600,
              }}
            >
              {l.type === "add" ? "+" : l.type === "rem" ? "−" : ""}
            </span>
            <span
              style={{
                color:
                  l.type === "ctx"
                    ? "var(--con-ink-2)"
                    : l.type === "add"
                      ? "var(--con-ok)"
                      : "var(--con-err)",
                whiteSpace: "pre",
              }}
            >
              {l.txt}
            </span>
          </div>
        ))}
        <div
          className="text-ink-4"
          style={{ padding: "10px 24px", fontSize: 11 }}
        >
          — 386 more lines —
        </div>
      </div>

      {/* Bottom action bar */}
      <div
        className="flex items-center justify-between bg-surface-hi border-t border-hx"
        style={{ padding: "10px 16px" }}
      >
        <div className="flex items-center" style={{ gap: 8 }}>
          <Chip tone="warn" dot>
            Pending approval
          </Chip>
          <span className="text-ink-3" style={{ fontSize: 11.5 }}>
            3 AI suggestions · 0 review comments
          </span>
        </div>
        <div className="flex" style={{ gap: 6 }}>
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
    <div
      className="flex flex-col bg-surface"
      style={{ height: "100%" }}
    >
      {/* Header */}
      <div
        className="border-b border-hx"
        style={{ padding: "12px 16px" }}
      >
        <div
          className="eyebrow flex items-center"
          style={{ gap: 6 }}
        >
          <Sparkles size={11} style={{ color: "var(--con-brand)" }} />
          AI REVIEW · CLAUDE 3.7
        </div>
        <div style={{ fontSize: 14, fontWeight: 600, marginTop: 4 }}>
          migrate.py
        </div>
        <div
          className="flex text-ink-3"
          style={{ gap: 12, marginTop: 8, fontSize: 11 }}
        >
          <span className="inline-flex items-center" style={{ gap: 4 }}>
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: "var(--con-ok)",
              }}
            />
            1 OK
          </span>
          <span className="inline-flex items-center" style={{ gap: 4 }}>
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: "var(--con-warn)",
              }}
            />
            2 Warning
          </span>
          <span className="inline-flex items-center" style={{ gap: 4 }}>
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: "var(--con-info)",
              }}
            />
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
              style={{
                padding: "14px 16px",
                borderBottom:
                  i === AI_REVIEWS.length - 1
                    ? "none"
                    : "1px solid var(--con-line)",
              }}
            >
              <div
                className="flex items-start justify-between"
                style={{ gap: 8, marginBottom: 6 }}
              >
                <div
                  className="flex items-center min-w-0"
                  style={{ gap: 7 }}
                >
                  <span
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: "50%",
                      background: c,
                      marginTop: 1,
                    }}
                  />
                  <span
                    className="text-ink"
                    style={{ fontSize: 12.5, fontWeight: 500 }}
                  >
                    {r.title}
                  </span>
                </div>
                <span
                  className="font-mono text-ink-4"
                  style={{ fontSize: 10.5 }}
                >
                  L{r.line}
                </span>
              </div>
              <div className="eyebrow" style={{ fontSize: 9, marginBottom: 6 }}>
                {r.type}
              </div>
              <p
                className="text-ink-2"
                style={{
                  margin: 0,
                  fontSize: 12,
                  lineHeight: 1.55,
                }}
              >
                {r.body}
              </p>
              {r.suggestion && (
                <div
                  className="bg-app border border-hx font-mono text-ok"
                  style={{
                    marginTop: 8,
                    padding: "8px 10px",
                    borderRadius: 6,
                    fontSize: 11.5,
                  }}
                >
                  {r.suggestion}
                </div>
              )}
              <div className="flex" style={{ gap: 6, marginTop: 8 }}>
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
      <div
        className="border-t border-hx bg-surface-hi"
        style={{ padding: 14 }}
      >
        <div className="eyebrow" style={{ marginBottom: 6 }}>
          ASK HELIX ABOUT THIS FILE
        </div>
        <label
          className="relative flex items-center"
          style={{
            height: 34,
            border: "1px solid var(--con-line)",
            borderRadius: 7,
            paddingLeft: 30,
            paddingRight: 10,
            background: "var(--con-surface)",
          }}
        >
          <Sparkles
            size={13}
            className="absolute"
            style={{ left: 10, color: "var(--con-brand)" }}
          />
          <input
            aria-label="Ask Helix about this migration step"
            placeholder="Explain this migration step…"
            className="bg-transparent border-0 outline-none focus-ring w-full text-ink"
            style={{ fontSize: 12.5, height: "100%" }}
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
      <div style={{ padding: "12px 32px 0" }}>
        <DemoBanner message="The IDE shows demo artifacts (migrate.py, ddl.sql, plan_v1.md). Upload or generate real artifacts to populate this workspace." />
      </div>
      {/* Custom page header (replaces PageHero for IDE layout) */}
      <div
        className="flex items-center justify-between border-b border-hx"
        style={{
          padding: "20px 32px 14px",
          gap: 16,
        }}
      >
        <div className="flex items-center" style={{ gap: 16 }}>
          <div>
            <div className="eyebrow">
              DEVELOPER WORKSPACE · MIGRATE.PY
            </div>
            <h1
              className="m-0"
              style={{
                margin: "4px 0 0",
                fontSize: 22,
                fontWeight: 500,
                letterSpacing: "-0.02em",
              }}
            >
              Review &amp; approve
            </h1>
          </div>
          <span
            style={{
              width: 1,
              height: 28,
              background: "var(--con-line-2)",
            }}
          />
          <ProjectSwitcher />
        </div>
        <div className="flex flex-wrap" style={{ gap: 8 }}>
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
        <div
          className="flex flex-col bg-surface overflow-hidden min-w-0"
          style={{ borderRight: "1px solid var(--con-line)" }}
        >
          <div
            className="border-b border-hx"
            style={{ padding: "12px 14px" }}
          >
            <div className="eyebrow" style={{ marginBottom: 8 }}>
              ARTIFACT EXPLORER
            </div>
            <label
              className="relative flex items-center"
              style={{
                height: 28,
                border: "1px solid var(--con-line)",
                borderRadius: 7,
                paddingLeft: 30,
                paddingRight: 8,
              }}
            >
              <Search
                size={13}
                className="absolute text-ink-4"
                style={{ left: 10 }}
              />
              <input
                aria-label="Search files"
                placeholder="Search files…"
                className="bg-transparent border-0 outline-none focus-ring w-full text-ink"
                style={{ fontSize: 12, height: "100%" }}
              />
            </label>
          </div>
          <div className="flex-1 overflow-y-auto">
            <Tree />
          </div>
          <div
            className="bg-surface-hi border-t border-hx"
            style={{ padding: "12px 14px" }}
          >
            <div className="eyebrow" style={{ marginBottom: 8 }}>
              VERSIONS · migrate.py
            </div>
            <div className="flex flex-col" style={{ gap: 1 }}>
              {VERSION_HISTORY.map((v) => (
                <div
                  key={v.v}
                  className="grid items-center"
                  style={{
                    gridTemplateColumns: "26px 1fr auto",
                    gap: 8,
                    padding: "5px 0",
                    fontSize: 11.5,
                  }}
                >
                  <span
                    className="font-mono font-semibold"
                    style={{
                      fontSize: 9.5,
                      padding: "1px 4px",
                      borderRadius: 3,
                      background: v.current
                        ? "var(--con-ink-1)"
                        : "var(--con-bg-2)",
                      color: v.current ? "#FFF" : "var(--con-ink-3)",
                      textAlign: "center",
                    }}
                  >
                    {v.v}
                  </span>
                  <div className="min-w-0">
                    <div
                      className="text-ink overflow-hidden whitespace-nowrap"
                      style={{
                        fontWeight: v.current ? 500 : 400,
                        fontSize: 11.5,
                        textOverflow: "ellipsis",
                      }}
                    >
                      {v.msg}
                    </div>
                    <div
                      className="font-mono text-ink-4"
                      style={{ fontSize: 10 }}
                    >
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
        <div
          className="bg-surface-hi overflow-hidden min-w-0"
          style={{ borderLeft: "1px solid var(--con-line)" }}
        >
          <AiReviewPane />
        </div>
        )}
      </div>
      </div>
    </AppShell>
  );
}
