"use client";

/**
 * /admin/roles — read-only RBAC matrix.
 *
 * Shows the built-in system roles and exactly which permissions each grants,
 * straight from the backend (auth_service.SYSTEM_ROLES). This reflects the real
 * system truth; roles are code-defined, so this view is read-only.
 */

import { useEffect, useState } from "react";
import { Check, Lock } from "lucide-react";

import { AppShell } from "@/components/layout";
import { Card, Chip, ErrorBanner, LoadingState, EmptyState, Table, THead, TBody, TR, TH, TD } from "@/components/ui";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface RoleRow { role: string; wildcard: boolean; permissions: string[]; count: number; }
interface RbacData { permissions: string[]; roles: RoleRow[]; }

const ROLE_LABELS: Record<string, string> = {
  super_admin: "Super Admin",
  admin: "Admin",
  project_manager: "Project Manager",
  architect: "Architect",
  data_engineer: "Data Engineer",
  qa_engineer: "QA Engineer",
  viewer: "Viewer",
};

export default function RolesPage() {
  const [data, setData] = useState<RbacData | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [forbidden, setForbidden] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/admin/roles`, { credentials: "include" })
      .then((r) => {
        if (r.status === 403) { setForbidden(true); return null; }
        if (!r.ok) throw new Error(`Failed to load roles (${r.status})`);
        return r.json();
      })
      .then((d: RbacData | null) => { if (d) setData(d); })
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  const has = (role: RoleRow, perm: string) => role.wildcard || role.permissions.includes(perm);

  return (
    <AppShell
      title="Roles & Permissions"
      subtitle="Built-in RBAC roles and the permissions each grants. Roles are defined by the platform; this view is read-only."
      crumbs={["Roles"]}
    >
      {err && <ErrorBanner message={err} onDismiss={() => setErr("")} />}
      {loading ? (
        <LoadingState label="Loading roles…" />
      ) : forbidden ? (
        <Card>
          <EmptyState
            title="Admins only"
            description="You need the admin:roles:read permission to view the RBAC matrix. Ask an administrator for access."
          />
        </Card>
      ) : !data ? (
        <Card title="Roles"><p className="text-[12.5px] text-ink-3">No role data available.</p></Card>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {data.roles.map((r) => (
              <Card key={r.role} padding="md">
                <div className="flex items-start gap-2.5">
                  <div className="grid place-items-center h-8 w-8 rounded-lg bg-[var(--con-brand-soft)] text-[var(--con-brand)] flex-shrink-0">
                    <Lock className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-[13px] font-semibold text-ink">{ROLE_LABELS[r.role] ?? r.role}</div>
                    <div className="text-[11.5px] text-ink-4 mt-0.5">
                      {r.wildcard ? "All permissions" : `${r.count} permission${r.count === 1 ? "" : "s"}`}
                    </div>
                  </div>
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
                    {data.roles.map((r) => (
                      <TH key={r.role} align="center">{ROLE_LABELS[r.role] ?? r.role}</TH>
                    ))}
                  </TR>
                </THead>
                <TBody>
                  {data.permissions.map((perm) => (
                    <TR key={perm}>
                      <TD className="font-mono text-[12px] text-ink-2 whitespace-nowrap">{perm}</TD>
                      {data.roles.map((r) => (
                        <TD key={r.role} align="center">
                          {has(r, perm)
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

          <div className="flex items-center gap-2 text-[12px] text-ink-4">
            <Chip tone="default">Read-only</Chip>
            <span>Custom roles and per-permission editing aren’t available yet — roles are defined by the platform.</span>
          </div>
        </>
      )}
    </AppShell>
  );
}
