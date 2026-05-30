/**
 * LLM usage + cost cap client.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

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
