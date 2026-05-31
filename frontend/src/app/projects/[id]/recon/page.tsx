"use client";

/**
 * /projects/[id]/recon — Reconciliation.
 *
 * Row-count reconciliation between the migrated source and target tables. The
 * page surfaces the project's REAL recon rollup (verified % = clean table
 * results / total, read from the project overview) and lets an operator with
 * `project:write` trigger a fresh row-count recon for a source/target table
 * pair via POST /projects/{id}/recon-runs.
 *
 * Honesty rules: the backend exposes recon data two ways and ONLY these — the
 * aggregate rollup on /projects/{id}/overview ({recon:{pct,total}}) and the
 * single per-pair result returned by the POST. There is no GET that lists
 * historical per-table recon rows, so we never fabricate a history table; we
 * show the live rollup plus the results from runs triggered in this session.
 */

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { GitCompareArrows, Play, CheckCircle2 } from "lucide-react";

import { ProjectShell } from "@/components/layout/ProjectShell";
import {
  Button, Card, Chip, StatusBadge, EmptyState, ErrorBanner, LoadingState,
  ProgressBar, Table, THead, TBody, TR, TH, TD,
} from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import { useRegisterCrumbLabel } from "@/lib/breadcrumbs";
import { useProjectKey } from "@/lib/projects/useProjectKey";
import {
  CONNECTOR_FIELDS, CONNECTOR_LABELS, type FieldDef,
} from "@/lib/projects/connections";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface ReconRollup { pct: number | null; total: number }

// Shape returned by POST /projects/{id}/recon-runs on success — maps the real
// fields from run_row_count_recon().
interface ReconRunResult {
  recon_run_id: string;
  status: string;
  source_count?: number;
  target_count?: number;
  difference?: number;
  passed?: boolean;
  source_ref?: string;
  target_ref?: string;
}

const fmt = (n: number | undefined | null) =>
  n == null ? "—" : n.toLocaleString();

export default function ProjectReconPage() {
  const projectKey = String(useParams<{ id: string }>().id);
  const { id } = useProjectKey(projectKey);
  const { can } = useAuth();
  const canWrite = can("project:write");

  const [projectName, setProjectName] = useState("Project");
  const [projectStatus, setProjectStatus] = useState("draft");
  const [onHold, setOnHold] = useState(false);

  const [rollup, setRollup] = useState<ReconRollup | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Per-pair results from recon runs triggered in this session (real POST
  // responses — the only per-table recon detail the API exposes).
  const [results, setResults] = useState<ReconRunResult[]>([]);

  useRegisterCrumbLabel(projectKey, projectName !== "Project" ? projectName : undefined);

  const loadOverview = useCallback(() => {
    if (!id) return Promise.resolve();
    return fetch(`${API_BASE}/api/v1/projects/${id}/overview`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d?.recon) setRollup({ pct: d.recon.pct ?? null, total: d.recon.total ?? 0 });
        else setRollup({ pct: null, total: 0 });
      })
      .catch(() => setError("Could not load the reconciliation rollup."));
  }, [id]);

  useEffect(() => {
    if (!id) return;
    fetch(`${API_BASE}/api/v1/projects/${id}`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((p) => {
        setProjectName(p?.name || "Project");
        if (p?.status) setProjectStatus(p.status);
        setOnHold(!!p?.on_hold);
      })
      .catch(() => setProjectName("Project"));
    loadOverview().finally(() => setLoading(false));
  }, [id, loadOverview]);

  const total = rollup?.total ?? 0;
  const pct = rollup?.pct;
  const cleanTables = pct != null ? Math.round((pct / 100) * total) : 0;
  const pctTone = pct == null ? "ink" : pct >= 100 ? "ok" : pct >= 80 ? "warn" : "err";

  const onRan = (res: ReconRunResult) => {
    setResults((prev) => [res, ...prev]);
    void loadOverview();
  };

  return (
    <ProjectShell
      projectId={projectKey}
      projectName={projectName}
      projectStatus={projectStatus as any}
      onHold={onHold}
      subtitle="Row-count reconciliation between the migrated source and target tables."
    >
      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      <div className="flex items-center gap-4 text-[12.5px]">
        <a href={`/projects/${projectKey}/recon/reports`} className="text-helix-700 hover:underline">Recon Agent &amp; business reports →</a>
      </div>

      {loading ? (
        <LoadingState label="Loading reconciliation…" />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.1fr] gap-4">
          {/* ── Verified rollup ── */}
          <Card
            title={
              <span className="flex items-center gap-2">
                <GitCompareArrows className="h-4 w-4 text-[var(--con-brand)]" /> Verified
              </span>
            }
            description="Clean tables (zero row-count mismatch) over all reconciled table results for this project."
          >
            {total === 0 ? (
              <EmptyState
                icon={<GitCompareArrows className="h-4 w-4" />}
                title="No reconciliation yet"
                description="Run a row-count reconciliation against a migrated source/target table pair. Results land here as a verified percentage."
              />
            ) : (
              <div>
                <div className="flex items-baseline gap-2">
                  <span className="text-[34px] leading-none font-semibold text-ink tabular-nums">
                    {pct != null ? `${pct}%` : "—"}
                  </span>
                  <span className="text-[12.5px] text-ink-3">verified</span>
                </div>
                <div className="mt-3">
                  <ProgressBar value={pct ?? 0} tone={pctTone as any} height={6} />
                </div>
                <div className="mt-3 flex items-center gap-2 text-[12.5px] text-ink-3">
                  <Chip tone="ok">{cleanTables} matched</Chip>
                  {total - cleanTables > 0 && (
                    <Chip tone="err">{total - cleanTables} with mismatch</Chip>
                  )}
                  <span className="text-ink-4">· {total} table result{total === 1 ? "" : "s"}</span>
                </div>
              </div>
            )}
          </Card>

          {/* ── Run reconciliation ── */}
          <ReconRunner
            projectId={id}
            canWrite={canWrite}
            onRan={onRan}
            onError={setError}
          />
        </div>
      )}

      {!loading && (
        <div className="mt-4">
          <Card
            title="Recon results"
            description="Per-table row-count comparisons from runs triggered here. The API does not expose a historical per-table list, so only this session's runs and the rollup above are shown."
          >
            {results.length === 0 ? (
              <EmptyState
                icon={<GitCompareArrows className="h-4 w-4" />}
                title="No recon results in this session"
                description="Trigger a reconciliation to compare source and target row counts for a table."
              />
            ) : (
              <Table>
                <THead>
                  <TR>
                    <TH>Table pair</TH>
                    <TH className="text-right">Source rows</TH>
                    <TH className="text-right">Target rows</TH>
                    <TH className="text-right">Mismatch</TH>
                    <TH>Result</TH>
                  </TR>
                </THead>
                <TBody>
                  {results.map((r) => {
                    const clean = r.passed === true || r.difference === 0;
                    return (
                      <TR key={r.recon_run_id}>
                        <TD>
                          <div className="font-mono text-[12px] text-ink-2">
                            {r.source_ref || "source"}
                          </div>
                          <div className="font-mono text-[11px] text-ink-4">
                            → {r.target_ref || "target"}
                          </div>
                        </TD>
                        <TD className="text-right tabular-nums">{fmt(r.source_count)}</TD>
                        <TD className="text-right tabular-nums">{fmt(r.target_count)}</TD>
                        <TD className="text-right tabular-nums">{fmt(r.difference)}</TD>
                        <TD>
                          <StatusBadge status={r.status === "failed" ? "failed" : clean ? "matched" : "mismatch"} />
                        </TD>
                      </TR>
                    );
                  })}
                </TBody>
              </Table>
            )}
          </Card>
        </div>
      )}
    </ProjectShell>
  );
}

/**
 * Run reconciliation form. The POST endpoint builds the connector directly
 * from the supplied config (it does NOT read a saved, encrypted connection),
 * so the operator supplies the connector type, credentials, schema and table
 * for both sides here. On success we surface the real returned counts.
 */
function ReconRunner({
  projectId, canWrite, onRan, onError,
}: {
  projectId: string;
  canWrite: boolean;
  onRan: (r: ReconRunResult) => void;
  onError: (m: string) => void;
}) {
  const [running, setRunning] = useState(false);
  const [src, setSrc] = useState({ connector_type: "postgres", schema: "public", table: "", cfg: {} as Record<string, string> });
  const [tgt, setTgt] = useState({ connector_type: "postgres", schema: "public", table: "", cfg: {} as Record<string, string> });

  if (!canWrite) {
    return (
      <Card title="Run reconciliation">
        <p className="text-[12.5px] text-ink-3 leading-relaxed">
          Running reconciliation requires the <code className="font-mono text-[11.5px]">project:write</code> permission.
        </p>
      </Card>
    );
  }

  const buildSide = (s: typeof src) => {
    const fields: FieldDef[] = CONNECTOR_FIELDS[s.connector_type] ?? [];
    const config: Record<string, unknown> = {};
    for (const f of fields) {
      const v = s.cfg[f.key];
      if (v != null && v !== "") config[f.key] = f.type === "number" ? Number(v) : v;
    }
    return { connector_type: s.connector_type, config, schema: s.schema, table: s.table };
  };

  const run = async () => {
    if (!src.table.trim() || !tgt.table.trim()) {
      onError("Enter a source and target table to reconcile.");
      return;
    }
    setRunning(true);
    onError("");
    try {
      const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/recon-runs`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: buildSide(src), target: buildSide(tgt) }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({ detail: res.statusText }));
        const msg = typeof d.detail === "object" ? (d.detail.error || d.detail.message) : d.detail;
        throw new Error(msg || `Reconciliation failed (${res.status})`);
      }
      const data = (await res.json()) as ReconRunResult;
      onRan({
        ...data,
        source_ref: `${src.connector_type}:${src.schema}.${src.table}`,
        target_ref: `${tgt.connector_type}:${tgt.schema}.${tgt.table}`,
      });
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : "Reconciliation failed");
    } finally {
      setRunning(false);
    }
  };

  return (
    <Card
      title="Run reconciliation"
      description="Compare live row counts for a source/target table pair. Credentials are sent over the request and used only for the count query."
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <SidePanel label="Source" side={src} setSide={setSrc} />
        <SidePanel label="Target" side={tgt} setSide={setTgt} />
      </div>
      <div className="mt-4 flex items-center gap-2">
        <Button onClick={() => void run()} loading={running}>
          <Play className="h-3.5 w-3.5" /> Run reconciliation
        </Button>
        <span className="flex items-center gap-1.5 text-[11.5px] text-ink-4">
          <CheckCircle2 className="h-3.5 w-3.5" /> Row counts only — no production rows leave the connector.
        </span>
      </div>
    </Card>
  );
}

function SidePanel({
  label, side, setSide,
}: {
  label: string;
  side: { connector_type: string; schema: string; table: string; cfg: Record<string, string> };
  setSide: (s: { connector_type: string; schema: string; table: string; cfg: Record<string, string> }) => void;
}) {
  const fields: FieldDef[] = CONNECTOR_FIELDS[side.connector_type] ?? [];
  const inputCls = "h-9 px-2.5 text-[13px] rounded-[8px] border border-hx bg-surface focus-ring w-full";
  const set = (patch: Partial<typeof side>) => setSide({ ...side, ...patch });
  const setCfg = (k: string, v: string) => setSide({ ...side, cfg: { ...side.cfg, [k]: v } });

  return (
    <div className="rounded-[10px] border border-hx p-3">
      <div className="text-[10px] uppercase tracking-wider font-mono text-ink-4 mb-2.5">{label}</div>
      <div className="grid grid-cols-2 gap-2.5">
        <label className="flex flex-col gap-1.5 col-span-2">
          <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">Connector</span>
          <select
            value={side.connector_type}
            onChange={(e) => set({ connector_type: e.target.value, cfg: {} })}
            className={inputCls}
          >
            {Object.keys(CONNECTOR_FIELDS).map((t) => (
              <option key={t} value={t}>{CONNECTOR_LABELS[t] ?? t}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">Schema</span>
          <input value={side.schema} onChange={(e) => set({ schema: e.target.value })} placeholder="public" className={inputCls} />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">Table</span>
          <input value={side.table} onChange={(e) => set({ table: e.target.value })} placeholder="orders" className={inputCls} />
        </label>
        {fields.map((f) => (
          <label key={f.key} className="flex flex-col gap-1.5">
            <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">{f.label}</span>
            <input
              type={f.type === "password" ? "password" : f.type === "number" ? "number" : "text"}
              value={side.cfg[f.key] ?? ""}
              onChange={(e) => setCfg(f.key, e.target.value)}
              placeholder={f.placeholder}
              className={inputCls}
            />
          </label>
        ))}
      </div>
    </div>
  );
}
