"use client";

/**
 * /projects/new — Create a new migration project.
 *
 * Refreshed visual layout using the operations-console token system.
 * Posts to `${API_BASE}/api/v1/projects` (unchanged from the previous version).
 */

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Sparkles, X, Wand2 } from "lucide-react";

import { AppShell } from "@/components/layout";
import { Button, Card, ErrorBanner, Chip } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import {
  cloneMigrationTemplate,
  listMigrationTemplates,
  type TemplateSummary,
} from "@/lib/migration-templates/api";
import { fetchProjectMembers, type OrgMember } from "@/lib/projects/api";
import { CONNECTOR_FIELDS, CONNECTOR_LABELS } from "@/lib/projects/connections";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface MigTypeSpec { value: string; label: string; source_kinds: string[]; target_kinds: string[]; }

const ENVIRONMENTS = [
  { value: "dev",  label: "Dev" },
  { value: "stg",  label: "Staging" },
  { value: "prod", label: "Production" },
];

export default function NewProjectPage() {
  const { token } = useAuth();
  const router = useRouter();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [sourceSystem, setSourceSystem] = useState("");
  const [targetSystem, setTargetSystem] = useState("");
  const [environment, setEnvironment] = useState("dev");
  const [ownerId, setOwnerId] = useState("");   // "" = me (creator)
  const [status, setStatus] = useState("draft");
  const [migrationType, setMigrationType] = useState("db_to_db");
  const [migTypes, setMigTypes] = useState<MigTypeSpec[]>([]);
  const [connKinds, setConnKinds] = useState<Record<string, string>>({});

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string>("");
  const [members, setMembers] = useState<OrgMember[]>([]);

  useEffect(() => {
    if (!token) return;
    listMigrationTemplates(token).then(setTemplates).catch(() => setTemplates([]));
    fetchProjectMembers().then(setMembers).catch(() => setMembers([]));
    fetch(`${API_BASE}/api/v1/migration-types`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d) { setMigTypes(d.types || []); setConnKinds(d.connector_kinds || {}); } })
      .catch(() => {});
  }, [token]);

  // Connectors valid for a side = those whose kind the chosen type allows.
  // Mirrors the Source & Target page so the project is provisioned with real,
  // type-valid connectors (not stale free-text systems).
  const spec = migTypes.find((t) => t.value === migrationType);
  const connectorsFor = (kinds: string[] | undefined) =>
    Object.keys(CONNECTOR_FIELDS).filter((ct) => !kinds || kinds.includes(connKinds[ct] ?? "db"));
  const sourceSystems = connectorsFor(spec?.source_kinds);
  const targetSystems = connectorsFor(spec?.target_kinds);

  // When the type changes, drop a source/target that's no longer valid.
  useEffect(() => {
    if (sourceSystem && !sourceSystems.includes(sourceSystem)) setSourceSystem("");
    if (targetSystem && !targetSystems.includes(targetSystem)) setTargetSystem("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [migrationType, migTypes, connKinds]);

  const handleTemplate = async (tplId: string) => {
    if (!token || !name.trim()) {
      setError("Set a project name before cloning a template.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const out = await cloneMigrationTemplate(token, tplId, name.trim(), description.trim() || undefined);
      router.push(`/projects/${out.project_id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Template clone failed");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Project name is required.");
      return;
    }
    if (!sourceSystem) {
      setError("Pick a source system.");
      return;
    }
    if (!targetSystem) {
      setError("Pick a target system.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/projects`, {
        method: "POST",
        credentials: "include", // SC-010: auth via HttpOnly cookie
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name,
          description,
          source_system: sourceSystem || undefined,
          target_system: targetSystem || undefined,
          environment,
          owner_id: ownerId || undefined,
          status,
          migration_type: migrationType,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to create project");
      }
      const project = await res.json();
      router.push(`/projects/${project.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AppShell
      eyebrow="ENTERPRISE MIGRATIONS"
      title="New migration project"
      description="Define scope, source/target systems, and ownership for a new run."
      crumbs={[{ label: "Projects", href: "/projects" }, { label: "New" }]}
      actions={
        // UI-034 — while the create POST is in flight, render Cancel as a
        // disabled Button (not a live Link) so a click can't navigate away and
        // race the API callback.
        loading ? (
          <Button variant="outline" disabled>
            <X className="h-3.5 w-3.5" /> Cancel
          </Button>
        ) : (
          <Link href="/projects">
            <Button variant="outline">
              <X className="h-3.5 w-3.5" /> Cancel
            </Button>
          </Link>
        )
      }
    >
      <div className="max-w-3xl">
        {error && (
          <div className="mb-4">
            <ErrorBanner message={error} onDismiss={() => setError("")} />
          </div>
        )}

        {templates.length > 0 && (
          <Card
            title="Start from a template"
            description="Pre-baked starter packs include source/target defaults, validation rules, and agent prompt overrides. Provide a project name first, then click a template."
            className="mb-4"
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
              {templates.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => { setSelectedTemplate(t.id); void handleTemplate(t.id); }}
                  disabled={loading}
                  className={`text-left p-3 rounded-[8px] border ${
                    selectedTemplate === t.id ? "border-ink bg-app-2" : "border-hx hover:bg-app-2"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <Wand2 className="h-3.5 w-3.5 text-[var(--con-brand)]" />
                    <span className="text-[13px] font-medium text-ink">{t.name}</span>
                    <Chip tone={t.risk_level === "high" ? "err" : t.risk_level === "medium" ? "amber" : "default"}>{t.risk_level}</Chip>
                  </div>
                  <p className="text-[11.5px] text-ink-3 line-clamp-3">{t.summary}</p>
                </button>
              ))}
            </div>
          </Card>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <Card
            title="Project basics"
            description="Visible name and short description for the team."
          >
            <div className="flex flex-col gap-4">
              <Field label="Project name" required>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  placeholder="e.g. Oracle GL → Snowflake"
                  className="w-full h-9 rounded-[7px] border border-hx bg-surface px-3 text-[13px] text-ink focus-ring"
                />
              </Field>

              <Field label="Description">
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={3}
                  placeholder="Migrate the general-ledger schema into Snowflake with full row-level reconciliation."
                  className="w-full rounded-[7px] border border-hx bg-surface px-3 py-2 text-[13px] text-ink focus-ring resize-none"
                />
              </Field>

              <Field label="Migration type">
                <select
                  value={migrationType}
                  onChange={(e) => setMigrationType(e.target.value)}
                  className="w-full h-9 rounded-[7px] border border-hx bg-surface px-3 text-[13px] text-ink focus-ring"
                >
                  {(migTypes.length ? migTypes : [{ value: "db_to_db", label: "Database → Database" }]).map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
                <span className="text-[11.5px] text-ink-4 mt-1 block">
                  Drives the connectors, schema discovery, and pipeline steps for this project.
                </span>
              </Field>
            </div>
          </Card>

          <Card
            title="Source and target"
            description="Pick the systems Helix will read from and write to."
          >
            <div className="grid grid-cols-2 gap-4">
              <Field label="Source system" required>
                <select
                  value={sourceSystem}
                  onChange={(e) => setSourceSystem(e.target.value)}
                  required
                  className="w-full h-9 rounded-[7px] border border-hx bg-surface px-3 text-[13px] text-ink focus-ring font-mono"
                >
                  <option value="">Select source…</option>
                  {sourceSystems.map((s) => (
                    <option key={s} value={s}>{CONNECTOR_LABELS[s] ?? s}</option>
                  ))}
                </select>
              </Field>

              <Field label="Target system" required>
                <select
                  value={targetSystem}
                  onChange={(e) => setTargetSystem(e.target.value)}
                  required
                  className="w-full h-9 rounded-[7px] border border-hx bg-surface px-3 text-[13px] text-ink focus-ring font-mono"
                >
                  <option value="">Select target…</option>
                  {targetSystems.map((s) => (
                    <option key={s} value={s}>{CONNECTOR_LABELS[s] ?? s}</option>
                  ))}
                </select>
              </Field>
            </div>
          </Card>

          <Card
            title="Environment"
            description="Which environment will this project operate against?"
          >
            <div className="flex flex-wrap gap-2">
              {ENVIRONMENTS.map((env) => {
                const active = environment === env.value;
                return (
                  <label
                    key={env.value}
                    className={`inline-flex items-center gap-2 px-3 h-9 rounded-[7px] cursor-pointer border text-[12.5px] transition-colors ${
                      active
                        ? "border-ink bg-app-2 text-ink font-medium"
                        : "border-hx bg-surface text-ink-2 hover:bg-app-2"
                    }`}
                  >
                    <input
                      type="radio"
                      name="environment"
                      value={env.value}
                      checked={active}
                      onChange={() => setEnvironment(env.value)}
                      className="sr-only"
                    />
                    <span
                      className={`inline-block w-2 h-2 rounded-full ${
                        active ? "bg-ink" : "bg-ink-5"
                      }`}
                    />
                    {env.label}
                  </label>
                );
              })}
            </div>
            <div className="mt-3 text-[11.5px] text-ink-4">
              <Chip tone="brand" dot>Tip</Chip>{" "}
              Production runs require a second-signer approval gate before any
              destructive write.
            </div>
          </Card>

          <Card title="Ownership & status" description="Assign the project owner and its initial status.">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="Owner">
                <select
                  value={ownerId}
                  onChange={(e) => setOwnerId(e.target.value)}
                  className="w-full h-9 px-2.5 text-[13px] rounded-[8px] border border-hx bg-surface focus-ring"
                >
                  <option value="">Me (creator)</option>
                  {members.map((m) => (
                    <option key={m.user_id} value={m.user_id}>{m.name || m.email}</option>
                  ))}
                </select>
              </Field>
              <Field label="Initial status">
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  className="w-full h-9 px-2.5 text-[13px] rounded-[8px] border border-hx bg-surface focus-ring"
                >
                  {["draft", "running", "awaiting", "completed", "failed", "archived"].map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </Field>
            </div>
          </Card>

          <div className="flex justify-end gap-2.5">
            <Button
              type="button"
              variant="outline"
              onClick={() => router.push("/projects")}
            >
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={loading}>
              <Sparkles className="h-3.5 w-3.5" /> Create project
            </Button>
          </div>
        </form>
      </div>
    </AppShell>
  );
}

// ─── Helpers ───────────────────────────────────────────────────

/**
 * Field — auto-binds htmlFor/id to its single child <input>/<select>/
 * <textarea> via React.cloneElement, so callers don't have to thread an
 * id by hand. Decorative asterisk has aria-hidden + an sr-only "(required)"
 * hint; the child input gets aria-required when required is true.
 */
function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  const autoId = React.useId();
  // If the child is a single form element, clone it with id + aria-required.
  const child = React.isValidElement(children)
    ? React.cloneElement(children as React.ReactElement<{ id?: string; "aria-required"?: boolean }>, {
        id: (children.props as { id?: string }).id ?? autoId,
        ...(required ? { "aria-required": true } : {}),
      })
    : children;
  return (
    <div>
      <label
        htmlFor={(child as React.ReactElement<{ id?: string }>)?.props?.id ?? autoId}
        className="block text-[11.5px] uppercase tracking-[0.08em] font-mono text-ink-4 mb-1.5"
      >
        {label}
        {required && (
          <>
            <span aria-hidden className="text-err ml-1">*</span>
            <span className="sr-only"> (required)</span>
          </>
        )}
      </label>
      {child}
    </div>
  );
}
