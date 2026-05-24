"use client";

/**
 * /projects/new — Create a new migration project.
 *
 * Refreshed visual layout using the operations-console token system.
 * Posts to `${API_BASE}/api/v1/projects` (unchanged from the previous version).
 */

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Sparkles, X } from "lucide-react";

import { AppShell } from "@/components/layout";
import { Button, Card, ErrorBanner, Chip } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const SOURCE_SYSTEMS = [
  "oracle", "sqlserver", "mysql", "postgres", "db2",
  "sas", "datastage", "salesforce", "snowflake", "databricks",
];

const TARGET_SYSTEMS = [
  "snowflake", "databricks", "bigquery", "postgres", "s3",
  "iceberg", "dbt", "redshift",
];

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

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/projects`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name,
          description,
          source_system: sourceSystem || undefined,
          target_system: targetSystem || undefined,
          environment,
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
        <Link href="/projects">
          <Button variant="outline">
            <X className="h-3.5 w-3.5" /> Cancel
          </Button>
        </Link>
      }
    >
      <div className="max-w-3xl">
        {error && (
          <div className="mb-4">
            <ErrorBanner message={error} onDismiss={() => setError("")} />
          </div>
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
            </div>
          </Card>

          <Card
            title="Source and target"
            description="Pick the systems Helix will read from and write to."
          >
            <div className="grid grid-cols-2 gap-4">
              <Field label="Source system">
                <select
                  value={sourceSystem}
                  onChange={(e) => setSourceSystem(e.target.value)}
                  className="w-full h-9 rounded-[7px] border border-hx bg-surface px-3 text-[13px] text-ink focus-ring font-mono"
                >
                  <option value="">Select source…</option>
                  {SOURCE_SYSTEMS.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </Field>

              <Field label="Target system">
                <select
                  value={targetSystem}
                  onChange={(e) => setTargetSystem(e.target.value)}
                  className="w-full h-9 rounded-[7px] border border-hx bg-surface px-3 text-[13px] text-ink focus-ring font-mono"
                >
                  <option value="">Select target…</option>
                  {TARGET_SYSTEMS.map((s) => (
                    <option key={s} value={s}>{s}</option>
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

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-[11.5px] uppercase tracking-[0.08em] font-mono text-ink-4 mb-1.5">
        {label}
        {required && <span className="text-err ml-1">*</span>}
      </label>
      {children}
    </div>
  );
}
