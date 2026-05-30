"use client";

/**
 * BudgetsTab — per-agent or per-project spend budgets.
 *
 * Rows merge configured budgets (fetchBudgets) with observed spend
 * (UsageSummary.by_agent / by_project), so an admin sees current spend next to
 * each cap. Add/edit via a Modal; clear via a destructive ConfirmModal. All
 * data is real — no fabricated values; empty states when nothing exists.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus, Pencil, Trash2 } from "lucide-react";

import { Button, Card, Chip, EmptyState, ErrorBanner, ProgressBar, Modal, ConfirmModal, Table, THead, TBody, TR, TH, TD } from "@/components/ui";
import { AgentIcon } from "@/components/icons";
import {
  fetchBudgets, upsertBudget, deleteBudget, fetchKnownAgents,
  type CostBudget, type BudgetScope, type UsageSummary,
} from "@/lib/usage/api";

const fmtUsd = (v: number) => (v >= 1000 ? `$${(v / 1000).toFixed(2)}k` : `$${v.toFixed(2)}`);

interface Row {
  key: string;            // agent code or project_id
  label: string;
  spend: number;
  tokens?: number;
  calls?: number;
  budget?: CostBudget;
}

export function BudgetsTab({ scope, usage, token }: { scope: BudgetScope; usage: UsageSummary | null; token: string | null }) {
  const [budgets, setBudgets] = useState<CostBudget[]>([]);
  const [agents, setAgents] = useState<string[]>([]);
  const [err, setErr] = useState("");
  const [editing, setEditing] = useState<CostBudget | null>(null);
  const [adding, setAdding] = useState(false);
  const [confirmKey, setConfirmKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const b = await fetchBudgets(token, scope);
      setBudgets(b);
      if (scope === "agent") setAgents((await fetchKnownAgents(token)).agents);
      setErr("");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to load budgets");
    }
  }, [scope, token]);

  useEffect(() => { void load(); }, [load]);

  const rows: Row[] = useMemo(() => {
    const byKey = new Map<string, Row>();
    if (scope === "agent") {
      (usage?.by_agent ?? []).forEach((a) => byKey.set(a.agent, {
        key: a.agent, label: a.agent, spend: a.cost_usd,
        tokens: a.input_tokens + a.output_tokens, calls: a.call_count,
      }));
    } else {
      (usage?.by_project ?? []).forEach((p) => byKey.set(p.project_id, {
        key: p.project_id, label: p.project_id, spend: p.cost_usd,
      }));
    }
    budgets.forEach((b) => {
      const r = byKey.get(b.scope_key) ?? { key: b.scope_key, label: b.scope_key, spend: 0 };
      r.budget = b;
      byKey.set(b.scope_key, r);
    });
    return Array.from(byKey.values()).sort((a, b) => b.spend - a.spend);
  }, [scope, usage, budgets]);

  const onDelete = async () => {
    if (!confirmKey) return;
    setBusy(true);
    try {
      await deleteBudget(token, scope, confirmKey);
      setConfirmKey(null);
      await load();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  };

  const noun = scope === "agent" ? "agent" : "project";

  return (
    <Card
      title={scope === "agent" ? "Per-agent budgets" : "Per-project budgets"}
      description={`Cap spend for a single ${noun}. Evaluated at workflow start alongside the org cap.`}
      actions={<Button size="sm" onClick={() => setAdding(true)}><Plus className="h-3.5 w-3.5" /> Add budget</Button>}
      bodyClassName="p-0"
    >
      {err && <div className="p-3"><ErrorBanner message={err} onDismiss={() => setErr("")} /></div>}

      {rows.length === 0 ? (
        <div className="p-4">
          <EmptyState
            title={`No ${noun} budgets or spend yet`}
            description={`Add a budget to cap a specific ${noun}'s spend, or wait for usage to appear.`}
          />
        </div>
      ) : (
        <Table>
          <THead>
            <TR hover={false}>
              <TH>{scope === "agent" ? "Agent" : "Project"}</TH>
              <TH>30d spend</TH>
              {scope === "agent" && <TH>Tokens</TH>}
              {scope === "agent" && <TH>Calls</TH>}
              <TH>Daily cap</TH>
              <TH>Monthly cap</TH>
              <TH>Mode</TH>
              <TH>&nbsp;</TH>
            </TR>
          </THead>
          <TBody>
            {rows.map((r) => {
              const cap = r.budget?.monthly_usd_cap || 0;
              const pct = cap > 0 ? Math.min(100, (r.spend / cap) * 100) : 0;
              return (
                <TR key={r.key}>
                  <TD>
                    <div className="flex items-center gap-2">
                      {scope === "agent" && <AgentIcon name={r.key} size={20} />}
                      <span className="font-medium text-ink truncate max-w-[220px]" title={r.label}>{r.label}</span>
                    </div>
                  </TD>
                  <TD>
                    <div className="font-mono tabular-nums">{fmtUsd(r.spend)}</div>
                    {cap > 0 && <div className="mt-1 w-24"><ProgressBar value={pct} /></div>}
                  </TD>
                  {scope === "agent" && <TD className="font-mono tabular-nums text-ink-3">{(r.tokens ?? 0).toLocaleString()}</TD>}
                  {scope === "agent" && <TD className="font-mono tabular-nums text-ink-3">{r.calls ?? 0}</TD>}
                  <TD className="font-mono">{r.budget && r.budget.daily_usd_cap > 0 ? fmtUsd(r.budget.daily_usd_cap) : <span className="text-ink-4">—</span>}</TD>
                  <TD className="font-mono">{r.budget && r.budget.monthly_usd_cap > 0 ? fmtUsd(r.budget.monthly_usd_cap) : <span className="text-ink-4">—</span>}</TD>
                  <TD>{r.budget ? <Chip tone={r.budget.enforcement === "hard" ? "warn" : "default"}>{r.budget.enforcement}</Chip> : <span className="text-ink-4 text-[12px]">no budget</span>}</TD>
                  <TD>
                    <div className="flex items-center gap-1 justify-end">
                      <button type="button" aria-label="Edit budget" onClick={() => setEditing(r.budget ?? { scope, scope_key: r.key, daily_usd_cap: 0, monthly_usd_cap: 0, enforcement: "hard" })} className="p-1.5 rounded-md text-ink-4 hover:text-ink hover:bg-app-2">
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      {r.budget && (
                        <button type="button" aria-label="Clear budget" onClick={() => setConfirmKey(r.key)} className="p-1.5 rounded-md text-ink-4 hover:text-[var(--con-err)] hover:bg-app-2">
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      )}
                    </div>
                  </TD>
                </TR>
              );
            })}
          </TBody>
        </Table>
      )}

      {(adding || editing) && (
        <BudgetModal
          scope={scope}
          initial={editing}
          agents={agents}
          existingKeys={budgets.map((b) => b.scope_key)}
          token={token}
          onClose={() => { setAdding(false); setEditing(null); }}
          onSaved={async () => { setAdding(false); setEditing(null); await load(); }}
        />
      )}

      <ConfirmModal
        open={confirmKey !== null}
        onClose={() => setConfirmKey(null)}
        onConfirm={onDelete}
        title="Clear this budget?"
        description={`The ${noun} will fall back to the org-wide cap only.`}
        destructive
        busy={busy}
        confirmLabel="Clear budget"
      />
    </Card>
  );
}

function BudgetModal({ scope, initial, agents, existingKeys, token, onClose, onSaved }: {
  scope: BudgetScope;
  initial: CostBudget | null;
  agents: string[];
  existingKeys: string[];
  token: string | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = !!initial?.scope_key && existingKeys.includes(initial.scope_key);
  const [scopeKey, setScopeKey] = useState(initial?.scope_key ?? "");
  const [daily, setDaily] = useState(String(initial?.daily_usd_cap ?? 0));
  const [monthly, setMonthly] = useState(String(initial?.monthly_usd_cap ?? 0));
  const [enforcement, setEnforcement] = useState<"hard" | "soft">(initial?.enforcement ?? "hard");
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

  const save = async () => {
    if (!scopeKey.trim()) { setErr(`Choose a ${scope}.`); return; }
    const dn = Number(daily), mn = Number(monthly);
    if (!Number.isFinite(dn) || dn < 0 || !Number.isFinite(mn) || mn < 0) { setErr("Caps must be non-negative."); return; }
    setSaving(true); setErr("");
    try {
      await upsertBudget(token, { scope, scope_key: scopeKey.trim(), daily_usd_cap: dn, monthly_usd_cap: mn, enforcement });
      onSaved();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open onClose={onClose} title={isEdit ? "Edit budget" : "Add budget"} width="sm">
      <div className="space-y-4">
        {err && <ErrorBanner message={err} onDismiss={() => setErr("")} />}
        <label className="flex flex-col gap-1.5">
          <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">{scope === "agent" ? "Agent" : "Project ID"}</span>
          {scope === "agent" ? (
            <select value={scopeKey} onChange={(e) => setScopeKey(e.target.value)} disabled={isEdit}
              className="h-9 px-2.5 text-[13px] rounded-[8px] border border-hx bg-surface focus-ring disabled:opacity-60">
              <option value="">— Select agent —</option>
              {agents.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          ) : (
            <input value={scopeKey} onChange={(e) => setScopeKey(e.target.value)} disabled={isEdit} placeholder="project uuid"
              className="h-9 px-2.5 text-[13px] rounded-[8px] border border-hx bg-surface focus-ring font-mono disabled:opacity-60" />
          )}
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="flex flex-col gap-1.5">
            <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">Daily cap ($)</span>
            <input type="number" step="0.01" min="0" value={daily} onChange={(e) => setDaily(e.target.value)}
              className="h-9 px-2.5 text-[13px] rounded-[8px] border border-hx bg-surface focus-ring font-mono" />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">Monthly cap ($)</span>
            <input type="number" step="0.01" min="0" value={monthly} onChange={(e) => setMonthly(e.target.value)}
              className="h-9 px-2.5 text-[13px] rounded-[8px] border border-hx bg-surface focus-ring font-mono" />
          </label>
        </div>
        <label className="flex flex-col gap-1.5">
          <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">Enforcement</span>
          <select value={enforcement} onChange={(e) => setEnforcement(e.target.value as "hard" | "soft")}
            className="h-9 px-2.5 text-[13px] rounded-[8px] border border-hx bg-surface focus-ring">
            <option value="hard">Hard — refuse over-cap workflows</option>
            <option value="soft">Soft — warn only</option>
          </select>
        </label>
        <p className="text-[11.5px] text-ink-4">A cap of 0 disables that window. Budgets are checked at workflow start.</p>
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} loading={saving}>Save budget</Button>
        </div>
      </div>
    </Modal>
  );
}
