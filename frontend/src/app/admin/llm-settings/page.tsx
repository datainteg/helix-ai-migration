"use client";

import { useAuth } from "@/lib/auth-context";
import { useEffect, useState } from "react";

interface Provider {
  id: string;
  name: string;
  provider_type: string;
  base_url: string | null;
  default_model: string;
  api_key_masked: string;
  status: string;
}

const PROVIDER_LABELS: Record<string, string> = {
  openai: "OpenAI / ChatGPT",
  deepseek: "DeepSeek",
  openrouter: "OpenRouter",
  anthropic: "Anthropic Claude",
  google: "Google Gemini",
  custom: "Custom OpenAI-compatible API",
  local: "Local Model URL",
};

export default function LLMSettingsPage() {
  const { token } = useAuth();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ provider_type: "openai", name: "", base_url: "", default_model: "", api_key: "" });
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [error, setError] = useState("");

  const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const fetchProviders = async () => {
    if (!token) return;
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/v1/llm-providers`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) setProviders(await res.json());
    } catch { /* ignore */ }
    setLoading(false);
  };

  useEffect(() => { fetchProviders(); }, [token]);

  const addProvider = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const res = await fetch(`${API}/api/v1/llm-providers`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(form),
      });
      if (!res.ok) { const err = await res.json(); throw new Error(err.detail); }
      setShowAdd(false);
      setForm({ provider_type: "openai", name: "", base_url: "", default_model: "", api_key: "" });
      fetchProviders();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to add provider");
    }
  };

  const testConnection = async (id: string) => {
    setTestResult(null);
    try {
      const res = await fetch(`${API}/api/v1/llm-providers/${id}/test`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      setTestResult(await res.json());
    } catch {
      setTestResult({ success: false, message: "Connection test failed" });
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">LLM Provider Settings</h1>
        <button onClick={() => setShowAdd(!showAdd)} className="rounded-lg bg-helix-600 px-4 py-2 text-sm font-medium text-white hover:bg-helix-700">
          {showAdd ? "Cancel" : "Add Provider"}
        </button>
      </div>

      {error && <div className="rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700">{error}</div>}
      {testResult && (
        <div className={`rounded-lg px-4 py-2 text-sm ${testResult.success ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
          {testResult.message}
        </div>
      )}

      {showAdd && (
        <form onSubmit={addProvider} className="rounded-xl border bg-white p-6 shadow-sm space-y-4">
          <h3 className="font-semibold">Add Provider</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Provider Type</label>
              <select value={form.provider_type} onChange={(e) => setForm((f) => ({ ...f, provider_type: e.target.value }))} className="w-full rounded-lg border px-3 py-2 text-sm">
                {Object.entries(PROVIDER_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Name</label>
              <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} className="w-full rounded-lg border px-3 py-2 text-sm" placeholder="My Provider" required />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Base URL</label>
              <input value={form.base_url} onChange={(e) => setForm((f) => ({ ...f, base_url: e.target.value }))} className="w-full rounded-lg border px-3 py-2 text-sm" placeholder="https://api.openai.com/v1" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Default Model</label>
              <input value={form.default_model} onChange={(e) => setForm((f) => ({ ...f, default_model: e.target.value }))} className="w-full rounded-lg border px-3 py-2 text-sm" placeholder="gpt-4.1" required />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">API Key</label>
            <input type="password" value={form.api_key} onChange={(e) => setForm((f) => ({ ...f, api_key: e.target.value }))} className="w-full rounded-lg border px-3 py-2 text-sm" placeholder="sk-..." required />
          </div>
          <button type="submit" className="rounded-lg bg-helix-600 px-4 py-2 text-sm font-medium text-white hover:bg-helix-700">Save Provider</button>
        </form>
      )}

      {loading ? (
        <div className="text-center py-8 text-gray-500">Loading providers...</div>
      ) : providers.length === 0 ? (
        <div className="rounded-xl border bg-white p-12 shadow-sm text-center text-gray-500">No providers configured. Add your first LLM provider.</div>
      ) : (
        <div className="space-y-3">
          {providers.map((p) => (
            <div key={p.id} className="rounded-xl border bg-white p-4 shadow-sm flex items-center justify-between">
              <div>
                <p className="font-medium text-sm">{p.name}</p>
                <p className="text-xs text-gray-500">{PROVIDER_LABELS[p.provider_type] || p.provider_type} • {p.default_model} • Key: {p.api_key_masked}</p>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-xs px-2 py-1 rounded ${p.status === "active" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>{p.status}</span>
                <button onClick={() => testConnection(p.id)} className="text-xs text-helix-600 hover:underline">Test</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
