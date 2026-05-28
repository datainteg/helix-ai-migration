/**
 * @helix/sdk — TypeScript client for the Helix Migration REST API.
 *
 * Mirrors the Python SDK surface so the two stay version-locked.
 *
 * Pagination envelope (v0.2.0+)
 * --------------------------------
 * Converted list endpoints now return `{items: T[], total: number|null,
 * limit: number, offset: number}` instead of a bare array.  All `.list()`
 * methods silently unwrap the envelope so existing callers keep working.
 * Call the companion `.paginated()` / `.listPaginated()` methods when you
 * need `total` / paging metadata.
 *
 * Usage:
 *   import { Helix, PaginatedResponse } from "@helix/sdk";
 *   const helix = new Helix({ apiUrl: "https://helix.example.com" });
 *   await helix.login("you@org.com", "<password>");
 *   const projects = await helix.projects.list();           // T[] back-compat
 *   const page = await helix.projects.paginated();          // PaginatedResponse<T>
 */

export interface HelixOptions {
  apiUrl: string;
  token?: string;
  timeoutMs?: number;
}

/** Shape returned by converted list endpoints (v0.2.0+). */
export interface PaginatedResponse<T = Record<string, unknown>> {
  items: T[];
  total: number | null;
  limit: number;
  offset: number;
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

/**
 * Unwrap a pagination envelope or pass through a bare array.
 * Returns the `items` array for back-compat `.list()` callers.
 */
function unwrap<T>(data: unknown): T[] {
  if (data !== null && typeof data === "object" && !Array.isArray(data) && "items" in (data as object)) {
    return (data as PaginatedResponse<T>).items;
  }
  return (data as T[]) ?? [];
}

/**
 * Coerce any response (envelope or bare array) to a {@link PaginatedResponse}.
 */
function asPaginated<T>(data: unknown): PaginatedResponse<T> {
  if (data !== null && typeof data === "object" && !Array.isArray(data) && "items" in (data as object)) {
    const d = data as PaginatedResponse<T>;
    return {
      items: d.items,
      total: d.total ?? null,
      limit: d.limit,
      offset: d.offset,
    };
  }
  // bare-array fallback
  const items: T[] = Array.isArray(data) ? (data as T[]) : [];
  return { items, total: items.length, limit: items.length, offset: 0 };
}

/**
 * Walk pagination envelopes by `offset` until all rows are collected (H-011).
 *
 * Callers of `.list()` previously saw at most the server-side cap (100/200).
 * `.listAll()` helpers delegate to this loop so they fetch every page
 * transparently. Guarded by `maxPages` to prevent runaway requests.
 */
async function paginateAll<T>(
  fetchPage: (offset: number) => Promise<PaginatedResponse<T>>,
  maxPages = 100,
): Promise<T[]> {
  const collected: T[] = [];
  let offset = 0;
  for (let i = 0; i < maxPages; i++) {
    const page = await fetchPage(offset);
    const items = page.items ?? [];
    collected.push(...items);
    const pageSize = page.limit || items.length || 1;
    if (page.total !== null && page.total !== undefined && collected.length >= page.total) break;
    if (items.length === 0 || items.length < pageSize) break;
    offset += pageSize;
  }
  return collected;
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

  /** GET *path* and return a {@link PaginatedResponse} regardless of whether
   *  the server sends a bare array or a pagination envelope. */
  async _getPaginated<T = Record<string, unknown>>(path: string): Promise<PaginatedResponse<T>> {
    return asPaginated<T>(await this._raw("GET", path));
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
  private static PAGE_SIZE = 200;
  /**
   * Return the first page of projects (max `PAGE_SIZE` rows).
   *
   * H-011: server-paginated; use {@link paginated} for `total` metadata or
   * {@link listAll} to walk every page transparently.
   */
  async list(): Promise<Record<string, unknown>[]> {
    return unwrap(await this.client._raw("GET", `/api/v1/projects?limit=${Projects.PAGE_SIZE}`));
  }
  async paginated(offset = 0): Promise<PaginatedResponse> {
    return asPaginated(
      await this.client._raw("GET", `/api/v1/projects?limit=${Projects.PAGE_SIZE}&offset=${offset}`),
    );
  }
  /** Walk all pages and return every project (H-011). */
  async listAll(): Promise<Record<string, unknown>[]> {
    return paginateAll<Record<string, unknown>>((off) => this.paginated(off));
  }
  get(id: string) { return this.client._raw("GET", `/api/v1/projects/${id}`); }
  create(name: string, description = "") { return this.client._raw("POST", "/api/v1/projects", { name, description }); }
}

class Workflows extends Resource {
  private static PAGE_SIZE = 100;
  start(project_id: string, requirement_id: string, requirement_text = "") {
    return this.client._raw("POST", `/api/v1/projects/${project_id}/agent-workflows`, { requirement_id, requirement_text });
  }
  status(workflow_id: string) { return this.client._raw("GET", `/api/v1/agent-workflows/${workflow_id}`); }
  /**
   * Return the first page of workflows (max `PAGE_SIZE` rows).
   *
   * H-011: server-paginated; use {@link paginated} for `total` metadata or
   * {@link listAll} to walk every page transparently.
   */
  async list(project_id?: string): Promise<Record<string, unknown>[]> {
    const path = project_id
      ? `/api/v1/projects/${project_id}/agent-workflows?limit=${Workflows.PAGE_SIZE}`
      : `/api/v1/agent-workflows?limit=${Workflows.PAGE_SIZE}`;
    return unwrap(await this.client._raw("GET", path));
  }
  async paginated(project_id?: string, offset = 0): Promise<PaginatedResponse> {
    const path = project_id
      ? `/api/v1/projects/${project_id}/agent-workflows?limit=${Workflows.PAGE_SIZE}&offset=${offset}`
      : `/api/v1/agent-workflows?limit=${Workflows.PAGE_SIZE}&offset=${offset}`;
    return asPaginated(await this.client._raw("GET", path));
  }
  /** Walk all pages and return every workflow (H-011). */
  async listAll(project_id?: string): Promise<Record<string, unknown>[]> {
    return paginateAll<Record<string, unknown>>((off) => this.paginated(project_id, off));
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
  /**
   * Return the full migration-template catalog.
   *
   * Note: the catalog is a static in-memory list — the endpoint returns
   * every entry in one bare-array response (no server-side paging).
   * {@link listAll} is provided for API symmetry and returns the same set.
   */
  async list(): Promise<Record<string, unknown>[]> {
    return unwrap(await this.client._raw("GET", "/api/v1/migration-templates"));
  }
  async paginated(): Promise<PaginatedResponse> {
    return asPaginated(await this.client._raw("GET", "/api/v1/migration-templates"));
  }
  /** Return the full template catalog (H-011 symmetry helper). */
  async listAll(): Promise<Record<string, unknown>[]> {
    return paginateAll<Record<string, unknown>>(() => this.paginated());
  }
  clone(template_id: string, project_name: string, project_description?: string) {
    return this.client._raw("POST", "/api/v1/migration-templates/clone", { template_id, project_name, project_description });
  }
}

class Cutovers extends Resource {
  private static PAGE_SIZE = 100;
  /**
   * Return the first page of cutovers for a project.
   *
   * H-011: server-paginated; use {@link listAll} to walk every page.
   */
  async list(project_id: string): Promise<Record<string, unknown>[]> {
    return unwrap(await this.client._raw("GET", `/api/v1/projects/${project_id}/cutovers?limit=${Cutovers.PAGE_SIZE}`));
  }
  async paginated(project_id: string, offset = 0): Promise<PaginatedResponse> {
    return asPaginated(
      await this.client._raw(
        "GET",
        `/api/v1/projects/${project_id}/cutovers?limit=${Cutovers.PAGE_SIZE}&offset=${offset}`,
      ),
    );
  }
  /** Walk all pages and return every cutover for a project (H-011). */
  async listAll(project_id: string): Promise<Record<string, unknown>[]> {
    return paginateAll<Record<string, unknown>>((off) => this.paginated(project_id, off));
  }
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
  /**
   * Return the top-`limit` matching knowledge docs.
   *
   * Note: `/knowledge/search` is a relevance-ranked top-N endpoint, NOT an
   * offset-paginated list (server caps `limit` at 20). There is no
   * `searchAll` because the endpoint never returns more than the top-N you
   * ask for — raise `limit` (up to 20) to widen the result set.
   */
  async search(q: string, limit = 5): Promise<Record<string, unknown>[]> {
    return unwrap(await this.client._raw("GET", `/api/v1/knowledge/search?q=${encodeURIComponent(q)}&limit=${limit}`));
  }
  async searchPaginated(q: string, limit = 5): Promise<PaginatedResponse> {
    return asPaginated(await this.client._raw("GET", `/api/v1/knowledge/search?q=${encodeURIComponent(q)}&limit=${limit}`));
  }
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
  private static PAGE_SIZE = 100;
  /**
   * Return the first page of artifacts for a project.
   *
   * H-011: server-paginated; use {@link listAllForProject} to walk every page.
   */
  async listForProject(project_id: string): Promise<Record<string, unknown>[]> {
    return unwrap(await this.client._raw("GET", `/api/v1/projects/${project_id}/artifacts?limit=${Artifacts.PAGE_SIZE}`));
  }
  async listForProjectPaginated(project_id: string, offset = 0): Promise<PaginatedResponse> {
    return asPaginated(
      await this.client._raw(
        "GET",
        `/api/v1/projects/${project_id}/artifacts?limit=${Artifacts.PAGE_SIZE}&offset=${offset}`,
      ),
    );
  }
  /** Walk all pages and return every artifact for a project (H-011). */
  async listAllForProject(project_id: string): Promise<Record<string, unknown>[]> {
    return paginateAll<Record<string, unknown>>((off) => this.listForProjectPaginated(project_id, off));
  }
  generateRollback(artifact_id: string) { return this.client._raw("POST", `/api/v1/artifacts/${artifact_id}/generate-rollback`); }
  pairReview(artifact_id: string, opts: { reviewer_model?: string; reviewer_provider_type?: string } = {}) {
    return this.client._raw("POST", `/api/v1/artifacts/${artifact_id}/pair-review`, opts);
  }
}
