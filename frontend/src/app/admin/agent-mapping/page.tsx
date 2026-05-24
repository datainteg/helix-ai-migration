"use client";

import { useEffect, useState, useCallback } from "react";
import { Save, Check } from "lucide-react";
import { AdminShell } from "@/components/layout";
import { LLMIcon, AgentIcon } from "@/components/icons";
import { Card, Button, Chip, ErrorBanner } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Mirrors backend AGENT_TYPES in backend/app/services/llm_router_service.py.
// Six official BMAD agents — codes match _bmad/config.toml.
const AGENT_TYPES: { id: string; name: string; role: string }[] = [
  { id: "bmad-agent-analyst",     name: "Mary — Business Analyst",        role: "Analysis" },
  { id: "bmad-agent-tech-writer", name: "Paige — Technical Writer",       role: "Documentation" },
  { id: "bmad-agent-pm",          name: "John — Product Manager",         role: "Planning" },
  { id: "bmad-agent-ux-designer", name: "Sally — UX Designer",            role: "UX" },
  { id: "bmad-agent-architect",   name: "Winston — System Architect",     role: "Architecture" },
  { id: "bmad-agent-dev",         name: "Amelia — Senior Software Engineer", role: "Implementation" },
];

interface LLMProvider {
  id: string;
  name: string;
  provider_type: string;
  default_model: string;
  status: string;
}

interface AgentMapping {
  agent_type: string;
  provider_id: string;
  model: string;
  temperature: number;
  max_tokens: number;
}

export default function AgentMappingPage() {
  const { token } = useAuth();
  const [mode, setMode] = useState<"simple" | "advanced">("advanced");
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [mappings, setMappings] = useState<Record<string, AgentMapping>>({});
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [error, setError] = useState("");

  const authHeader: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

  const loadProviders = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/llm-providers`, { headers: authHeader });
      if (res.ok) setProviders(await res.json());
    } catch { /* ignore */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const loadMappings = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/llm-agent-mappings`, { headers: authHeader });
      if (!res.ok) return;
      const rows: AgentMapping[] = await res.json();
      const next: Record<string, AgentMapping> = {};
      rows.forEach((r) => { next[r.agent_type] = r; });
      setMappings(next);
    } catch { /* ignore */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    loadProviders();
    loadMappings();
  }, [loadProviders, loadMappings]);

  const updateMapping = (agentType: string, patch: Partial<AgentMapping>) => {
    setMappings((prev) => ({
      ...prev,
      [agentType]: {
        agent_type: agentType,
        provider_id: prev[agentType]?.provider_id || providers[0]?.id || "",
        model: prev[agentType]?.model || providers[0]?.default_model || "",
        temperature: prev[agentType]?.temperature ?? 0.2,
        max_tokens: prev[agentType]?.max_tokens ?? 4096,
        ...patch,
      },
    }));
  };

  const handleSave = async () => {
    if (!token) return;
    setSaving(true);
    setError("");
    setSavedAt(null);
    try {
      // In simple mode, propagate the analyst mapping to every agent.
      const payload: AgentMapping[] = [];
      const baseMapping = mode === "simple" ? mappings["bmad-agent-analyst"] : null;
      AGENT_TYPES.forEach((a) => {
        const m = mode === "simple" && baseMapping
          ? { ...baseMapping, agent_type: a.id }
          : mappings[a.id];
        if (m && m.provider_id) payload.push(m);
      });
      if (payload.length === 0) {
        throw new Error("No mappings to save — pick a provider for at least one agent.");
      }
      const res = await fetch(`${API_BASE}/api/v1/llm-agent-mappings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...authHeader },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Save failed" }));
        throw new Error(err.detail || "Save failed");
      }
      setSavedAt(Date.now());
      await loadMappings();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <AdminShell
      title="Agent Model Mapping"
      subtitle="Route each BMAD agent to a provider and model. Simple mode: one model for all. Advanced: per-agent control."
      actions={
        <Button onClick={handleSave} loading={saving}>
          {savedAt ? <Check className="h-4 w-4" /> : <Save className="h-4 w-4" />}
          {savedAt ? "Saved" : "Save Mapping"}
        </Button>
      }
    >
      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      <Card title="Routing mode" description="Pick how migrations should select models for each agent role.">
        <div className="flex gap-3">
          {(["simple", "advanced"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`flex-1 rounded-[10px] border px-5 py-4 text-left transition-colors ${
                mode === m
                  ? "border-hx-2 bg-[var(--con-brand-soft)]"
                  : "border-hx hover:bg-surface-hi"
              }`}
            >
              <div className="text-[13.5px] font-semibold text-ink capitalize">{m} mode</div>
              <div className="text-[12px] text-ink-3 mt-0.5">
                {m === "simple"
                  ? "Same model for all 6 BMAD agents. Lowest cost surface."
                  : "Different model per agent. Use a cheap model for Mary, a strong one for Winston."}
              </div>
            </button>
          ))}
        </div>
      </Card>

      <Card title="Agent → Provider · Model" description="Per-agent routing and tuning" bodyClassName="p-0">
        <table className="w-full text-[13px] border-t border-hx">
          <thead className="bg-surface-hi text-[10.5px] uppercase tracking-[0.08em] text-ink-4 font-mono">
            <tr>
              <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Agent</th>
              <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Role</th>
              <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Provider</th>
              <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Model</th>
              <th className="px-4 py-2.5 text-right font-medium border-b border-hx">Temperature</th>
              <th className="px-4 py-2.5 text-right font-medium border-b border-hx">Max Tokens</th>
              <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Status</th>
            </tr>
          </thead>
          <tbody>
            {AGENT_TYPES.map((a) => {
              const map = mappings[a.id];
              const disabled = mode === "simple" && a.id !== "bmad-agent-analyst";
              const selectedProvider = providers.find((p) => p.id === map?.provider_id);
              return (
                <tr key={a.id} className="border-b border-hx last:border-b-0 hover:bg-surface-hi">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <AgentIcon name={a.id} size={20} />
                      <span className="font-medium text-ink">{a.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3"><Chip tone="brand">{a.role}</Chip></td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      {selectedProvider && (
                        <LLMIcon provider={selectedProvider.provider_type} size={18} />
                      )}
                      <select
                        value={map?.provider_id || ""}
                        onChange={(e) => updateMapping(a.id, { provider_id: e.target.value })}
                        disabled={disabled}
                        className="rounded-[8px] border border-hx bg-surface px-2 py-1 text-[12.5px] focus-ring disabled:opacity-50"
                      >
                        <option value="">— Select provider —</option>
                        {providers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                      </select>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <input
                      type="text"
                      value={map?.model || ""}
                      onChange={(e) => updateMapping(a.id, { model: e.target.value })}
                      placeholder="model id"
                      disabled={disabled}
                      className="w-40 rounded-[8px] border border-hx bg-surface px-2 py-1 text-[12px] font-mono focus-ring disabled:opacity-50"
                    />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      max="2"
                      value={map?.temperature ?? 0.2}
                      onChange={(e) => updateMapping(a.id, { temperature: parseFloat(e.target.value) })}
                      disabled={disabled}
                      className="w-16 rounded-[8px] border border-hx bg-surface px-2 py-1 text-[12px] text-right font-mono focus-ring disabled:opacity-50"
                    />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <input
                      type="number"
                      value={map?.max_tokens ?? 4096}
                      onChange={(e) => updateMapping(a.id, { max_tokens: parseInt(e.target.value, 10) })}
                      disabled={disabled}
                      className="w-20 rounded-[8px] border border-hx bg-surface px-2 py-1 text-[12px] text-right font-mono focus-ring disabled:opacity-50"
                    />
                  </td>
                  <td className="px-4 py-3"><Chip tone={map?.provider_id ? "ok" : "warn"} dot>{map?.provider_id ? "Mapped" : "Unset"}</Chip></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
    </AdminShell>
  );
}
