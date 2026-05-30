"use client";

/**
 * /admin/roles — RBAC roles + permissions.
 *
 * System roles (admin, viewer, …) are protected: shown read-only. Admins can
 * create custom roles and toggle their permissions. Backed by /admin/roles
 * (gated by admin:roles:read/write). Shows an "admins only" state on 403.
 */

import { useEffect, useState } from "react";
import { Check, Lock, Plus, Trash2, Pencil, ShieldCheck } from "lucide-react";

import { AppShell } from "@/components/layout";
import { Card, Chip, Button, ErrorBanner, LoadingState, EmptyState, Modal, ConfirmModal, Table, THead, TBody, TR, TH, TD } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import {
  fetchRoles, createRole, updateRolePermissions, deleteRole,
  type RoleInfo, type RolesResponse,
} from "@/lib/admin/rbac";

const ROLE_LABELS: Record<string, string> = {
  super_admin: "Super Admin", admin: "Admin", project_manager: "Project Manager",
  architect: "Architect", data_engineer: "Data Engineer", qa_engineer: "QA Engineer", viewer: "Viewer",
};
const label = (n: string) => ROLE_LABELS[n] ?? n;

export default function RolesPage() {
  const { can } = useAuth();
  const canWrite = can("admin:roles:write");
  const [data, setData] = useState<RolesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");
  const [forbidden, setForbidden] = useState(false);
  const [editing, setEditing] = useState<RoleInfo | null>(null);
  const [creating, setCreating] = useState(false);
  const [confirmDel, setConfirmDel] = useState<RoleInfo | null>(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const d = await fetchRoles();
      setData(d); setErr("");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load";
      if (/403/.test(msg)) setForbidden(true); else setErr(msg);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { void load(); }, []);

  const onDelete = async () => {
    if (!confirmDel) return;
    setBusy(true);
    try {
      await deleteRole(confirmDel.id);
      setConfirmDel(null); setOk(`Deleted role "${confirmDel.name}".`);
      await load();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  };

  const roles = data?.roles ?? [];
  const allPerms = data?.permissions ?? [];

  return (
    <AppShell
      title="Roles & Permissions"
      subtitle="System roles are protected. Create custom roles and toggle their permissions to fit your team."
      crumbs={["Roles"]}
      actions={!forbidden && canWrite ? <Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> New role</Button> : undefined}
    >
      {err && <ErrorBanner message={err} onDismiss={() => setErr("")} />}
      {ok && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-[8px] border border-hx-2 bg-[var(--con-ok-soft,#ecfdf5)] text-[12.5px] text-ink-2">
          <ShieldCheck className="h-4 w-4 text-[var(--con-ok)]" /> {ok}
        </div>
      )}

      {loading ? (
        <LoadingState label="Loading roles…" />
      ) : forbidden ? (
        <Card><EmptyState title="Admins only" description="You need the admin:roles:read permission to view roles." /></Card>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {roles.map((r) => (
              <Card key={r.id} padding="md">
                <div className="flex items-start gap-2.5">
                  <div className="grid place-items-center h-8 w-8 rounded-lg bg-[var(--con-brand-soft)] text-[var(--con-brand)] flex-shrink-0"><Lock className="h-4 w-4" /></div>
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] font-semibold text-ink flex items-center gap-1.5">{label(r.name)}{r.is_system && <Chip tone="default">system</Chip>}</div>
                    <div className="text-[11.5px] text-ink-4 mt-0.5">{r.count} perms · {r.members} member{r.members === 1 ? "" : "s"}</div>
                  </div>
                </div>
                <div className="mt-3 flex gap-1.5">
                  <Button size="sm" variant="outline" onClick={() => setEditing(r)}>
                    {r.is_system || !canWrite ? <>View</> : <><Pencil className="h-3.5 w-3.5" /> Edit</>}
                  </Button>
                  {!r.is_system && canWrite && (
                    <Button size="sm" variant="ghost" onClick={() => setConfirmDel(r)}><Trash2 className="h-3.5 w-3.5" /></Button>
                  )}
                </div>
              </Card>
            ))}
          </div>

          <Card title="Permission matrix" description="Which role grants which permission" bodyClassName="p-0">
            <div className="overflow-x-auto">
              <Table minWidth={720}>
                <THead>
                  <TR hover={false}>
                    <TH>Permission</TH>
                    {roles.map((r) => <TH key={r.id} align="center">{label(r.name)}</TH>)}
                  </TR>
                </THead>
                <TBody>
                  {allPerms.map((perm) => (
                    <TR key={perm}>
                      <TD className="font-mono text-[12px] text-ink-2 whitespace-nowrap">{perm}</TD>
                      {roles.map((r) => (
                        <TD key={r.id} align="center">
                          {r.permissions.includes(perm)
                            ? <Check className="h-4 w-4 mx-auto text-[var(--con-ok)]" aria-label="granted" />
                            : <span className="text-ink-5" aria-label="not granted">·</span>}
                        </TD>
                      ))}
                    </TR>
                  ))}
                </TBody>
              </Table>
            </div>
          </Card>
        </>
      )}

      {(editing || creating) && (
        <RoleEditor
          role={editing}
          canWrite={canWrite}
          allPerms={allPerms}
          onClose={() => { setEditing(null); setCreating(false); }}
          onSaved={async (msg) => { setEditing(null); setCreating(false); setOk(msg); await load(); }}
          onError={(m) => setErr(m)}
        />
      )}

      <ConfirmModal
        open={confirmDel !== null}
        onClose={() => setConfirmDel(null)}
        onConfirm={onDelete}
        title={`Delete role "${confirmDel?.name}"?`}
        description="This can't be undone. Roles assigned to members must be reassigned first."
        destructive
        busy={busy}
        confirmLabel="Delete role"
      />
    </AppShell>
  );
}

function RoleEditor({ role, canWrite, allPerms, onClose, onSaved, onError }: {
  role: RoleInfo | null;
  canWrite: boolean;
  allPerms: string[];
  onClose: () => void;
  onSaved: (msg: string) => void;
  onError: (m: string) => void;
}) {
  const readOnly = !!role?.is_system || !canWrite;
  const [name, setName] = useState(role?.name ?? "");
  const [selected, setSelected] = useState<Set<string>>(new Set(role?.permissions ?? []));
  const [saving, setSaving] = useState(false);

  const toggle = (p: string) => {
    if (readOnly) return;
    setSelected((cur) => { const n = new Set(cur); n.has(p) ? n.delete(p) : n.add(p); return n; });
  };

  const save = async () => {
    setSaving(true);
    try {
      if (role && !role.is_system) {
        await updateRolePermissions(role.id, Array.from(selected));
        onSaved(`Updated "${role.name}".`);
      } else if (!role) {
        await createRole(name.trim(), Array.from(selected));
        onSaved(`Created role "${name.trim()}".`);
      }
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open onClose={onClose} title={role ? (readOnly ? `${role.name} (system role)` : `Edit ${role.name}`) : "New role"} width="md">
      <div className="space-y-4">
        {!role && (
          <label className="flex flex-col gap-1.5">
            <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">Role name</span>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. analyst_readonly"
              className="h-9 px-2.5 text-[13px] rounded-[8px] border border-hx bg-surface focus-ring" />
          </label>
        )}
        {readOnly && <p className="text-[12px] text-ink-4">System roles are protected and can’t be edited. Create a custom role to define your own permission set.</p>}
        <div>
          <div className="text-[10px] uppercase tracking-wider font-mono text-ink-4 mb-2">Permissions</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 max-h-[320px] overflow-y-auto pr-1">
            {allPerms.map((p) => {
              const on = selected.has(p);
              return (
                <button key={p} type="button" onClick={() => toggle(p)} disabled={readOnly}
                  className={`flex items-center gap-2 px-2.5 py-1.5 rounded-md border text-left text-[12px] transition-colors disabled:cursor-default ${on ? "border-[var(--con-brand)] bg-[var(--con-brand-soft)] text-ink" : "border-hx-2 bg-surface text-ink-3 hover:bg-app-2"}`}>
                  <span className={`grid place-items-center h-4 w-4 rounded-[4px] border flex-shrink-0 ${on ? "bg-[var(--con-brand)] border-[var(--con-brand)]" : "border-hx-2"}`}>
                    {on && <Check className="h-3 w-3 text-white" />}
                  </span>
                  <span className="font-mono truncate">{p}</span>
                </button>
              );
            })}
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onClose}>{readOnly ? "Close" : "Cancel"}</Button>
          {!readOnly && <Button onClick={save} loading={saving}>{role ? "Save changes" : "Create role"}</Button>}
        </div>
      </div>
    </Modal>
  );
}
