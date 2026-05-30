"use client";

import { useAuth } from "@/lib/auth-context";
import { useEffect, useCallback, useId, useState } from "react";
import { Plus, Check, X, BrainCircuit } from "lucide-react";
import { AppShell } from "@/components/layout";
import { LLMIcon } from "@/components/icons";
import { Card, Button, StatusBadge, ErrorBanner, LoadingState, EmptyState } from "@/components/ui";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface Provider {
  id: string;
  name: string;
  provider_type: string;
  base_url: string | null;
  default_model: string;
  api_key_masked: string;
  status: string;
  extra_config?: Record<string, string> | null;
}

interface CatalogueEntry {
  provider_type: string;
  models: string[];
  default_base_url: string;
  default_model?: string;
}

const PROVIDER_LABELS: Record<string, string> = {
  anthropic:  "Anthropic Claude",
  openai:     "OpenAI / ChatGPT",
  google:     "Google Gemini API",
  deepseek:   "DeepSeek",
  openrouter: "OpenRouter",
  bedrock:    "AWS Bedrock",
  vertex:     "Google Vertex AI",
  azure:      "Azure OpenAI",
  local:      "Local (Ollama / LM Studio)",
  custom:     "Custom OpenAI-compatible",
};

// Provider types that don't require a user-supplied API key (auth via IAM / ADC).
const KEYLESS_PROVIDERS = new Set(["bedrock", "vertex"]);

interface FormState {
  provider_type: string;
  name: string;
  base_url: string;
  default_model: string;
  api_key: string;
  extra_config: Record<string, string>;
}

const EMPTY_FORM: FormState = {
  provider_type: "anthropic",
  name: "",
  base_url: "",
  default_model: "",
  api_key: "",
  extra_config: {},
};

export default function LLMSettingsPage() {
  const { token } = useAuth();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [catalogue, setCatalogue] = useState<Record<string, CatalogueEntry>>({});
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [editingProviderId, setEditingProviderId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [testResult, setTestResult] = useState<{ id: string; success: boolean; message: string } | null>(null);
  const [error, setError] = useState("");

  // Stable ids for form fields — unique even if the component renders twice.
  const uid = useId();
  const fieldId = (name: string) => `${uid}-${name}`;

  // SC-010: auth now rides on the HttpOnly cookie (credentials:"include"); the
  // Authorization header is no longer used. `authHeader` is kept as an empty
  // object so the existing `...authHeader` spreads remain harmless no-ops.
  const authHeader: Record<string, string> = {};

  const fetchProviders = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/llm-providers`, { credentials: "include", headers: authHeader });
      if (res.ok) setProviders(await res.json());
    } catch { /* ignore */ }
    setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    fetchProviders();
    fetch(`${API_BASE}/api/v1/llm-providers/catalogue`, { credentials: "include", headers: authHeader })
      .then((r) => (r.ok ? r.json() : []))
      .then((entries: CatalogueEntry[]) => {
        const map: Record<string, CatalogueEntry> = {};
        entries.forEach((e) => { map[e.provider_type] = e; });
        setCatalogue(map);
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchProviders]);

  const handleProviderTypeChange = (ptype: string) => {
    const entry = catalogue[ptype];
    setForm((f) => ({
      ...f,
      provider_type: ptype,
      base_url: entry?.default_base_url || "",
      default_model: entry?.default_model || entry?.models[0] || "",
      extra_config: {}, // reset so prev provider's fields don't leak
    }));
  };

  const setExtra = (k: string, v: string) =>
    setForm((f) => ({ ...f, extra_config: { ...f.extra_config, [k]: v } }));

  const cleanedExtraConfig = (cfg: Record<string, string>) =>
    Object.fromEntries(Object.entries(cfg).filter(([, v]) => v !== ""));

  const closeForm = () => {
    setShowAdd(false);
    setEditingProviderId(null);
    setForm(EMPTY_FORM);
    setError("");
  };

  const startEdit = (p: Provider) => {
    setEditingProviderId(p.id);
    setForm({
      provider_type: p.provider_type,
      name: p.name,
      base_url: p.base_url ?? "",
      default_model: p.default_model,
      // API key is blank on edit — leaving it blank means "don't rotate".
      api_key: "",
      extra_config: (p.extra_config ?? {}) as Record<string, string>,
    });
    setShowAdd(true);
    setError("");
    setTestResult(null);
  };

  const addProvider = async (form: FormState) => {
    const payload = { ...form, extra_config: cleanedExtraConfig(form.extra_config) };
    const res = await fetch(`${API_BASE}/api/v1/llm-providers`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...authHeader },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Failed to add provider" }));
      throw new Error(err.detail || "Failed to add provider");
    }
  };

  const updateProvider = async (id: string, form: FormState) => {
    const patchBody: Record<string, unknown> = {
      name: form.name,
      base_url: form.base_url,
      default_model: form.default_model,
      status: "active",
      extra_config: cleanedExtraConfig(form.extra_config),
    };
    const res = await fetch(`${API_BASE}/api/v1/llm-providers/${id}`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...authHeader },
      body: JSON.stringify(patchBody),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Failed to update provider" }));
      throw new Error(err.detail || "Failed to update provider");
    }
    if (form.api_key.trim() !== "") {
      const rotateRes = await fetch(`${API_BASE}/api/v1/llm-providers/${id}/rotate-key`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", ...authHeader },
        body: JSON.stringify({ new_api_key: form.api_key }),
      });
      if (!rotateRes.ok) {
        const err = await rotateRes.json().catch(() => ({ detail: "Failed to rotate API key" }));
        throw new Error(err.detail || "Failed to rotate API key");
      }
    }
  };

  const submitForm = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      if (editingProviderId) {
        await updateProvider(editingProviderId, form);
      } else {
        await addProvider(form);
      }
      closeForm();
      fetchProviders();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save provider");
    }
  };

  const testConnection = async (id: string) => {
    setTestResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/llm-providers/${id}/test`, {
        method: "POST",
        credentials: "include",
        headers: authHeader,
      });
      if (!res.ok) throw new Error("Connection test failed");
      const result: { success: boolean; message: string } = await res.json();
      setTestResult({ id, ...result });
    } catch {
      setTestResult({ id, success: false, message: "Connection test failed" });
    }
  };

  const availableModels = catalogue[form.provider_type]?.models ?? [];
  const apiKeyRequired = !KEYLESS_PROVIDERS.has(form.provider_type);

  return (
    <AppShell
      title="LLM Providers"
      crumbs={["LLM Providers"]}
      subtitle="Configure and manage AI providers, models, and routing for your migration agents."
      actions={
        <Button
          onClick={() => {
            if (showAdd) {
              closeForm();
            } else {
              setEditingProviderId(null);
              setForm(EMPTY_FORM);
              setShowAdd(true);
              setError("");
            }
          }}
        >
          {showAdd ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
          {showAdd ? "Cancel" : "Add Provider"}
        </Button>
      }
    >
      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}
      {testResult && (
        <div
          className={`rounded-[10px] px-4 py-3 text-[13px] border ${
            testResult.success
              ? "bg-[var(--con-ok-soft)] border-hx text-ok"
              : "bg-[var(--con-err-soft)] border-hx text-err"
          }`}
        >
          {testResult.success ? <Check className="inline h-4 w-4 -mt-0.5 mr-1.5" /> : <X className="inline h-4 w-4 -mt-0.5 mr-1.5" />}
          {testResult.message}
        </div>
      )}

      {showAdd && (
        <Card
          title={editingProviderId ? `Edit Provider — ${form.name || "—"}` : "Add Provider"}
          description={
            editingProviderId
              ? "Update this provider's settings. Leave the API key blank to keep the current one."
              : "Configure a new LLM provider for agents to use."
          }
        >
          <form onSubmit={submitForm} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label htmlFor={fieldId("provider-type")} className="block text-[12.5px] font-medium text-ink-2 mb-1.5">Provider type</label>
                <select
                  id={fieldId("provider-type")}
                  value={form.provider_type}
                  onChange={(e) => handleProviderTypeChange(e.target.value)}
                  className="w-full h-10 rounded-[8px] border border-hx bg-surface px-3 text-[13.5px] focus-ring disabled:opacity-60 disabled:cursor-not-allowed"
                  disabled={!!editingProviderId}
                >
                  {Object.entries(PROVIDER_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor={fieldId("name")} className="block text-[12.5px] font-medium text-ink-2 mb-1.5">Display name</label>
                <input
                  id={fieldId("name")}
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  className="w-full h-10 rounded-[8px] border border-hx bg-surface px-3.5 text-[13.5px] focus-ring"
                  placeholder="e.g. Anthropic Prod"
                  required
                />
              </div>
              {/* Base URL — hidden for SDK-managed providers (bedrock/vertex/azure use extra_config). */}
              {!["bedrock", "vertex", "azure"].includes(form.provider_type) && (
                <div>
                  <label htmlFor={fieldId("base-url")} className="block text-[12.5px] font-medium text-ink-2 mb-1.5">Base URL</label>
                  <input
                    id={fieldId("base-url")}
                    value={form.base_url}
                    onChange={(e) => setForm((f) => ({ ...f, base_url: e.target.value }))}
                    className="w-full h-10 rounded-[8px] border border-hx bg-surface px-3.5 text-[13.5px] font-mono focus-ring"
                    placeholder="Auto-filled from provider type"
                  />
                </div>
              )}
              <div>
                <label htmlFor={fieldId("default-model")} className="block text-[12.5px] font-medium text-ink-2 mb-1.5">Default model</label>
                {availableModels.length > 0 ? (
                  <select
                    id={fieldId("default-model")}
                    value={form.default_model}
                    onChange={(e) => setForm((f) => ({ ...f, default_model: e.target.value }))}
                    className="w-full h-10 rounded-[8px] border border-hx bg-surface px-3 text-[13.5px] font-mono focus-ring"
                    required
                  >
                    {availableModels.map((m) => <option key={m} value={m}>{m}</option>)}
                  </select>
                ) : (
                  <input
                    id={fieldId("default-model")}
                    value={form.default_model}
                    onChange={(e) => setForm((f) => ({ ...f, default_model: e.target.value }))}
                    className="w-full h-10 rounded-[8px] border border-hx bg-surface px-3.5 text-[13.5px] font-mono focus-ring"
                    placeholder="Enter model name"
                    required
                  />
                )}
              </div>
            </div>

            {/* Provider-specific extra_config */}
            <ExtraConfigFields ptype={form.provider_type} values={form.extra_config} onChange={setExtra} />

            <div>
              <label htmlFor={fieldId("api-key")} className="block text-[12.5px] font-medium text-ink-2 mb-1.5">
                API key{" "}
                {editingProviderId ? (
                  <span className="text-ink-4 font-normal">(leave blank to keep current)</span>
                ) : !apiKeyRequired ? (
                  <span className="text-ink-4 font-normal">(optional — uses IAM / ADC)</span>
                ) : null}
              </label>
              <input
                id={fieldId("api-key")}
                type="password"
                value={form.api_key}
                onChange={(e) => setForm((f) => ({ ...f, api_key: e.target.value }))}
                className="w-full h-10 rounded-[8px] border border-hx bg-surface px-3.5 text-[13.5px] font-mono focus-ring"
                placeholder={
                  editingProviderId                   ? "Leave blank to keep current key" :
                  form.provider_type === "anthropic"  ? "sk-ant-…" :
                  form.provider_type === "azure"      ? "Azure OpenAI key" :
                  apiKeyRequired                      ? "sk-…" :
                                                        "Leave blank to use cloud auth"
                }
                required={!editingProviderId && apiKeyRequired}
              />
              {form.provider_type === "deepseek" && (
                <p className="mt-1.5 text-[11.5px] text-ink-3">
                  Get your API key at <span className="font-mono">platform.deepseek.com</span>.
                </p>
              )}
              {form.provider_type === "bedrock" && (
                <p className="mt-1.5 text-[11.5px] text-ink-3">
                  Leave blank if the worker runs with an IAM role; otherwise paste an access key ID below
                  and use the API key field for the secret.
                </p>
              )}
              {form.provider_type === "vertex" && (
                <p className="mt-1.5 text-[11.5px] text-ink-3">
                  Vertex uses Application Default Credentials. Set <span className="font-mono">GOOGLE_APPLICATION_CREDENTIALS</span> in the worker
                  env, then fill in the GCP project below.
                </p>
              )}
            </div>

            <div className="flex justify-end gap-2.5">
              <Button type="button" variant="outline" onClick={() => setShowAdd(false)}>Cancel</Button>
              <Button type="submit" variant="primary">Save Provider</Button>
            </div>
          </form>
        </Card>
      )}

      {loading ? (
        <LoadingState label="Loading providers…" />
      ) : providers.length === 0 ? (
        <EmptyState
          icon={<BrainCircuit className="h-5 w-5" />}
          title="No providers configured"
          description="Add your first LLM provider to start routing agent traffic."
          action={<Button onClick={() => setShowAdd(true)}><Plus className="h-4 w-4" /> Add Provider</Button>}
        />
      ) : (
        <Card bodyClassName="p-0">
          <table className="w-full text-[13px] border-t border-hx">
            <thead className="bg-surface-hi text-[10.5px] uppercase tracking-[0.08em] text-ink-4 font-mono">
              <tr>
                <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Provider</th>
                <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Default Model</th>
                <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Endpoint</th>
                <th className="px-4 py-2.5 text-left font-medium border-b border-hx">API Key</th>
                <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Status</th>
                <th className="px-4 py-2.5 text-right font-medium border-b border-hx"></th>
              </tr>
            </thead>
            <tbody>
              {providers.map((p) => (
                <tr key={p.id} className="border-b border-hx last:border-b-0 hover:bg-surface-hi">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <LLMIcon provider={p.provider_type} size={20} />
                      <div>
                        <p className="font-medium text-ink">{p.name}</p>
                        <p className="text-[11.5px] text-ink-3">{PROVIDER_LABELS[p.provider_type] || p.provider_type}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono text-[12px] text-ink-2">{p.default_model}</td>
                  <td className="px-4 py-3 font-mono text-[12px] text-ink-3 truncate max-w-[240px]">
                    {endpointSummary(p)}
                  </td>
                  <td className="px-4 py-3 font-mono text-[12px] text-ink-3">{p.api_key_masked || "—"}</td>
                  <td className="px-4 py-3"><StatusBadge status={p.status} /></td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => testConnection(p.id)} className="text-[12.5px] text-[var(--con-brand)] hover:underline">
                      Test connection
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </AppShell>
  );
}

// ── Provider-specific extra_config fields ────────────────────────────

function ExtraConfigFields({
  ptype,
  values,
  onChange,
}: {
  ptype: string;
  values: Record<string, string>;
  onChange: (k: string, v: string) => void;
}) {
  if (ptype === "bedrock") {
    return (
      <ExtraFieldset title="AWS Bedrock">
        <ExtraInput label="AWS region" value={values.aws_region ?? ""} onChange={(v) => onChange("aws_region", v)} placeholder="us-east-1" />
        <ExtraInput label="Access key ID (optional)" value={values.aws_access_key_id ?? ""} onChange={(v) => onChange("aws_access_key_id", v)} placeholder="AKIA…" mono />
        <ExtraInput label="Session token (optional)" value={values.aws_session_token ?? ""} onChange={(v) => onChange("aws_session_token", v)} placeholder="for STS / IAM-role users" mono />
        <p className="md:col-span-2 text-[11.5px] text-ink-3">
          The secret key goes in the API key field above. Leave both blank if the worker container assumes an IAM role.
        </p>
      </ExtraFieldset>
    );
  }
  if (ptype === "vertex") {
    return (
      <ExtraFieldset title="Google Vertex AI">
        <ExtraInput label="GCP project" value={values.gcp_project ?? ""} onChange={(v) => onChange("gcp_project", v)} placeholder="my-gcp-project" mono required />
        <ExtraInput label="Location" value={values.gcp_location ?? ""} onChange={(v) => onChange("gcp_location", v)} placeholder="us-central1" mono />
      </ExtraFieldset>
    );
  }
  if (ptype === "azure") {
    return (
      <ExtraFieldset title="Azure OpenAI">
        <ExtraInput label="Azure endpoint" value={values.azure_endpoint ?? ""} onChange={(v) => onChange("azure_endpoint", v)} placeholder="https://my-resource.openai.azure.com" mono required />
        <ExtraInput label="API version" value={values.api_version ?? ""} onChange={(v) => onChange("api_version", v)} placeholder="2026-01-01" mono />
        <ExtraInput label="Deployment name" value={values.deployment_name ?? ""} onChange={(v) => onChange("deployment_name", v)} placeholder="gpt-5.5-prod" mono required />
      </ExtraFieldset>
    );
  }
  return null;
}

function ExtraFieldset({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <fieldset className="border border-hx rounded-[10px] p-4">
      <legend className="px-2 text-[10.5px] uppercase tracking-[0.08em] font-mono text-ink-4">{title}</legend>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{children}</div>
    </fieldset>
  );
}

function ExtraInput({
  label,
  value,
  onChange,
  placeholder,
  mono,
  required,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  mono?: boolean;
  required?: boolean;
}) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="block text-[12.5px] font-medium text-ink-2 mb-1.5">
        {label}
        {required && <span className="text-err"> *</span>}
      </label>
      <input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        className={`w-full h-10 rounded-[8px] border border-hx bg-surface px-3.5 text-[13.5px] focus-ring ${mono ? "font-mono" : ""}`}
      />
    </div>
  );
}

function endpointSummary(p: Provider): string {
  if (p.provider_type === "bedrock") {
    return `bedrock · ${p.extra_config?.aws_region ?? "us-east-1"}`;
  }
  if (p.provider_type === "vertex") {
    const project = p.extra_config?.gcp_project ?? "";
    const loc = p.extra_config?.gcp_location ?? "us-central1";
    return `vertex · ${project}/${loc}`;
  }
  if (p.provider_type === "azure") {
    return p.extra_config?.azure_endpoint ?? "azure";
  }
  return p.base_url || "—";
}
