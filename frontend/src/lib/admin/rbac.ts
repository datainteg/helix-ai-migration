/**
 * Admin RBAC client — org members, role assignment, editable roles, invites.
 * Auth via HttpOnly cookie.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export interface Member {
  user_id: string;
  membership_id: string;
  email: string | null;
  name: string | null;
  role_id: string;
  role: string;
  status: string;
  is_super_admin: boolean;
}

export interface RoleInfo {
  id: string;
  name: string;
  is_system: boolean;
  permissions: string[];
  count: number;
  members: number;
}

export interface RolesResponse {
  permissions: string[];
  roles: RoleInfo[];
}

export interface Invitation {
  id: string;
  email: string;
  status: string;
  expires_at: string | null;
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((detail && detail.detail) || `${path} → ${res.status}`);
  }
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

// members
export const fetchMembers = () => req<Member[]>(`/api/v1/admin/users`);
export const changeMemberRole = (userId: string, roleId: string) =>
  req<{ user_id: string; role_id: string; role: string }>(`/api/v1/admin/users/${userId}/role`, {
    method: "PUT", body: JSON.stringify({ role_id: roleId }),
  });

// roles
export const fetchRoles = () => req<RolesResponse>(`/api/v1/admin/roles`);
export const createRole = (name: string, permissions: string[]) =>
  req<RoleInfo>(`/api/v1/admin/roles`, { method: "POST", body: JSON.stringify({ name, permissions }) });
export const updateRolePermissions = (roleId: string, permissions: string[]) =>
  req<RoleInfo>(`/api/v1/admin/roles/${roleId}/permissions`, { method: "PUT", body: JSON.stringify({ permissions }) });
export const deleteRole = (roleId: string) =>
  req<void>(`/api/v1/admin/roles/${roleId}`, { method: "DELETE" });

// invitations
export const fetchInvitations = () => req<Invitation[]>(`/api/v1/invitations`);
export const inviteUser = (email: string, role: string) =>
  req<{ status: string; email: string }>(`/api/v1/invitations`, { method: "POST", body: JSON.stringify({ email, role }) });
export const revokeInvitation = (id: string) =>
  req<void>(`/api/v1/invitations/${id}`, { method: "DELETE" });
