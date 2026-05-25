/**
 * @helix/sdk — TypeScript client for the Helix Migration REST API.
 *
 * Mirrors the Python SDK surface so the two stay version-locked.
 *
 * Usage:
 *   import { Helix } from "@helix/sdk";
 *   const helix = new Helix({ apiUrl: "https://helix.example.com" });
 *   await helix.login("you@org.com", "<password>");
 *   const projects = await helix.projects.list();
 */

export interface HelixOptions {
  apiUrl: string;
  token?: string;
  timeoutMs?: number;
}

export class HelixError extends Error {
  status: number;
  detail: string;
  path: string;
  constructor(status: number, detail: string, path: string) {
    super(`${status} ${detail} (${path})`);
    this.status = status;
    this.detail = detail;
    this.path = path;
  }
}

export class Helix {
  apiUrl: string;
  token: string;
  timeoutMs: number;
  projects: Projects;
  workflows: Workflows;
  cost: Cost;
  templates: Templates;
  cutovers: Cutovers;
  knowledge: Knowledge;
  schemaDrift: SchemaDrift;
  artifacts: Artifacts;

  constructor(opts: HelixOptions) {
    this.apiUrl = opts.apiUrl.replace(/\/$/, "");
    this.token = opts.token ?? "";
    this.timeoutMs = opts.timeoutMs ?? 30_000;
    this.projects = new Projects(this);
    this.workflows = new Workflows(this);
    this.cost = new Cost(this);
    this.templates = new Templates(this);
    this.cutovers = new Cutovers(this);
    this.knowledge = new Knowledge(this);
    this.schemaDrift = new SchemaDrift(this);
    this.artifacts = new Artifacts(this);
  }

  async login(email: string, password: string): Promise<{ access_token: string }> {
    const res = await this._raw("POST", "/api/v1/auth/login", { email, password }, { skipAuth: true });
    this.token = res.access_token;
    return res;
  }

  async whoami(): Promise<unknown> {
    return this._raw("GET", "/api/v1/auth/me");
  }

  async _raw(method: string, path: string, body?: unknown, opts?: { skipAuth?: boolean }): Promise<any> {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (!opts?.skipAuth) {
      if (!this.token) throw new HelixError(401, "No token; call login() first", path);
      headers["Authorization"] = `Bearer ${this.token}`;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const res = await fetch(`${this.apiUrl}${path}`, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
      });
      const text = await res.text();
      if (!res.ok) {
        let detail = res.statusText;
        try { detail = JSON.parse(text).detail ?? detail; } catch { /* ignore */ }
        throw new HelixError(res.status, detail, path);
      }
      return text ? JSON.parse(text) : {};
    } finally {
      clearTimeout(timer);
    }
  }
}

class Resource {
  constructor(protected client: Helix) {}
}

class Projects extends Resource {
  list() { return this.client._raw("GET", "/api/v1/projects?limit=200"); }
  get(id: string) { return this.client._raw("GET", `/api/v1/projects/${id}`); }
  create(name: string, description = "") { return this.client._raw("POST", "/api/v1/projects", { name, description }); }
}

class Workflows extends Resource {
  start(project_id: string, requirement_id: string, requirement_text = "") {
    return this.client._raw("POST", `/api/v1/projects/${project_id}/agent-workflows`, { requirement_id, requirement_text });
  }
  status(workflow_id: string) { return this.client._raw("GET", `/api/v1/agent-workflows/${workflow_id}`); }
  list(project_id?: string) {
    return project_id
      ? this.client._raw("GET", `/api/v1/projects/${project_id}/agent-workflows?limit=100`)
      : this.client._raw("GET", "/api/v1/agent-workflows?limit=100");
  }
  approve(workflow_id: string, notes = "") {
    return this.client._raw("POST", `/api/v1/agent-workflows/${workflow_id}/signal-approve`, { decision: "approved", notes });
  }
  reject(workflow_id: string, notes = "") {
    return this.client._raw("POST", `/api/v1/agent-workflows/${workflow_id}/signal-reject`, { decision: "rejected", notes });
  }
  replay(workflow_id: string, opts: { agent_prompt_overrides?: Record<string, string>; model_override?: string } = {}) {
    return this.client._raw("POST", `/api/v1/workflows/${workflow_id}/replay`, opts);
  }
}

class Cost extends Resource {
  summary(days = 30) { return this.client._raw("GET", `/api/v1/usage/llm?days=${days}`); }
  limit() { return this.client._raw("GET", "/api/v1/usage/cost-limit"); }
  setLimit(d: { daily_usd_cap?: number; monthly_usd_cap?: number; enforcement?: "hard" | "soft" } = {}) {
    return this.client._raw("PUT", "/api/v1/usage/cost-limit", {
      daily_usd_cap: d.daily_usd_cap ?? 0,
      monthly_usd_cap: d.monthly_usd_cap ?? 0,
      enforcement: d.enforcement ?? "hard",
    });
  }
}

class Templates extends Resource {
  list() { return this.client._raw("GET", "/api/v1/migration-templates"); }
  clone(template_id: string, project_name: string, project_description?: string) {
    return this.client._raw("POST", "/api/v1/migration-templates/clone", { template_id, project_name, project_description });
  }
}

class Cutovers extends Resource {
  list(project_id: string) { return this.client._raw("GET", `/api/v1/projects/${project_id}/cutovers`); }
  create(project_id: string, source_ref: string, target_ref: string, notes?: string) {
    return this.client._raw("POST", `/api/v1/projects/${project_id}/cutovers`, { source_ref, target_ref, notes });
  }
  transition(cutover_id: string, target_state: string, notes = "") {
    return this.client._raw("POST", `/api/v1/cutovers/${cutover_id}/transition`, { target_state, notes });
  }
}

class Knowledge extends Resource {
  upload(d: { title: string; content: string; source_url?: string; tags?: string }) {
    return this.client._raw("POST", "/api/v1/knowledge/docs", d);
  }
  search(q: string, limit = 5) { return this.client._raw("GET", `/api/v1/knowledge/search?q=${encodeURIComponent(q)}&limit=${limit}`); }
}

class SchemaDrift extends Resource {
  snapshot(project_id: string, source_ref: string, payload: { schemas: string[]; tables: any[] }) {
    return this.client._raw("POST", `/api/v1/projects/${project_id}/sources/${encodeURIComponent(source_ref)}/schema-snapshots`, payload);
  }
  drift(project_id: string, source_ref: string) {
    return this.client._raw("GET", `/api/v1/projects/${project_id}/sources/${encodeURIComponent(source_ref)}/drift`);
  }
}

class Artifacts extends Resource {
  listForProject(project_id: string) { return this.client._raw("GET", `/api/v1/projects/${project_id}/artifacts`); }
  generateRollback(artifact_id: string) { return this.client._raw("POST", `/api/v1/artifacts/${artifact_id}/generate-rollback`); }
  pairReview(artifact_id: string, opts: { reviewer_model?: string; reviewer_provider_type?: string } = {}) {
    return this.client._raw("POST", `/api/v1/artifacts/${artifact_id}/pair-review`, opts);
  }
}
