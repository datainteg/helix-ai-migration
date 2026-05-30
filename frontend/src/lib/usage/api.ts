/**
 * LLM usage + cost cap client.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export interface AgentUsage {
  agent: string;
  cost_usd: number;
  input_tokens: number;
  output_tokens: number;
  call_count: number;
}

export interface UsageSummary {
  window_days: number;
  input_tokens: number;
  output_tokens: number;
  total_cost_usd: number;
  by_provider: { provider: string; cost_usd: number }[];
  by_agent: AgentUsage[];
  by_project: { project_id: string; cost_usd: number }[];
}

export interface CostLimit {
  daily_usd_cap: number;
  monthly_usd_cap: number;
  enforcement: "hard" | "soft";
  configured: boolean;
}

export type BudgetScope = "agent" | "project";

export interface CostBudget {
  scope: BudgetScope;
  scope_key: string;
  daily_usd_cap: number;
  monthly_usd_cap: number;
  enforcement: "hard" | "soft";
}

// SC-010: auth rides on the HttpOnly cookie (`credentials: "include"`). The
// `token` params are retained for call-site compatibility but unused.
async function req<T>(path: string, _token: string | null, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail || `${path} → ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function fetchUsageSummary(token: string | null, days = 30): Promise<UsageSummary> {
  return req<UsageSummary>(`/api/v1/usage/llm?days=${days}`, token);
}

export interface DailyCostPoint { date: string; cost_usd: number }

export function fetchDailyCost(token: string | null, days = 30): Promise<DailyCostPoint[]> {
  return req<DailyCostPoint[]>(`/api/v1/usage/llm/daily?days=${days}`, token);
}

export function fetchCostLimit(token: string | null): Promise<CostLimit> {
  return req<CostLimit>(`/api/v1/usage/cost-limit`, token);
}

export function updateCostLimit(token: string | null, data: Omit<CostLimit, "configured">): Promise<CostLimit> {
  return req<CostLimit>(`/api/v1/usage/cost-limit`, token, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

/* ---------------------------- per-agent / per-project budgets ---------------------------- */

export function fetchBudgets(token: string | null, scope: BudgetScope): Promise<CostBudget[]> {
  return req<CostBudget[]>(`/api/v1/usage/budgets?scope=${scope}`, token);
}

export function upsertBudget(token: string | null, data: CostBudget): Promise<CostBudget> {
  return req<CostBudget>(`/api/v1/usage/budgets`, token, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export function deleteBudget(token: string | null, scope: BudgetScope, scopeKey: string): Promise<void> {
  return req<void>(`/api/v1/usage/budgets?scope=${scope}&scope_key=${encodeURIComponent(scopeKey)}`, token, {
    method: "DELETE",
  });
}

/** Known (AGENT_TYPES) ∪ observed agent codes, for the budget picker. */
export function fetchKnownAgents(token: string | null): Promise<{ agents: string[] }> {
  return req<{ agents: string[] }>(`/api/v1/usage/agents`, token);
}

/** Trigger a browser download of the per-agent / per-day usage CSV. */
export async function downloadUsageCsv(days = 30): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/usage/llm/export.csv?days=${days}`, { credentials: "include" });
  if (!res.ok) throw new Error(`Export failed (${res.status})`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `helix-usage-${days}d.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
