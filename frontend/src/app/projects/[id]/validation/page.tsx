"use client";

/**
 * /projects/[id]/validation — data-validation runs & rules.
 *
 * Shows the latest validation run summary (pass/fail counts + pass %), a table
 * of per-rule results, and the list of validation rules defined for the
 * project. "Run validation" (project:write) POSTs a new run then polls its
 * detail until it settles.
 *
 * Backend note (backend/app/api/validation.py): there is NO list-runs
 * endpoint — runs are addressable only by id. So the "latest run" we can
 * display is the one started/seen in this browser; we persist its id in
 * localStorage so a refresh re-fetches the same run's detail. On first visit
 * with no run yet we honestly show an EmptyState and the rules list.
 */

import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Play, ClipboardCheck, ListChecks, CheckCircle2, XCircle } from "lucide-react";

import { ProjectShell } from "@/components/layout/ProjectShell";
import {
  Card, Button, Chip, StatusBadge, EmptyState, ErrorBanner, LoadingState,
  MetricCard, Table, THead, TBody, TR, TH, TD,
} from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import { useRegisterCrumbLabel } from "@/lib/breadcrumbs";
import { useProjectKey } from "@/lib/projects/useProjectKey";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface RuleSummary { id: string; rule_type: string; target_ref: string | null; status: string | null; }
interface ResultRow { rule_id: string | null; status: string | null; observed: string | null; expected: string | null; }
interface RunDetail { id: string; status: string; results: ResultRow[]; }

const TERMINAL = new Set(["completed", "failed", "error"]);

export default function ProjectValidationPage() {
  const projectKey = String(useParams<{ id: string }>().id);
  const { id } = useProjectKey(projectKey);
  const { can } = useAuth();
  const canWrite = can("project:write");

  const [projectName, setProjectName] = useState("Project");
  const [projectStatus, setProjectStatus] = useState("draft");
  const [onHold, setOnHold] = useState(false);

  const [rules, setRules] = useState<RuleSummary[] | null>(null);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [loadingRun, setLoadingRun] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");

  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useRegisterCrumbLabel(projectKey, projectName !== "Project" ? projectName : undefined);

  // Real project name + status for the ProjectShell header + breadcrumb.
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
  }, [id]);

  // Rule labels for mapping result.rule_id → human ref.
  const ruleById = (rid: string | null) => (rid ? rules?.find((r) => r.id === rid) : undefined);

  const loadRules = useCallback(() => {
    if (!id) return;
    fetch(`${API_BASE}/api/v1/projects/${id}/validation-rules?limit=200`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setRules(d?.items ?? []))
      .catch(() => setRules([]));
  }, [id]);

  const fetchRun = useCallback(
    async (runId: string, poll = false) => {
      if (!id || !runId) return;
      setLoadingRun(true);
      try {
        const res = await fetch(`${API_BASE}/api/v1/projects/${id}/validation-runs/${runId}`, {
          credentials: "include",
        });
        if (res.status === 404) {
          // The persisted run no longer exists — clear it honestly.
          window.localStorage.removeItem(`helix:validation-run:${id}`);
          setRun(null);
          return;
        }
        if (!res.ok) throw new Error(`Could not load run (${res.status})`);
        const detail: RunDetail = await res.json();
        setRun(detail);
        if (poll && !TERMINAL.has(detail.status.toLowerCase())) {
          pollRef.current = setTimeout(() => void fetchRun(runId, true), 2000);
        }
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Could not load validation run");
      } finally {
        setLoadingRun(false);
      }
    },
    [id]
  );

  // Initial load: rules + re-hydrate the last run id from localStorage.
  useEffect(() => {
    if (!id) return;
    loadRules();
    const last = window.localStorage.getItem(`helix:validation-run:${id}`);
    if (last) void fetchRun(last, true);
    return () => { if (pollRef.current) clearTimeout(pollRef.current); };
  }, [id, loadRules, fetchRun]);

  const runValidation = async () => {
    if (!id) return;
    setStarting(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/v1/projects/${id}/validation-runs`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ connector_configs: {} }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(d.detail || `Run failed to start (${res.status})`);
      }
      const started: { id: string; status: string; rule_count: number } = await res.json();
      window.localStorage.setItem(`helix:validation-run:${id}`, started.id);
      if (pollRef.current) clearTimeout(pollRef.current);
      await fetchRun(started.id, true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Run failed to start");
    } finally {
      setStarting(false);
    }
  };

  // Derived run summary.
  const results = run?.results ?? [];
  const passCount = results.filter((r) => (r.status || "").toLowerCase() === "pass" || (r.status || "").toLowerCase() === "passed").length;
  const failCount = results.filter((r) => (r.status || "").toLowerCase() === "fail" || (r.status || "").toLowerCase() === "failed").length;
  const total = results.length;
  const passPct = total > 0 ? Math.round((passCount / total) * 100) : 0;

  const runAction = canWrite ? (
    <Button size="sm" onClick={() => void runValidation()} loading={starting}>
      <Play className="h-3.5 w-3.5" /> Run validation
    </Button>
  ) : undefined;

  return (
    <ProjectShell
      projectId={projectKey}
      projectName={projectName}
      projectStatus={projectStatus}
      onHold={onHold}
      subtitle="Run the project's validation rules and inspect per-rule pass/fail results."
      actions={runAction}
    >
      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      <div className="flex flex-col gap-4">
        {/* Latest run summary */}
        <Card
          title={<span className="flex items-center gap-2"><ClipboardCheck className="h-4 w-4 text-[var(--con-brand)]" /> Latest validation run</span>}
          description={run ? `Run ${run.id.slice(0, 8)} · ${total} ${total === 1 ? "result" : "results"}` : undefined}
          actions={run ? <StatusBadge status={run.status} /> : undefined}
        >
          {!run && loadingRun ? (
            <LoadingState label="Loading run…" />
          ) : !run ? (
            <EmptyState
              icon={<ClipboardCheck className="h-4 w-4" />}
              title="No validation run yet"
              description={
                canWrite
                  ? "Start a run to validate the project's rules against the target. Results will appear here."
                  : "No validation has been run for this project yet."
              }
              action={runAction}
            />
          ) : (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <MetricCard label="Pass rate" value={`${passPct}%`} accent={failCount > 0 ? "var(--con-warn)" : "var(--con-ok)"} hint={`${total} ${total === 1 ? "rule" : "rules"} checked`} />
                <MetricCard label="Passed" value={passCount} accent="var(--con-ok)" />
                <MetricCard label="Failed" value={failCount} accent={failCount > 0 ? "var(--con-err)" : undefined} />
                <MetricCard label="Total" value={total} />
              </div>
              {!TERMINAL.has(run.status.toLowerCase()) && (
                <p className="mt-3 text-[12px] text-ink-3 flex items-center gap-2">
                  <LoadingState label={`Run ${run.status} — refreshing…`} className="py-0" />
                </p>
              )}

              {/* Per-rule results table */}
              <div className="mt-4">
                {total === 0 ? (
                  <EmptyState
                    icon={<ListChecks className="h-4 w-4" />}
                    title={TERMINAL.has(run.status.toLowerCase()) ? "No results recorded" : "Awaiting results"}
                    description={
                      TERMINAL.has(run.status.toLowerCase())
                        ? "This run produced no per-rule results. Add active validation rules then run again."
                        : "The run is in progress — per-rule results will populate as it completes."
                    }
                  />
                ) : (
                  <div className="rounded-[10px] border border-hx overflow-hidden">
                    <Table>
                      <THead>
                        <TR>
                          <TH>Rule</TH>
                          <TH>Target</TH>
                          <TH>Expected</TH>
                          <TH>Observed</TH>
                          <TH align="right">Status</TH>
                        </TR>
                      </THead>
                      <TBody>
                        {results.map((res, i) => {
                          const rule = ruleById(res.rule_id);
                          const ok = (res.status || "").toLowerCase().startsWith("pass");
                          return (
                            <TR key={`${res.rule_id}-${i}`} hover>
                              <TD>
                                <span className="text-[12.5px] text-ink font-medium">{rule?.rule_type ?? "—"}</span>
                              </TD>
                              <TD mono>
                                <span className="text-[11.5px] text-ink-3">{rule?.target_ref || "—"}</span>
                              </TD>
                              <TD mono><span className="text-[11.5px] text-ink-3">{res.expected ?? "—"}</span></TD>
                              <TD mono><span className="text-[11.5px] text-ink-3">{res.observed ?? "—"}</span></TD>
                              <TD align="right">
                                <span className={`inline-flex items-center gap-1.5 text-[12px] ${ok ? "text-[var(--con-ok)]" : "text-[var(--con-err)]"}`}>
                                  {ok ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
                                  {res.status ? res.status.charAt(0).toUpperCase() + res.status.slice(1) : "—"}
                                </span>
                              </TD>
                            </TR>
                          );
                        })}
                      </TBody>
                    </Table>
                  </div>
                )}
              </div>
            </>
          )}
        </Card>

        {/* Validation rules */}
        <Card
          title={<span className="flex items-center gap-2"><ListChecks className="h-4 w-4 text-ink-3" /> Validation rules</span>}
          description="Rules the migration is checked against. Only active rules run during a validation."
          actions={rules ? <Chip tone="default">{rules.length} {rules.length === 1 ? "rule" : "rules"}</Chip> : undefined}
        >
          {rules === null ? (
            <LoadingState label="Loading rules…" />
          ) : rules.length === 0 ? (
            <EmptyState
              icon={<ListChecks className="h-4 w-4" />}
              title="No validation rules"
              description="No validation rules are defined for this project yet. A run with no rules completes immediately with no results."
            />
          ) : (
            <div className="rounded-[10px] border border-hx overflow-hidden">
              <Table>
                <THead>
                  <TR>
                    <TH>Rule type</TH>
                    <TH>Target</TH>
                    <TH align="right">Status</TH>
                  </TR>
                </THead>
                <TBody>
                  {rules.map((r) => (
                    <TR key={r.id} hover>
                      <TD><span className="text-[12.5px] text-ink font-medium">{r.rule_type}</span></TD>
                      <TD mono><span className="text-[11.5px] text-ink-3">{r.target_ref || "—"}</span></TD>
                      <TD align="right"><StatusBadge status={r.status || "active"} /></TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </div>
          )}
        </Card>
      </div>
    </ProjectShell>
  );
}
