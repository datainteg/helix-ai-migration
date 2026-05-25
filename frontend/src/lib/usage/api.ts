/**
 * LLM usage + cost cap client.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface UsageSummary {
  window_days: number;
  input_tokens: number;
  output_tokens: number;
  total_cost_usd: number;
  by_provider: { provider: string; cost_usd: number }[];
  by_agent: { agent: string; cost_usd: number }[];
  by_project: { project_id: string; cost_usd: number }[];
}

export interface CostLimit {
  daily_usd_cap: number;
  monthly_usd_cap: number;
  enforcement: "hard" | "soft";
  configured: boolean;
}

async function req<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
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

export function fetchUsageSummary(token: string, days = 30): Promise<UsageSummary> {
  return req<UsageSummary>(`/api/v1/usage/llm?days=${days}`, token);
}

export interface DailyCostPoint { date: string; cost_usd: number }

export function fetchDailyCost(token: string, days = 30): Promise<DailyCostPoint[]> {
  return req<DailyCostPoint[]>(`/api/v1/usage/llm/daily?days=${days}`, token);
}

export function fetchCostLimit(token: string): Promise<CostLimit> {
  return req<CostLimit>(`/api/v1/usage/cost-limit`, token);
}

export function updateCostLimit(token: string, data: Omit<CostLimit, "configured">): Promise<CostLimit> {
  return req<CostLimit>(`/api/v1/usage/cost-limit`, token, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}
