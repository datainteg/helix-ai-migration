"use client";

import { useAuth } from "@/lib/auth-context";
import { useEffect, useCallback, useState } from "react";
import { Plus, Check, X, BrainCircuit } from "lucide-react";
import { AdminShell } from "@/components/layout";
import { LLMIcon } from "@/components/icons";
import { Card, Button, Chip, StatusBadge, ErrorBanner, LoadingState, EmptyState } from "@/components/ui";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Provider {
  id: string;
  name: string;
  provider_type: string;
  base_url: string | null;
  default_model: string;
  api_key_masked: string;
  status: string;
}

interface CatalogueEntry {
  provider_type: string;
  models: string[];
  default_base_url: string;
}

const PROVIDER_LABELS: Record<string, string> = {
  openai: "OpenAI / ChatGPT",
  anthropic: "Anthropic Claude",
  google: "Google Gemini",
  deepseek: "DeepSeek",
  openrouter: "OpenRouter",
  local: "Local Model (Ollama / LM Studio)",
  custom: "Custom OpenAI-compatible API",
};

const EMPTY_FORM = { provider_type: "openai", name: "", base_url: "", default_model: "", api_key: "" };

export default function LLMSettingsPage() {
  const { token } = useAuth();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [catalogue, setCatalogue] = useState<Record<string, CatalogueEntry>>({});
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [testResult, setTestResult] = useState<{ id: string; success: boolean; message: string } | null>(null);
  const [error, setError] = useState("");

  const authHeader: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

  const fetchProviders = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/llm-providers`, { headers: authHeader });
      if (res.ok) setProviders(await res.json());
    } catch { /* ignore */ }
    setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    fetchProviders();
    fetch(`${API_BASE}/api/v1/llm-providers/catalogue`, { headers: authHeader })
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
      default_model: entry?.models[0] || "",
    }));
  };

  const addProvider = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/v1/llm-providers`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeader },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Failed to add provider" }));
        throw new Error(err.detail || "Failed to add provider");
      }
      setShowAdd(false);
      setForm(EMPTY_FORM);
      fetchProviders();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add provider");
    }
  };

  const testConnection = async (id: string) => {
    setTestResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/llm-providers/${id}/test`, {
        method: "POST",
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

  return (
    <AdminShell
      title="LLM Providers"
      subtitle="Configure and manage AI providers, models, and routing for your migration agents."
      actions={
        <Button onClick={() => { setShowAdd((v) => !v); setError(""); }}>
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
        <Card title="Add Provider" description="Configure a new LLM provider for agents to use.">
          <form onSubmit={addProvider} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-[12.5px] font-medium text-ink-2 mb-1.5">Provider type</label>
                <select
                  value={form.provider_type}
                  onChange={(e) => handleProviderTypeChange(e.target.value)}
                  className="w-full h-10 rounded-[8px] border border-hx bg-surface px-3 text-[13.5px] focus-ring"
                >
                  {Object.entries(PROVIDER_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-[12.5px] font-medium text-ink-2 mb-1.5">Display name</label>
                <input
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  className="w-full h-10 rounded-[8px] border border-hx bg-surface px-3.5 text-[13.5px] focus-ring"
                  placeholder="e.g. OpenAI Prod"
                  required
                />
              </div>
              <div>
                <label className="block text-[12.5px] font-medium text-ink-2 mb-1.5">Base URL</label>
                <input
                  value={form.base_url}
                  onChange={(e) => setForm((f) => ({ ...f, base_url: e.target.value }))}
                  className="w-full h-10 rounded-[8px] border border-hx bg-surface px-3.5 text-[13.5px] font-mono focus-ring"
                  placeholder="Auto-filled from provider type"
                />
              </div>
              <div>
                <label className="block text-[12.5px] font-medium text-ink-2 mb-1.5">Default model</label>
                {availableModels.length > 0 ? (
                  <select
                    value={form.default_model}
                    onChange={(e) => setForm((f) => ({ ...f, default_model: e.target.value }))}
                    className="w-full h-10 rounded-[8px] border border-hx bg-surface px-3 text-[13.5px] font-mono focus-ring"
                    required
                  >
                    {availableModels.map((m) => <option key={m} value={m}>{m}</option>)}
                  </select>
                ) : (
                  <input
                    value={form.default_model}
                    onChange={(e) => setForm((f) => ({ ...f, default_model: e.target.value }))}
                    className="w-full h-10 rounded-[8px] border border-hx bg-surface px-3.5 text-[13.5px] font-mono focus-ring"
                    placeholder="Enter model name"
                    required
                  />
                )}
              </div>
            </div>
            <div>
              <label className="block text-[12.5px] font-medium text-ink-2 mb-1.5">API key</label>
              <input
                type="password"
                value={form.api_key}
                onChange={(e) => setForm((f) => ({ ...f, api_key: e.target.value }))}
                className="w-full h-10 rounded-[8px] border border-hx bg-surface px-3.5 text-[13.5px] font-mono focus-ring"
                placeholder={form.provider_type === "anthropic" ? "sk-ant-…" : "sk-…"}
                required
              />
              {form.provider_type === "deepseek" && (
                <p className="mt-1.5 text-[11.5px] text-ink-3">
                  Get your API key at <span className="font-mono">platform.deepseek.com</span>.
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
                <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Base URL</th>
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
                  <td className="px-4 py-3 font-mono text-[12px] text-ink-3 truncate max-w-[200px]">{p.base_url || "—"}</td>
                  <td className="px-4 py-3 font-mono text-[12px] text-ink-3">{p.api_key_masked}</td>
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
    </AdminShell>
  );
}
