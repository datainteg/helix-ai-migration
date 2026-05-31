/**
 * Project source/target connection client — add, list, delete, test, discover.
 * Credentials are sent once on create (encrypted server-side, never returned).
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export type ConnSide = "source" | "target";

export interface Connection {
  id: string;
  project_id: string;
  name: string;
  connector_type: string;
  status: string;
  config_masked: string | null;
}

export interface TestResult { success: boolean; message: string; }

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init, credentials: "include",
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((d && d.detail) || `${path} → ${res.status}`);
  }
  const t = await res.text();
  return (t ? JSON.parse(t) : undefined) as T;
}

const seg = (side: ConnSide) => (side === "source" ? "sources" : "targets");

export function listConnections(projectId: string, side: ConnSide): Promise<Connection[]> {
  return req<Connection[]>(`/api/v1/projects/${projectId}/${seg(side)}`);
}

export function addConnection(projectId: string, side: ConnSide, body: { name: string; connector_type: string; config: Record<string, unknown> }): Promise<Connection> {
  return req<Connection>(`/api/v1/projects/${projectId}/${seg(side)}`, { method: "POST", body: JSON.stringify(body) });
}

export function deleteConnection(projectId: string, side: ConnSide, connId: string): Promise<void> {
  return req<void>(`/api/v1/projects/${projectId}/${seg(side)}/${connId}`, { method: "DELETE" });
}

export function testConnection(projectId: string, side: ConnSide, connId: string): Promise<TestResult> {
  return req<TestResult>(`/api/v1/projects/${projectId}/${seg(side)}/${connId}/test`, { method: "POST" });
}

/** Introspect schemas from a saved connection (populates schema metadata). */
export function discoverSchemas(projectId: string, side: ConnSide, connId: string): Promise<unknown> {
  return req(`/api/v1/projects/${projectId}/${seg(side)}/${connId}/discover/schemas`, { method: "POST" });
}

// Per-connector credential fields. Keys must match what the backend connector
// reads from `config` (connectors/<type>/connector.py).
export interface FieldDef { key: string; label: string; type?: "text" | "password" | "number"; placeholder?: string; }

export const CONNECTOR_FIELDS: Record<string, FieldDef[]> = {
  postgres: [
    { key: "host", label: "Host", placeholder: "db.example.com" },
    { key: "port", label: "Port", type: "number", placeholder: "5432" },
    { key: "database", label: "Database", placeholder: "postgres" },
    { key: "username", label: "Username", placeholder: "postgres" },
    { key: "password", label: "Password", type: "password" },
    { key: "ssl_mode", label: "SSL mode", placeholder: "prefer" },
  ],
  mysql: [
    { key: "host", label: "Host", placeholder: "db.example.com" },
    { key: "port", label: "Port", type: "number", placeholder: "3306" },
    { key: "database", label: "Database" },
    { key: "username", label: "Username", placeholder: "root" },
    { key: "password", label: "Password", type: "password" },
  ],
  sqlserver: [
    { key: "host", label: "Host", placeholder: "sql.example.com" },
    { key: "port", label: "Port", type: "number", placeholder: "1433" },
    { key: "database", label: "Database", placeholder: "master" },
    { key: "username", label: "Username", placeholder: "sa" },
    { key: "password", label: "Password", type: "password" },
  ],
  snowflake: [
    { key: "account", label: "Account", placeholder: "xy12345.us-east-1" },
    { key: "username", label: "Username" },
    { key: "password", label: "Password", type: "password" },
    { key: "database", label: "Database" },
    { key: "warehouse", label: "Warehouse" },
    { key: "role", label: "Role (optional)" },
    { key: "schema", label: "Schema", placeholder: "PUBLIC" },
  ],
  s3: [
    { key: "bucket", label: "Bucket" },
    { key: "region", label: "Region", placeholder: "us-east-1" },
    { key: "access_key_id", label: "Access key ID" },
    { key: "secret_access_key", label: "Secret access key", type: "password" },
    { key: "prefix", label: "Prefix (optional)" },
  ],
};

export const CONNECTOR_LABELS: Record<string, string> = {
  postgres: "PostgreSQL", mysql: "MySQL", sqlserver: "SQL Server",
  snowflake: "Snowflake", s3: "Amazon S3",
};
