/**
 * Migration template catalog + clone helper.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface TemplateSummary {
  id: string;
  name: string;
  source: string;
  target: string;
  summary: string;
  risk_level: string;
  recon_threshold_pct: number;
  validation_rules: { rule_type: string; definition: string }[];
}

export interface TemplateCloneResponse {
  project_id: string;
  validation_rule_ids: string[];
  agent_prompts: Record<string, string>;
  recon_threshold_pct: number | null;
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

export function listMigrationTemplates(token: string | null): Promise<TemplateSummary[]> {
  return req<TemplateSummary[]>("/api/v1/migration-templates", token);
}

export function cloneMigrationTemplate(
  token: string | null,
  template_id: string,
  project_name: string,
  project_description?: string,
): Promise<TemplateCloneResponse> {
  return req<TemplateCloneResponse>("/api/v1/migration-templates/clone", token, {
    method: "POST",
    body: JSON.stringify({ template_id, project_name, project_description }),
  });
}
