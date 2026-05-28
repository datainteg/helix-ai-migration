"use client";

import React, { useEffect, useId, useState } from "react";
import {
  Plus,
  Code,
  X,
  Check,
  Play,
  RefreshCw,
  Upload,
  Info,
  AlertTriangle,
  Plug,
} from "lucide-react";

import { AppShell } from "@/components/layout";
import { AppIcon } from "@/components/icons";
import { Button, Card, Tabs, LoadingState, EmptyState, Modal, ErrorBanner, SearchInput } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ConnectorRow {
  name: string;
  category: string;
  instances: number | string;
  status: "ok" | "warn" | "err";
  p95: string;
  rows: string;
  authored: string;
  color: string;
  letter: string;
}

// Shape returned by GET /api/v1/connectors/registry.
// The registry-mode field maps to "authored" (built_in → datainteg, custom → you).
interface RegistryEntry {
  connector_type?: string;
  display_name?: string;
  name?: string;
  category?: string;
  mode?: string;
  capabilities?: Record<string, boolean>;
  supports_test?: boolean;
  supports_discover_schemas?: boolean;
  supports_discover_tables?: boolean;
  supports_discover_columns?: boolean;
  supports_row_count?: boolean;
}

// Map a connector_type / display_name to a UI category bucket so the tab
// filter (database / warehouse / object / saas / file / legacy / custom)
// continues to slice the grid even though the backend doesn't return one.
function categoryFor(entry: RegistryEntry): string {
  if (entry.category) return entry.category;
  if (entry.mode === "custom") return "custom";
  const slug = (entry.connector_type || entry.name || entry.display_name || "")
    .toLowerCase();
  if (["s3", "gcs", "azure", "azure_blob", "minio"].some((k) => slug.includes(k))) return "object";
  if (["snowflake", "databricks", "bigquery", "redshift", "synapse"].some((k) => slug.includes(k))) return "warehouse";
  if (["salesforce", "hubspot", "zendesk", "workday", "netsuite"].some((k) => slug.includes(k))) return "saas";
  if (["csv", "excel", "parquet", "json", "xml"].some((k) => slug === k || slug.includes(k))) return "file";
  if (["datastage", "informatica", "sas", "abinitio"].some((k) => slug.includes(k))) return "legacy";
  return "database";
}

function rowFromEntry(entry: RegistryEntry): ConnectorRow {
  const name = entry.display_name || entry.name || entry.connector_type || "Unknown";
  const isCustom = entry.mode === "custom";
  return {
    name,
    category: categoryFor(entry),
    instances: "—",
    status: "ok",
    p95: "—",
    rows: "—",
    authored: isCustom ? "you" : "datainteg",
    // color/letter are unused by AppIcon (it derives its own); keep harmless defaults.
    color: "#71717A",
    letter: (name[0] || "?").toUpperCase(),
  };
}

// Map a connector display name (or row entry) to an AppIcon slug. AppIcon
// renders the real brand SVG when available, letter fallback when not. For
// brands AppIcon does not know (Azure Blob, GCS, CSV, Excel, custom...) we
// pass the lowercase name and let AppIcon use its `?` fallback rendering.
function appIconSlugFor(connectorName: string): string {
  const n = connectorName.toLowerCase();
  if (n.includes("postgres")) return "postgresql";
  if (n.includes("snowflake")) return "snowflake";
  if (n.includes("oracle")) return "oracle";
  if (n.includes("sql server")) return "sqlserver";
  if (n.includes("mysql")) return "mysql";
  if (n.includes("db2")) return "db2";
  if (n.includes("databricks")) return "databricks";
  if (n.includes("bigquery")) return "googlebigquery";
  if (n.includes("salesforce")) return "salesforce";
  if (n.includes("datastage")) return "datastage";
  if (n.includes("mongo")) return "mongodb";
  if (n.includes("sas")) return "sas";
  if (n === "s3") return "s3";
  // Azure Blob, GCS, CSV, Excel, Custom: pass through — AppIcon shows `?`.
  return n;
}

interface Provider {
  key: string;
  name: string;
  category: string;
  color: string;
  letter: string;
}

const PROVIDER_CATALOG: Provider[] = [
  { key: "postgres", name: "PostgreSQL", category: "database", color: "#336791", letter: "P" },
  { key: "mysql", name: "MySQL", category: "database", color: "#00758F", letter: "M" },
  { key: "sqlserver", name: "SQL Server", category: "database", color: "#A91D22", letter: "M" },
  { key: "oracle", name: "Oracle", category: "database", color: "#E11D48", letter: "O" },
  { key: "db2", name: "DB2", category: "database", color: "#1F70C1", letter: "D" },
  { key: "mongo", name: "MongoDB", category: "database", color: "#13AA52", letter: "M" },
  { key: "snowflake", name: "Snowflake", category: "warehouse", color: "#29B5E8", letter: "S" },
  { key: "databricks", name: "Databricks", category: "warehouse", color: "#FF3621", letter: "D" },
  { key: "bigquery", name: "BigQuery", category: "warehouse", color: "#4285F4", letter: "B" },
  { key: "s3", name: "S3", category: "object", color: "#FF9900", letter: "S" },
  { key: "gcs", name: "GCS", category: "object", color: "#4285F4", letter: "G" },
  { key: "azure", name: "Azure Blob", category: "object", color: "#0078D4", letter: "A" },
  { key: "salesforce", name: "Salesforce", category: "saas", color: "#00A1E0", letter: "S" },
  { key: "csv", name: "CSV file", category: "file", color: "#71717A", letter: "C" },
];

interface FormField {
  id: string;
  label: string;
  placeholder?: string;
  type: "text" | "number" | "password" | "select" | "textarea" | "file";
  defaultValue?: string | number;
  options?: string[];
  col?: number;
}

const FIELDS_FOR = (key: string): FormField[] => {
  switch (key) {
    case "postgres":
    case "mysql":
    case "sqlserver":
    case "db2":
      return [
        { id: "name", label: "Connection name", placeholder: "Acme Production", type: "text", col: 2 },
        { id: "host", label: "Host", placeholder: "db.example.com", type: "text" },
        { id: "port", label: "Port", placeholder: "5432", type: "number", defaultValue: key === "postgres" ? 5432 : key === "mysql" ? 3306 : 1433 },
        { id: "database", label: "Database", placeholder: "warehouse", type: "text", col: 2 },
        { id: "user", label: "Username", placeholder: "helix_reader", type: "text" },
        { id: "password", label: "Password", placeholder: "••••••••", type: "password" },
        { id: "ssl", label: "SSL mode", type: "select", options: ["disable", "require", "verify-ca", "verify-full"], defaultValue: "require", col: 2 },
      ];
    case "oracle":
      return [
        { id: "name", label: "Connection name", type: "text", col: 2 },
        { id: "host", label: "Host", type: "text" },
        { id: "port", label: "Port", type: "number", defaultValue: 1521 },
        { id: "service", label: "Service name", placeholder: "ORCL", type: "text", col: 2 },
        { id: "user", label: "Username", type: "text" },
        { id: "password", label: "Password", type: "password" },
      ];
    case "snowflake":
      return [
        { id: "name", label: "Connection name", type: "text", col: 2 },
        { id: "account", label: "Account", placeholder: "acme-east.us-east-1", type: "text", col: 2 },
        { id: "warehouse", label: "Warehouse", placeholder: "HELIX_WH", type: "text" },
        { id: "database", label: "Database", placeholder: "ANALYTICS", type: "text" },
        { id: "role", label: "Role", placeholder: "HELIX_ROLE", type: "text" },
        { id: "auth", label: "Auth method", type: "select", options: ["password", "keypair", "oauth"], defaultValue: "keypair" },
        { id: "user", label: "Username", type: "text" },
        { id: "key", label: "Private key", type: "textarea", placeholder: "-----BEGIN PRIVATE KEY-----\n…\n-----END PRIVATE KEY-----", col: 2 },
      ];
    case "databricks":
      return [
        { id: "name", label: "Connection name", type: "text", col: 2 },
        { id: "host", label: "Workspace host", placeholder: "adb-xxxx.azuredatabricks.net", type: "text", col: 2 },
        { id: "httpPath", label: "HTTP path", placeholder: "/sql/1.0/warehouses/...", type: "text", col: 2 },
        { id: "token", label: "Access token", type: "password", col: 2 },
      ];
    case "bigquery":
      return [
        { id: "name", label: "Connection name", type: "text", col: 2 },
        { id: "project", label: "GCP project ID", type: "text" },
        { id: "location", label: "Default location", type: "text", defaultValue: "US" },
        { id: "creds", label: "Service account JSON", type: "textarea", col: 2 },
      ];
    case "s3":
      return [
        { id: "name", label: "Connection name", type: "text", col: 2 },
        { id: "bucket", label: "Bucket", placeholder: "acme-data-lake", type: "text" },
        { id: "region", label: "Region", placeholder: "us-east-1", type: "text" },
        { id: "auth", label: "Auth method", type: "select", options: ["iam-role", "access-keys"], defaultValue: "iam-role", col: 2 },
        { id: "key", label: "Access key ID", type: "text" },
        { id: "secret", label: "Secret access key", type: "password" },
      ];
    case "salesforce":
      return [
        { id: "name", label: "Connection name", type: "text", col: 2 },
        { id: "instance", label: "Instance URL", placeholder: "https://acme.my.salesforce.com", type: "text", col: 2 },
        { id: "auth", label: "Auth method", type: "select", options: ["oauth-jwt", "oauth-pkce", "user-pass"], defaultValue: "oauth-jwt", col: 2 },
        { id: "clientId", label: "Client ID", type: "text" },
        { id: "clientSecret", label: "Client secret", type: "password" },
      ];
    case "csv":
      return [
        { id: "name", label: "Source name", type: "text", col: 2 },
        { id: "upload", label: "CSV file", type: "file", col: 2 },
        { id: "delimiter", label: "Delimiter", type: "select", options: [",", ";", "\\t", "|"], defaultValue: "," },
        { id: "encoding", label: "Encoding", type: "select", options: ["utf-8", "latin-1", "cp1252"], defaultValue: "utf-8" },
      ];
    default:
      return [
        { id: "name", label: "Connection name", type: "text", col: 2 },
        { id: "url", label: "Endpoint URL", type: "text", col: 2 },
        { id: "auth", label: "Auth header", type: "password", col: 2 },
      ];
  }
};

interface ModalState {
  mode: "new" | "edit";
  connector?: ConnectorRow;
}

function ConnectorCard({ c, onClick }: { c: ConnectorRow; onClick: () => void }) {
  const statusColor =
    c.status === "ok" ? "var(--con-ok)" : c.status === "warn" ? "var(--con-warn)" : "var(--con-err)";
  const isCustom = c.authored === "you";
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`Configure ${c.name} connector`}
      className="text-left bg-surface border border-hx flex flex-col cursor-pointer relative hover:border-hx-2 transition-colors focus-ring w-full"
      style={{
        borderRadius: 10,
        padding: "14px 16px",
        gap: 12,
      }}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center" style={{ gap: 10 }}>
          <AppIcon name={appIconSlugFor(c.name)} size={30} className="rounded-md" />
          <div>
            <div className="text-ink font-semibold" style={{ fontSize: 13 }}>
              {c.name}
            </div>
            <div
              className="font-mono text-ink-4 uppercase"
              style={{
                fontSize: 10.5,
                marginTop: 2,
                letterSpacing: "0.05em",
              }}
            >
              {c.category}
              {isCustom && " · custom"}
            </div>
          </div>
        </div>
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: statusColor,
            marginTop: 8,
          }}
        />
      </div>

      <div
        className="grid border-t border-hx"
        style={{
          gridTemplateColumns: "1fr 1fr 1fr",
          gap: 0,
          paddingTop: 12,
        }}
      >
        <div>
          <div className="eyebrow" style={{ fontSize: 9 }}>
            INSTANCES
          </div>
          <div
            className="font-mono tabular-nums text-ink"
            style={{ fontSize: 16, fontWeight: 500, marginTop: 2 }}
          >
            {c.instances}
          </div>
        </div>
        <div>
          <div className="eyebrow" style={{ fontSize: 9 }}>
            P95
          </div>
          <div
            className="font-mono tabular-nums"
            style={{
              fontSize: 16,
              fontWeight: 500,
              marginTop: 2,
              color: c.status === "warn" ? "var(--con-warn)" : "var(--con-ink-1)",
            }}
          >
            {c.p95}
          </div>
        </div>
        <div>
          <div className="eyebrow" style={{ fontSize: 9 }}>
            ROWS / DAY
          </div>
          <div
            className="font-mono tabular-nums text-ink"
            style={{ fontSize: 16, fontWeight: 500, marginTop: 2 }}
          >
            {c.rows}
          </div>
        </div>
      </div>
    </button>
  );
}

function Field({ field }: { field: FormField }) {
  // useId guarantees a unique htmlFor/id pair even when the same Field
  // is rendered in two places. focus-ring class restores the missing focus
  // outline that the inline `outline: none` style was removing.
  const inputId = useId();
  const baseStyle: React.CSSProperties = {
    width: "100%",
    height: field.type === "textarea" ? "auto" : 36,
    padding: field.type === "textarea" ? "10px 12px" : "0 12px",
    background: "var(--con-surface)",
    border: "1px solid var(--con-line-2)",
    borderRadius: 7,
    fontSize: 12.5,
    fontFamily:
      field.type === "textarea"
        ? "Geist Mono, ui-monospace, monospace"
        : "Geist, sans-serif",
    color: "var(--con-ink-1)",
  };

  return (
    <div style={{ gridColumn: field.col === 2 ? "span 2" : undefined }}>
      <label
        htmlFor={inputId}
        className="block text-ink-2"
        style={{
          fontSize: 11.5,
          fontWeight: 500,
          marginBottom: 5,
        }}
      >
        {field.label}
      </label>
      {field.type === "textarea" ? (
        <textarea
          id={inputId}
          className="focus-ring"
          style={baseStyle}
          placeholder={field.placeholder}
          defaultValue={field.defaultValue}
          rows={4}
        />
      ) : field.type === "select" ? (
        <select
          id={inputId}
          className="focus-ring"
          style={baseStyle}
          defaultValue={field.defaultValue}
        >
          {(field.options || []).map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      ) : field.type === "file" ? (
        <label
          htmlFor={inputId}
          className="flex items-center justify-center cursor-pointer text-ink-3 focus-within:outline focus-within:outline-2 focus-within:outline-offset-2"
          style={{
            ...baseStyle,
            height: 56,
            border: "1.5px dashed var(--con-line-3)",
            gap: 8,
            outlineColor: "var(--con-brand)",
          }}
        >
          <Upload size={14} aria-hidden />
          <span>Drop file here or click to browse</span>
          <input id={inputId} type="file" className="sr-only" />
        </label>
      ) : (
        <input
          id={inputId}
          type={field.type}
          className="focus-ring"
          style={baseStyle}
          placeholder={field.placeholder}
          defaultValue={field.defaultValue}
        />
      )}
    </div>
  );
}

type TestState = "idle" | "testing" | "ok" | "fail";

interface ConnectModalProps {
  open: boolean;
  modal: ModalState | null;
  onClose: () => void;
}

function ConnectModal({ open, modal, onClose }: ConnectModalProps) {
  if (!modal) return null;
  const fromConnector = modal.mode === "edit" ? modal.connector ?? null : null;
  const initialProvider: Provider | null = fromConnector
    ? PROVIDER_CATALOG.find((p) =>
        p.name.toLowerCase().includes(fromConnector.name.toLowerCase().split(" ")[0] ?? ""),
      ) ?? null
    : null;

  const [step, setStep] = useState<number>(initialProvider ? 1 : 0);
  const [provider, setProvider] = useState<Provider | null>(initialProvider);
  const [testState, setTestState] = useState<TestState>("idle");

  const fields: FormField[] = provider ? FIELDS_FOR(provider.key) : [];

  const runTest = () => {
    setTestState("testing");
    setTimeout(() => {
      setTestState(Math.random() > 0.15 ? "ok" : "fail");
    }, 1400);
  };

  const steps = [
    { id: 0, label: "Provider" },
    { id: 1, label: "Credentials" },
    { id: 2, label: "Test & save" },
  ];

  type CheckState = "ok" | "fail" | "running" | "skip" | "pending" | "idle";

  const checks: { name: string; state: CheckState; detail: string }[] = [
    { name: "Network reachability", state: "ok", detail: "TCP handshake · 12 ms" },
    {
      name: "Credentials accepted",
      state:
        testState === "idle"
          ? "idle"
          : testState === "testing"
            ? "running"
            : "ok",
      detail: "Auth method: password",
    },
    {
      name: "Permissions",
      state:
        testState === "ok"
          ? "ok"
          : testState === "fail"
            ? "fail"
            : testState === "testing"
              ? "running"
              : "idle",
      detail: "SELECT on warehouse.* · OK",
    },
    {
      name: "Schema discovery",
      state:
        testState === "ok"
          ? "ok"
          : testState === "fail"
            ? "skip"
            : testState === "testing"
              ? "pending"
              : "idle",
      detail:
        testState === "ok"
          ? "12 schemas, 412 tables found"
          : "pending previous step",
    },
    {
      name: "Row-count probe",
      state:
        testState === "ok"
          ? "ok"
          : testState === "fail"
            ? "skip"
            : "idle",
      detail:
        testState === "ok"
          ? "warehouse.GL_LEDGER: 12,408,221 rows"
          : "pending previous step",
    },
  ];

  // Render through the Modal primitive so we inherit dialog semantics,
  // focus trap, Escape close, scroll lock and focus restore. The Modal
  // header/title is provided by the title prop; we keep the custom stepper
  // + step content as the modal body.
  const modalTitle = provider
    ? `Configure ${provider.name}`
    : "Connect a new source or target";
  const modalDescription = fromConnector ? "Edit connection" : "New connection";

  return (
    <Modal open={open} onClose={onClose} title={modalTitle} description={modalDescription} width="lg">
      <div
        className="flex flex-col overflow-hidden"
        style={{ maxHeight: "calc(100vh - 200px)" }}
      >
        {/* Stepper */}
        <div
          className="flex bg-surface-hi border-b border-hx"
          style={{ padding: "14px 24px", gap: 8 }}
        >
          {steps.map((s, i) => (
            <div
              key={s.id}
              className="flex items-center flex-1"
              style={{ gap: 8, opacity: s.id <= step ? 1 : 0.45 }}
            >
              <div
                className="grid place-items-center font-mono font-semibold"
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: "50%",
                  background:
                    s.id < step
                      ? "var(--con-ink-1)"
                      : s.id === step
                        ? "var(--con-brand)"
                        : "var(--con-surface)",
                  border:
                    s.id < step || s.id === step
                      ? "none"
                      : "1px solid var(--con-line-2)",
                  color:
                    s.id <= step ? "#FFF" : "var(--con-ink-4)",
                  fontSize: 10.5,
                }}
              >
                {s.id < step ? <Check size={11} /> : i + 1}
              </div>
              <div className="flex-1">
                <div className="eyebrow" style={{ fontSize: 9.5 }}>
                  STEP {i + 1}
                </div>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 500,
                    color:
                      s.id <= step
                        ? "var(--con-ink-1)"
                        : "var(--con-ink-4)",
                  }}
                >
                  {s.label}
                </div>
              </div>
              {i < steps.length - 1 && (
                <div
                  className="flex-1"
                  style={{
                    height: 1,
                    background: "var(--con-line-2)",
                  }}
                />
              )}
            </div>
          ))}
        </div>

        {/* Body */}
        <div
          className="flex-1 overflow-y-auto"
          style={{ padding: "20px 24px" }}
        >
          {/* Step 0 — pick provider */}
          {step === 0 && (
            <div>
              <p
                className="text-ink-3"
                style={{ margin: "0 0 14px", fontSize: 12.5 }}
              >
                Choose a connector. Helix supports databases, warehouses,
                object stores, SaaS and file formats — plus custom connectors
                via the SDK.
              </p>
              <div
                className="grid"
                style={{
                  gridTemplateColumns: "repeat(3, 1fr)",
                  gap: 8,
                }}
              >
                {PROVIDER_CATALOG.map((p) => (
                  <button
                    type="button"
                    key={p.key}
                    onClick={() => {
                      setProvider(p);
                      setStep(1);
                    }}
                    className="flex items-center text-left cursor-pointer"
                    style={{
                      gap: 10,
                      padding: "10px 12px",
                      background:
                        provider?.key === p.key
                          ? "var(--con-surface-hi)"
                          : "var(--con-surface)",
                      border:
                        provider?.key === p.key
                          ? "1px solid var(--con-ink-1)"
                          : "1px solid var(--con-line)",
                      borderRadius: 8,
                    }}
                  >
                    <AppIcon name={appIconSlugFor(p.name)} size={28} className="rounded-md" />
                    <div className="flex-1 min-w-0">
                      <div
                        className="text-ink"
                        style={{
                          fontSize: 12.5,
                          fontWeight: 500,
                        }}
                      >
                        {p.name}
                      </div>
                      <div
                        className="font-mono text-ink-4 uppercase"
                        style={{
                          fontSize: 10,
                          letterSpacing: "0.05em",
                          marginTop: 1,
                        }}
                      >
                        {p.category}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Step 1 — credentials form */}
          {step === 1 && provider && (
            <div>
              <div
                className="flex items-center"
                style={{ gap: 10, marginBottom: 16 }}
              >
                <AppIcon name={appIconSlugFor(provider.name)} size={30} className="rounded-md" />
                <div>
                  <div style={{ fontSize: 13.5, fontWeight: 600 }}>
                    {provider.name}
                  </div>
                  <div
                    className="font-mono text-ink-4"
                    style={{ fontSize: 11 }}
                  >
                    {provider.category}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setStep(0)}
                  className="bg-transparent border-0 text-ink-3"
                  style={{
                    marginLeft: "auto",
                    fontSize: 11.5,
                    cursor: "pointer",
                  }}
                >
                  change ↺
                </button>
              </div>
              <div
                className="grid"
                style={{
                  gridTemplateColumns: "1fr 1fr",
                  gap: 12,
                }}
              >
                {fields.map((f) => (
                  <Field key={f.id} field={f} />
                ))}
              </div>
              <div
                className="flex items-start bg-app border border-hx"
                style={{
                  marginTop: 16,
                  padding: "10px 12px",
                  borderRadius: 8,
                  gap: 8,
                }}
              >
                <Info
                  size={13}
                  className="text-ink-4"
                  style={{ marginTop: 1, flexShrink: 0 }}
                />
                <div
                  className="text-ink-3"
                  style={{ fontSize: 11.5, lineHeight: 1.5 }}
                >
                  Credentials are encrypted at rest using the Helix secrets
                  store. The reader role recommendation is enforced — Helix
                  will refuse to run a migration with a connection that has
                  DDL grants on the source.
                </div>
              </div>
            </div>
          )}

          {/* Step 2 — test & save */}
          {step === 2 && provider && (
            <div>
              <div
                className="flex items-center"
                style={{ gap: 10, marginBottom: 18 }}
              >
                <AppIcon name={appIconSlugFor(provider.name)} size={30} className="rounded-md" />
                <div>
                  <div style={{ fontSize: 13.5, fontWeight: 600 }}>
                    {provider.name}
                  </div>
                  <div
                    className="font-mono text-ink-4"
                    style={{ fontSize: 11 }}
                  >
                    Acme Production · db.example.com:5432/warehouse
                  </div>
                </div>
              </div>

              <div className="flex flex-col" style={{ gap: 8 }}>
                {checks.map((check, i) => {
                  const icon =
                    check.state === "ok" ? (
                      <Check size={11} />
                    ) : check.state === "fail" ? (
                      <X size={11} />
                    ) : check.state === "running" ? (
                      <span
                        className="animate-spin"
                        style={{
                          width: 10,
                          height: 10,
                          borderRadius: "50%",
                          border: "1.5px solid var(--con-brand)",
                          borderRightColor: "transparent",
                        }}
                      />
                    ) : (
                      <span
                        style={{
                          width: 5,
                          height: 5,
                          borderRadius: "50%",
                          background: "var(--con-ink-5)",
                        }}
                      />
                    );
                  const color =
                    check.state === "ok"
                      ? "var(--con-ok)"
                      : check.state === "fail"
                        ? "var(--con-err)"
                        : check.state === "running"
                          ? "var(--con-brand)"
                          : check.state === "skip"
                            ? "var(--con-ink-5)"
                            : "var(--con-ink-4)";
                  return (
                    <div
                      key={i}
                      className="grid items-center"
                      style={{
                        gridTemplateColumns: "20px 200px 1fr 80px",
                        gap: 12,
                        padding: "8px 10px",
                        background:
                          check.state === "fail"
                            ? "var(--con-err-soft)"
                            : "var(--con-surface)",
                        border: "1px solid",
                        borderColor:
                          check.state === "fail"
                            ? "#FCA5A5"
                            : "var(--con-line)",
                        borderRadius: 6,
                      }}
                    >
                      <div
                        className="grid place-items-center"
                        style={{ color }}
                      >
                        {icon}
                      </div>
                      <span
                        style={{
                          fontSize: 12.5,
                          fontWeight: 500,
                          color:
                            check.state === "skip"
                              ? "var(--con-ink-5)"
                              : "var(--con-ink-1)",
                        }}
                      >
                        {check.name}
                      </span>
                      <span
                        className="font-mono text-ink-3"
                        style={{ fontSize: 11 }}
                      >
                        {check.detail}
                      </span>
                      <span
                        className="font-mono uppercase"
                        style={{
                          fontSize: 10.5,
                          color,
                          textAlign: "right",
                          letterSpacing: "0.05em",
                        }}
                      >
                        {check.state}
                      </span>
                    </div>
                  );
                })}
              </div>

              {testState === "ok" && (
                <div
                  className="flex items-center bg-ok-soft"
                  style={{
                    marginTop: 14,
                    padding: "10px 12px",
                    border: "1px solid #86EFAC",
                    borderRadius: 8,
                    gap: 9,
                  }}
                >
                  <Check size={14} className="text-ok" />
                  <span
                    className="text-ok"
                    style={{ fontSize: 12.5, fontWeight: 500 }}
                  >
                    Connection ready · 12 schemas discovered
                  </span>
                  <button
                    type="button"
                    className="bg-transparent border-0 text-ok"
                    style={{
                      marginLeft: "auto",
                      fontSize: 11.5,
                      cursor: "pointer",
                      fontWeight: 500,
                    }}
                  >
                    Browse schemas →
                  </button>
                </div>
              )}
              {testState === "fail" && (
                <div
                  className="flex items-start bg-err-soft"
                  style={{
                    marginTop: 14,
                    padding: "10px 12px",
                    border: "1px solid #FCA5A5",
                    borderRadius: 8,
                    gap: 9,
                  }}
                >
                  <AlertTriangle
                    size={14}
                    className="text-err"
                    style={{ marginTop: 1 }}
                  />
                  <div className="flex-1">
                    <div
                      className="text-err"
                      style={{ fontSize: 12.5, fontWeight: 500 }}
                    >
                      Permission check failed
                    </div>
                    <div
                      className="font-mono text-err"
                      style={{
                        fontSize: 11,
                        marginTop: 3,
                        opacity: 0.85,
                      }}
                    >
                      ERROR 42501: permission denied for schema warehouse
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          className="flex items-center justify-between bg-surface-hi border-t border-hx"
          style={{ padding: "14px 24px" }}
        >
          <div
            className="font-mono text-ink-4"
            style={{ fontSize: 11 }}
          >
            {step + 1} / {steps.length}
          </div>
          <div className="flex" style={{ gap: 8 }}>
            {step > 0 && (
              <Button
                variant="ghost"
                size="md"
                onClick={() => setStep(step - 1)}
              >
                ← Back
              </Button>
            )}
            {step === 1 && (
              <Button
                variant="outline"
                size="md"
                onClick={() => {
                  setStep(2);
                  runTest();
                }}
              >
                Skip test
              </Button>
            )}
            {step === 1 && (
              <Button
                variant="primary"
                size="md"
                onClick={() => {
                  setStep(2);
                  runTest();
                }}
              >
                <Play size={11} /> Test connection
              </Button>
            )}
            {step === 2 && testState !== "ok" && (
              <Button
                variant="outline"
                size="md"
                onClick={runTest}
                loading={testState === "testing"}
              >
                <RefreshCw size={12} /> Re-test
              </Button>
            )}
            {step === 2 && testState === "ok" && (
              <Button variant="primary" size="md" onClick={onClose}>
                <Check size={11} /> Save connection
              </Button>
            )}
          </div>
        </div>
      </div>
    </Modal>
  );
}

export default function ConnectorsPage() {
  const { token } = useAuth();
  const [cat, setCat] = useState<string>("all");
  const [query, setQuery] = useState<string>("");
  const [modal, setModal] = useState<ModalState | null>(null);
  const [connectors, setConnectors] = useState<ConnectorRow[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadError, setLoadError] = useState<string>("");
  const searchInputId = useId();

  useEffect(() => {
    let cancelled = false;
    const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
    setLoading(true);
    setLoadError("");
    fetch(`${API_BASE}/api/v1/connectors/registry`, { headers })
      .then((r) => {
        if (!r.ok) throw new Error(`Couldn't reach the connector registry (HTTP ${r.status})`);
        return r.json() as Promise<RegistryEntry[]>;
      })
      .then((entries) => {
        if (cancelled) return;
        const rows = Array.isArray(entries) ? entries.map(rowFromEntry) : [];
        setConnectors(rows);
        setLoading(false);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setConnectors([]);
        setLoadError(e instanceof Error ? e.message : "Couldn't reach the connector registry");
        setLoading(false);
      });
    return () => { cancelled = true; };
  }, [token]);

  const categories = ["database", "warehouse", "object", "saas", "file", "legacy", "custom"];
  const q = query.trim().toLowerCase();
  const matchesSearch = (c: ConnectorRow) =>
    q === "" || c.name.toLowerCase().includes(q) || c.category.toLowerCase().includes(q);
  const filtered = (cat === "all" ? connectors : connectors.filter((c) => c.category === cat))
    .filter(matchesSearch);

  const counts: Record<string, number> = {
    all: connectors.length,
    ...Object.fromEntries(
      categories.map((k) => [k, connectors.filter((c) => c.category === k).length]),
    ),
  };

  const instancesTotal = connectors.reduce((acc, c) => acc + (typeof c.instances === "number" ? c.instances : 0), 0);
  const eyebrow = loading
    ? "CONNECTORS · LOADING…"
    : `CONNECTORS · ${connectors.length} ACTIVE${instancesTotal ? ` · ${instancesTotal} INSTANCES` : ""}`;

  return (
    <AppShell
      eyebrow={eyebrow}
      title="Connectors"
      description="First-class connectors for databases, warehouses, files and object storage. Pluggable framework for custom integrations."
      actions={
        <>
          <Button variant="outline">
            <Code size={13} /> Connector SDK
          </Button>
          <Button variant="primary" onClick={() => setModal({ mode: "new" })}>
            <Plus size={13} /> New connection
          </Button>
        </>
      }
    >
      <div className="flex flex-col" style={{ gap: 16 }}>
        {loadError && <ErrorBanner message={loadError} onDismiss={() => setLoadError("")} />}

        {/* Filter — UI-016/UI-010/UI-026: inline pixel styles replaced with
            Tailwind utilities and the shared SearchInput primitive (carries its
            own aria-label + focus-ring). Tab strip scrolls on narrow widths. */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 bg-surface border border-hx rounded-[10px] px-3.5 py-2.5">
          <SearchInput
            id={searchInputId}
            ariaLabel="Search connectors"
            placeholder="Search connectors…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            wrapperClassName="flex-1 min-w-[180px] max-w-[320px]"
          />
          <div className="max-w-full overflow-x-auto">
          <Tabs
            value={cat}
            onChange={setCat}
            tabs={[
              { id: "all", label: "All", count: counts.all },
              { id: "database", label: "Database", count: counts.database },
              { id: "warehouse", label: "Warehouse", count: counts.warehouse },
              { id: "object", label: "Object", count: counts.object },
              { id: "saas", label: "SaaS", count: counts.saas },
              { id: "file", label: "File", count: counts.file },
              { id: "legacy", label: "Legacy", count: counts.legacy },
              { id: "custom", label: "Custom", count: counts.custom },
            ]}
          />
          </div>
        </div>

        {loading ? (
          <LoadingState label="Loading connectors…" />
        ) : connectors.length === 0 ? (
          <EmptyState
            icon={<Plug className="h-5 w-5" />}
            title={loadError ? "Couldn't load connectors" : "No connectors available"}
            description={
              loadError
                ? loadError
                : "No connector types are registered yet. Add a custom connector via the SDK."
            }
            action={
              <Button variant="outline" onClick={() => setModal({ mode: "new" })}>
                <Plus size={13} /> New connection
              </Button>
            }
          />
        ) : (
          <>
        {/* Grid */}
        <div
          className="grid"
          style={{
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: 12,
          }}
        >
          {filtered.map((c) => (
            <ConnectorCard
              key={c.name}
              c={c}
              onClick={() => setModal({ mode: "edit", connector: c })}
            />
          ))}

          {/* Build-your-own callout. NOT a button-of-buttons (invalid HTML);
              the inner Button owns the click action. */}
          <div
            className="flex flex-col justify-between bg-transparent"
            style={{
              border: "1px dashed var(--con-line-3)",
              borderRadius: 10,
              padding: "14px 16px",
              gap: 10,
            }}
          >
            <div>
              <div className="flex items-center" style={{ gap: 8 }}>
                <div
                  className="grid place-items-center bg-surface text-ink-3"
                  style={{
                    width: 30,
                    height: 30,
                    borderRadius: 6,
                    border: "1px dashed var(--con-line-3)",
                  }}
                >
                  <Plus size={14} />
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>
                    Build a connector
                  </div>
                  <div
                    className="font-mono text-ink-4 uppercase"
                    style={{
                      fontSize: 10.5,
                      marginTop: 2,
                      letterSpacing: "0.05em",
                    }}
                  >
                    SDK
                  </div>
                </div>
              </div>
              <p
                className="text-ink-3"
                style={{
                  margin: "10px 0 0",
                  fontSize: 11.5,
                  lineHeight: 1.5,
                }}
              >
                Implement{" "}
                <span className="font-mono text-ink">Source</span> and{" "}
                <span className="font-mono text-ink">Sink</span> protocols in
                Python. Plugs into Validation and Recon automatically.
              </p>
            </div>
            <div className="flex gap-2">
              <Button variant="primary" size="sm" onClick={() => setModal({ mode: "new" })}>
                <Plus size={12} aria-hidden /> Start
              </Button>
              <Button variant="outline" size="sm">
                <Code size={12} aria-hidden /> Read SDK docs →
              </Button>
            </div>
          </div>
        </div>
          </>
        )}
      </div>
      <ConnectModal open={modal !== null} modal={modal} onClose={() => setModal(null)} />
    </AppShell>
  );
}
