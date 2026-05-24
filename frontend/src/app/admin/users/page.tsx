"use client";

import { useAuth } from "@/lib/auth-context";
import { useEffect, useState } from "react";
import { Plus, Mail } from "lucide-react";
import { AdminShell } from "@/components/layout";
import { Card, Avatar, StatusBadge, Chip, Button, LoadingState, EmptyState, ErrorBanner } from "@/components/ui";
import { formatDate } from "@/lib/utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

const DEMO: User[] = [
  { id: "u1", email: "avery@datainteg.io", name: "Avery Johnson", role: "Super Admin", is_active: true, created_at: "2026-03-01T00:00:00Z" },
  { id: "u2", email: "mei.chen@datainteg.io", name: "Mei Chen", role: "Engineer", is_active: true, created_at: "2026-03-12T00:00:00Z" },
  { id: "u3", email: "sofia@datainteg.io", name: "Sofia Marin", role: "QA Lead", is_active: true, created_at: "2026-04-05T00:00:00Z" },
  { id: "u4", email: "rohan@datainteg.io", name: "Rohan Patel", role: "Architect", is_active: true, created_at: "2026-04-18T00:00:00Z" },
  { id: "u5", email: "liam@datainteg.io", name: "Liam O'Connor", role: "DevOps", is_active: false, created_at: "2026-05-01T00:00:00Z" },
];

export default function UsersPage() {
  const { token } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) { setLoading(false); return; }
    fetch(`${API_BASE}/api/v1/admin/users`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setUsers)
      .catch(() => setError("Failed to load users"))
      .finally(() => setLoading(false));
  }, [token]);

  const data = users.length > 0 ? users : DEMO;

  return (
    <AdminShell
      title="Users"
      subtitle="Manage accounts, roles, and access across organizations."
      actions={<Button><Plus className="h-4 w-4" /> Invite User</Button>}
    >
      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}
      {loading ? (
        <LoadingState label="Loading users…" />
      ) : data.length === 0 ? (
        <EmptyState title="No users yet" description="Invite teammates to start collaborating on migrations." />
      ) : (
        <Card bodyClassName="p-0">
          <table className="w-full text-[13px] border-t border-hx">
            <thead className="bg-surface-hi text-[10.5px] uppercase tracking-[0.08em] text-ink-4 font-mono">
              <tr>
                <th className="px-4 py-2.5 text-left font-medium border-b border-hx">User</th>
                <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Role</th>
                <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Created</th>
                <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Status</th>
                <th className="px-4 py-2.5 text-right font-medium border-b border-hx"></th>
              </tr>
            </thead>
            <tbody>
              {data.map((u) => (
                <tr key={u.id} className="border-b border-hx last:border-b-0 hover:bg-surface-hi">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <Avatar name={u.name || u.email} size="md" />
                      <div>
                        <p className="font-medium text-ink">{u.name || u.email}</p>
                        <p className="text-[11.5px] text-ink-3 flex items-center gap-1 font-mono"><Mail className="h-3 w-3" />{u.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3"><Chip tone="brand">{u.role}</Chip></td>
                  <td className="px-4 py-3 text-ink-3 text-[12px] font-mono">{formatDate(u.created_at)}</td>
                  <td className="px-4 py-3"><StatusBadge status={u.is_active ? "active" : "inactive"} /></td>
                  <td className="px-4 py-3 text-right">
                    <button className="text-[12.5px] text-[var(--con-brand)] hover:underline">Manage</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </AdminShell>
  );
}
