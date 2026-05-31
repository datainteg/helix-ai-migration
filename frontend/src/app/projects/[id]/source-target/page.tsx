"use client";

/**
 * /projects/[id]/source-target — configure the project's source & target
 * database connections. This is the foundation for running a migration: the
 * SchemaAnalyst agent introspects the real source from these credentials, so
 * the AI discovers all schemas/tables/types itself (you don't hand-type them).
 *
 * Add connection (credentials per connector) → Test → Discover schemas.
 */

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Plus, Plug, Trash2, CheckCircle2, Database, Search } from "lucide-react";

import { ProjectShell } from "@/components/layout/ProjectShell";
import { Card, Button, Chip, StatusBadge, EmptyState, ErrorBanner, Modal } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import { useRegisterCrumbLabel } from "@/lib/breadcrumbs";
import { useProjectKey } from "@/lib/projects/useProjectKey";
import {
  listConnections, addConnection, deleteConnection, testConnection, discoverSchemas,
  CONNECTOR_FIELDS, CONNECTOR_LABELS, type Connection, type ConnSide, type FieldDef,
} from "@/lib/projects/connections";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface MigTypeSpec { value: string; label: string; source_kinds: string[]; target_kinds: string[]; }

export default function SourceTargetPage() {
  const projectKey = String(useParams<{ id: string }>().id);
  const { id } = useProjectKey(projectKey);
  const { can } = useAuth();
  const canWrite = can("project:write");
  const [projectName, setProjectName] = useState("Loading…");
  const [migType, setMigType] = useState("db_to_db");
  const [typeSpecs, setTypeSpecs] = useState<MigTypeSpec[]>([]);
  const [connKinds, setConnKinds] = useState<Record<string, string>>({});

  useRegisterCrumbLabel(projectKey, projectName !== "Loading…" ? projectName : undefined);
  useEffect(() => {
    if (!id) return;
    fetch(`${API_BASE}/api/v1/projects/${id}`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((p) => { setProjectName(p?.name || "Project"); if (p?.migration_type) setMigType(p.migration_type); })
      .catch(() => setProjectName("Project"));
    fetch(`${API_BASE}/api/v1/migration-types`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d) { setTypeSpecs(d.types || []); setConnKinds(d.connector_kinds || {}); } })
      .catch(() => {});
  }, [id]);

  const spec = typeSpecs.find((t) => t.value === migType);
  // Connectors valid for a side = those whose kind is allowed by the type.
  const connectorsFor = (kinds: string[] | undefined) =>
    Object.keys(CONNECTOR_FIELDS).filter((ct) => !kinds || kinds.includes(connKinds[ct] ?? "db"));
  const sourceTypes = connectorsFor(spec?.source_kinds);
  const targetTypes = connectorsFor(spec?.target_kinds);
  const sourceIsFile = (spec?.source_kinds ?? ["db"]).every((k) => k === "file");

  return (
    <ProjectShell
      projectId={projectKey}
      projectName={projectName}
      subtitle={`Connect the source and target for this ${spec?.label ?? "migration"}. The agents read the source structure from here.`}
    >
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ConnPanel projectId={id} side="source" canWrite={canWrite} allowed={sourceTypes} discoverLabel={sourceIsFile ? "Infer schema from files" : "Introspect schema"} />
        <ConnPanel projectId={id} side="target" canWrite={canWrite} allowed={targetTypes} discoverLabel="Introspect schema" />
      </div>
    </ProjectShell>
  );
}

function ConnPanel({ projectId, side, canWrite, allowed, discoverLabel }: { projectId: string; side: ConnSide; canWrite: boolean; allowed: string[]; discoverLabel: string }) {
  const [conns, setConns] = useState<Connection[] | null>(null);
  const [err, setErr] = useState("");
  const [adding, setAdding] = useState(false);
  const [busyId, setBusyId] = useState<string>("");
  const [testMsg, setTestMsg] = useState<Record<string, { ok: boolean; text: string }>>({});

  const load = () => listConnections(projectId, side).then(setConns).catch(() => setConns([]));
  useEffect(() => { if (!projectId) return; load(); /* eslint-disable-next-line */ }, [projectId, side]);

  const onTest = async (c: Connection) => {
    setBusyId(c.id); setErr("");
    try { const r = await testConnection(projectId, side, c.id); setTestMsg((m) => ({ ...m, [c.id]: { ok: r.success, text: r.message } })); }
    catch (e: unknown) { setTestMsg((m) => ({ ...m, [c.id]: { ok: false, text: e instanceof Error ? e.message : "Test failed" } })); }
    finally { setBusyId(""); }
  };
  const onDiscover = async (c: Connection) => {
    setBusyId(c.id); setErr("");
    try { await discoverSchemas(projectId, side, c.id); setTestMsg((m) => ({ ...m, [c.id]: { ok: true, text: "Schemas discovered — see the project Overview." } })); }
    catch (e: unknown) { setErr(e instanceof Error ? e.message : "Discovery failed"); }
    finally { setBusyId(""); }
  };
  const onDelete = async (c: Connection) => {
    setBusyId(c.id);
    try { await deleteConnection(projectId, side, c.id); load(); }
    catch (e: unknown) { setErr(e instanceof Error ? e.message : "Delete failed"); }
    finally { setBusyId(""); }
  };

  const label = side === "source" ? "Source" : "Target";
  return (
    <Card
      title={`${label} connection`}
      description={side === "source" ? "Where data is migrated FROM (introspected by the agents)" : "Where data is migrated TO"}
      actions={canWrite ? <Button size="sm" onClick={() => setAdding(true)}><Plus className="h-3.5 w-3.5" /> Add</Button> : undefined}
    >
      {err && <div className="mb-3"><ErrorBanner message={err} onDismiss={() => setErr("")} /></div>}
      {conns === null ? (
        <p className="text-[12.5px] text-ink-4">Loading…</p>
      ) : conns.length === 0 ? (
        <EmptyState icon={<Database className="h-4 w-4" />} title={`No ${side} connection`} description={`Add a ${side} database so the migration can ${side === "source" ? "read" : "write"} it.`} />
      ) : (
        <div className="flex flex-col gap-3">
          {conns.map((c) => (
            <div key={c.id} className="rounded-[10px] border border-hx p-3">
              <div className="flex items-center gap-2.5">
                <span className="grid place-items-center h-8 w-8 rounded-lg bg-app-2 text-ink-3"><Plug className="h-4 w-4" /></span>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-medium text-ink truncate">{c.name}</div>
                  <div className="text-[11px] text-ink-4 font-mono">{CONNECTOR_LABELS[c.connector_type] ?? c.connector_type} · {c.config_masked || "—"}</div>
                </div>
                <StatusBadge status={c.status} />
              </div>
              {testMsg[c.id] && (
                <div className={`mt-2 flex items-center gap-1.5 text-[12px] ${testMsg[c.id].ok ? "text-[var(--con-ok)]" : "text-[var(--con-err)]"}`}>
                  <CheckCircle2 className="h-3.5 w-3.5" /> {testMsg[c.id].text}
                </div>
              )}
              {canWrite && (
                <div className="mt-2.5 flex gap-2">
                  <Button size="sm" variant="outline" loading={busyId === c.id} onClick={() => onTest(c)}><CheckCircle2 className="h-3.5 w-3.5" /> Test</Button>
                  <Button size="sm" variant="outline" loading={busyId === c.id} onClick={() => onDiscover(c)}><Search className="h-3.5 w-3.5" /> {discoverLabel}</Button>
                  <Button size="sm" variant="ghost" onClick={() => onDelete(c)} aria-label="Delete connection"><Trash2 className="h-3.5 w-3.5" /></Button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {adding && (
        <AddConnectionModal projectId={projectId} side={side} allowed={allowed} onClose={() => setAdding(false)} onSaved={() => { setAdding(false); load(); }} />
      )}
    </Card>
  );
}

function AddConnectionModal({ projectId, side, allowed, onClose, onSaved }: { projectId: string; side: ConnSide; allowed: string[]; onClose: () => void; onSaved: () => void }) {
  const types = allowed.length ? allowed : Object.keys(CONNECTOR_FIELDS);
  const [type, setType] = useState(types[0]);
  const [name, setName] = useState("");
  const [cfg, setCfg] = useState<Record<string, string>>({});
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

  const fields: FieldDef[] = CONNECTOR_FIELDS[type] ?? [];
  const setField = (k: string, v: string) => setCfg((c) => ({ ...c, [k]: v }));

  const save = async () => {
    if (!name.trim()) { setErr("Name the connection."); return; }
    setSaving(true); setErr("");
    try {
      const config: Record<string, unknown> = {};
      for (const f of fields) {
        const v = cfg[f.key];
        if (v != null && v !== "") config[f.key] = f.type === "number" ? Number(v) : v;
      }
      await addConnection(projectId, side, { name: name.trim(), connector_type: type, config });
      onSaved();
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Save failed"); }
    finally { setSaving(false); }
  };

  const inputCls = "h-9 px-2.5 text-[13px] rounded-[8px] border border-hx bg-surface focus-ring w-full";
  return (
    <Modal open onClose={onClose} title={`Add ${side} connection`} width="md">
      <div className="space-y-4">
        {err && <ErrorBanner message={err} onDismiss={() => setErr("")} />}
        <div className="grid grid-cols-2 gap-3">
          <label className="flex flex-col gap-1.5">
            <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">Connector</span>
            <select value={type} onChange={(e) => { setType(e.target.value); setCfg({}); }} className={inputCls}>
              {types.map((t) => <option key={t} value={t}>{CONNECTOR_LABELS[t] ?? t}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">Name</span>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder={`${side} db`} className={inputCls} />
          </label>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {fields.map((f) => (
            <label key={f.key} className="flex flex-col gap-1.5">
              <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">{f.label}</span>
              <input type={f.type === "password" ? "password" : f.type === "number" ? "number" : "text"}
                value={cfg[f.key] ?? ""} onChange={(e) => setField(f.key, e.target.value)} placeholder={f.placeholder}
                className={inputCls} />
            </label>
          ))}
        </div>
        <p className="text-[11.5px] text-ink-4">Credentials are encrypted server-side and never returned. After saving, click <strong>Test</strong> then <strong>Discover schemas</strong>.</p>
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} loading={saving}>Save connection</Button>
        </div>
      </div>
    </Modal>
  );
}
