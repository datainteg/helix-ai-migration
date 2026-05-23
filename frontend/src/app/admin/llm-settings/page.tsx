"use client";

import { useAuth } from "@/lib/auth-context";
import { useEffect, useCallback, useState } from "react";

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
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
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
      .then((r) => r.ok ? r.json() : [])
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
    } catch (err: unknown) {
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
      setTestResult(result);
    } catch {
      setTestResult({ success: false, message: "Connection test failed" });
    }
  };

  const availableModels = catalogue[form.provider_type]?.models ?? [];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">LLM Provider Settings</h1>
        <button
          onClick={() => { setShowAdd(!showAdd); setError(""); }}
          className="rounded-lg bg-helix-600 px-4 py-2 text-sm font-medium text-white hover:bg-helix-700"
        >
          {showAdd ? "Cancel" : "Add Provider"}
        </button>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 px-4 py-2 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}
      {testResult && (
        <div className={`rounded-lg px-4 py-2 text-sm border ${testResult.success ? "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800 text-green-700 dark:text-green-400" : "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800 text-red-700 dark:text-red-400"}`}>
          {testResult.success ? "✓" : "✗"} {testResult.message}
        </div>
      )}

      {showAdd && (
        <form onSubmit={addProvider} className="rounded-xl border dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm space-y-4">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100">Add Provider</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Provider Type</label>
              <select
                value={form.provider_type}
                onChange={(e) => handleProviderTypeChange(e.target.value)}
                className="w-full rounded-lg border dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm"
              >
                {Object.entries(PROVIDER_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Name</label>
              <input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                className="w-full rounded-lg border dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm"
                placeholder="My Provider"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Base URL</label>
              <input
                value={form.base_url}
                onChange={(e) => setForm((f) => ({ ...f, base_url: e.target.value }))}
                className="w-full rounded-lg border dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm"
                placeholder="Auto-filled from provider type"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Default Model</label>
              {availableModels.length > 0 ? (
                <select
                  value={form.default_model}
                  onChange={(e) => setForm((f) => ({ ...f, default_model: e.target.value }))}
                  className="w-full rounded-lg border dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm"
                  required
                >
                  {availableModels.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              ) : (
                <input
                  value={form.default_model}
                  onChange={(e) => setForm((f) => ({ ...f, default_model: e.target.value }))}
                  className="w-full rounded-lg border dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm"
                  placeholder="Enter model name"
                  required
                />
              )}
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">API Key</label>
            <input
              type="password"
              value={form.api_key}
              onChange={(e) => setForm((f) => ({ ...f, api_key: e.target.value }))}
              className="w-full rounded-lg border dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm"
              placeholder={form.provider_type === "anthropic" ? "sk-ant-..." : "sk-..."}
              required
            />
            {form.provider_type === "deepseek" && (
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                Get your API key at <span className="font-mono">platform.deepseek.com</span>. Supports deepseek-chat (V3), deepseek-reasoner (R1), and deepseek-coder.
              </p>
            )}
          </div>
          <button type="submit" className="rounded-lg bg-helix-600 px-4 py-2 text-sm font-medium text-white hover:bg-helix-700">
            Save Provider
          </button>
        </form>
      )}

      {loading ? (
        <div className="text-center py-8 text-gray-500 dark:text-gray-400">Loading providers...</div>
      ) : providers.length === 0 ? (
        <div className="rounded-xl border dark:border-gray-800 bg-white dark:bg-gray-900 p-12 shadow-sm text-center text-gray-500 dark:text-gray-400">
          No providers configured. Add your first LLM provider above.
        </div>
      ) : (
        <div className="space-y-3">
          {providers.map((p) => (
            <div key={p.id} className="rounded-xl border dark:border-gray-800 bg-white dark:bg-gray-900 p-4 shadow-sm flex items-center justify-between">
              <div>
                <p className="font-medium text-sm text-gray-900 dark:text-gray-100">{p.name}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {PROVIDER_LABELS[p.provider_type] || p.provider_type} • {p.default_model} • Key: {p.api_key_masked}
                  {p.base_url && <span className="ml-1 text-gray-400 dark:text-gray-500">• {p.base_url}</span>}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-xs px-2 py-1 rounded-full ${p.status === "active" ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" : "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400"}`}>
                  {p.status}
                </span>
                <button onClick={() => testConnection(p.id)} className="text-xs text-helix-600 hover:underline">
                  Test
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
