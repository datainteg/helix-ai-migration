"use client";

/**
 * /admin/users — organization members + invitations.
 *
 * Lists active members (real org-scoped /admin/users), lets an admin change a
 * member's role inline, invite new users by email, and revoke pending invites.
 * Role changes + invites need admin:users:write; the backend enforces lockout
 * guardrails (can't strip the last admin).
 */

import { useEffect, useState } from "react";
import { Plus, Mail, Trash2, ShieldCheck } from "lucide-react";

import { AdminShell } from "@/components/layout";
import { Card, Avatar, StatusBadge, Chip, Button, LoadingState, EmptyState, ErrorBanner, Modal, Table, THead, TBody, TR, TH, TD } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import {
  fetchMembers, changeMemberRole, fetchRoles, fetchInvitations, inviteUser, revokeInvitation,
  type Member, type RoleInfo, type Invitation,
} from "@/lib/admin/rbac";

// Roles the backend allows for invites (admin/super_admin require promotion).
const INVITABLE = ["viewer", "project_manager", "architect", "data_engineer", "qa_engineer"];

export default function UsersPage() {
  const { can } = useAuth();
  const canWrite = can("admin:users:write");
  const [members, setMembers] = useState<Member[]>([]);
  const [roles, setRoles] = useState<RoleInfo[]>([]);
  const [invites, setInvites] = useState<Invitation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [showInvite, setShowInvite] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [m, r, i] = await Promise.all([
        fetchMembers(),
        fetchRoles(),
        fetchInvitations().catch(() => []),
      ]);
      setMembers(m); setRoles(r.roles); setInvites(i);
      setError("");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load users");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const onRoleChange = async (m: Member, roleId: string) => {
    if (roleId === m.role_id) return;
    setError(""); setOk("");
    // optimistic
    const prev = members;
    setMembers((cur) => cur.map((x) => (x.user_id === m.user_id ? { ...x, role_id: roleId, role: roles.find((r) => r.id === roleId)?.name ?? x.role } : x)));
    try {
      await changeMemberRole(m.user_id, roleId);
      setOk(`Updated ${m.email}'s role.`);
    } catch (e: unknown) {
      setMembers(prev); // revert
      setError(e instanceof Error ? e.message : "Role change failed");
    }
  };

  const pending = invites.filter((i) => i.status === "pending");

  return (
    <AdminShell
      title="Users"
      subtitle="Manage organization members, assign roles, and invite teammates."
      page="Users"
      actions={canWrite ? <Button onClick={() => setShowInvite(true)}><Plus className="h-4 w-4" /> Invite user</Button> : undefined}
    >
      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}
      {ok && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-[8px] border border-hx-2 bg-[var(--con-ok-soft,#ecfdf5)] text-[12.5px] text-ink-2">
          <ShieldCheck className="h-4 w-4 text-[var(--con-ok)]" /> {ok}
        </div>
      )}

      {loading ? (
        <LoadingState label="Loading members…" />
      ) : (
        <>
          <Card title="Members" description="People with access to this organization" bodyClassName="p-0">
            {members.length === 0 ? (
              <div className="p-4"><EmptyState title="No members yet" description="Invite teammates to start collaborating." /></div>
            ) : (
              <div className="overflow-x-auto">
                <Table minWidth={680}>
                  <THead>
                    <TR hover={false}><TH>User</TH><TH>Role</TH><TH>Status</TH><TH>&nbsp;</TH></TR>
                  </THead>
                  <TBody>
                    {members.map((m) => (
                      <TR key={m.user_id}>
                        <TD>
                          <div className="flex items-center gap-3">
                            <Avatar name={m.name || m.email || "?"} size={26} />
                            <div className="min-w-0">
                              <p className="font-medium text-ink truncate">{m.name || m.email}</p>
                              <p className="text-[11.5px] text-ink-3 flex items-center gap-1 font-mono truncate"><Mail className="h-3 w-3" />{m.email}</p>
                            </div>
                          </div>
                        </TD>
                        <TD>
                          {m.is_super_admin || !canWrite ? (
                            <Chip tone="brand">{m.role}</Chip>
                          ) : (
                            <select
                              value={m.role_id}
                              onChange={(e) => onRoleChange(m, e.target.value)}
                              className="h-8 px-2 text-[12.5px] rounded-[8px] border border-hx bg-surface focus-ring"
                            >
                              {roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                            </select>
                          )}
                        </TD>
                        <TD><StatusBadge status={m.status} /></TD>
                        <TD className="text-right">
                          {m.is_super_admin && <span className="text-[11px] text-ink-4">platform owner</span>}
                        </TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              </div>
            )}
          </Card>

          {pending.length > 0 && (
            <Card title="Pending invitations" description="Invited but not yet accepted" bodyClassName="p-0">
              <Table>
                <THead><TR hover={false}><TH>Email</TH><TH>Status</TH><TH>Expires</TH><TH>&nbsp;</TH></TR></THead>
                <TBody>
                  {pending.map((i) => (
                    <TR key={i.id}>
                      <TD className="font-mono text-[12.5px]">{i.email}</TD>
                      <TD><Chip tone="warn" dot>{i.status}</Chip></TD>
                      <TD className="text-[11.5px] text-ink-4">{i.expires_at ? new Date(i.expires_at).toLocaleDateString() : "—"}</TD>
                      <TD className="text-right">
                        <button
                          type="button"
                          aria-label="Revoke invitation"
                          onClick={async () => { try { await revokeInvitation(i.id); await load(); } catch (e: unknown) { setError(e instanceof Error ? e.message : "Revoke failed"); } }}
                          className="p-1.5 rounded-md text-ink-4 hover:text-[var(--con-err)] hover:bg-app-2"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </Card>
          )}
        </>
      )}

      {showInvite && (
        <InviteModal
          onClose={() => setShowInvite(false)}
          onInvited={async () => { setShowInvite(false); setOk("Invitation sent."); await load(); }}
        />
      )}
    </AdminShell>
  );
}

function InviteModal({ onClose, onInvited }: { onClose: () => void; onInvited: () => void }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("viewer");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!email.trim()) { setErr("Enter an email address."); return; }
    setBusy(true); setErr("");
    try {
      await inviteUser(email.trim(), role);
      onInvited();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Invite failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Invite user" width="sm">
      <div className="space-y-4">
        {err && <ErrorBanner message={err} onDismiss={() => setErr("")} />}
        <label className="flex flex-col gap-1.5">
          <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">Email</span>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="teammate@company.com"
            className="h-9 px-2.5 text-[13px] rounded-[8px] border border-hx bg-surface focus-ring" />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">Role</span>
          <select value={role} onChange={(e) => setRole(e.target.value)} className="h-9 px-2.5 text-[13px] rounded-[8px] border border-hx bg-surface focus-ring">
            {INVITABLE.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <span className="text-[11.5px] text-ink-4">Admin roles must be assigned after the user joins.</span>
        </label>
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} loading={busy}><Mail className="h-3.5 w-3.5" /> Send invite</Button>
        </div>
      </div>
    </Modal>
  );
}
