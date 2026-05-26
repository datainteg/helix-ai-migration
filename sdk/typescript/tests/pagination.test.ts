/**
 * Tests for pagination-envelope handling in the TypeScript SDK.
 *
 * Uses a minimal fetch mock so no real server is required.  Verifies:
 *   - Envelope `{items, total, limit, offset}` is transparently unwrapped by
 *     every `.list()` method (back-compat guarantee).
 *   - The companion `.paginated()` helpers return the full PaginatedResponse.
 *   - Bare-array responses (endpoints not yet converted) continue to work.
 *   - `_getPaginated()` synthesises a consistent envelope from a bare array.
 */

import { Helix, HelixError, PaginatedResponse } from "../src/index";

// ---------------------------------------------------------------------------
// Minimal fetch mock
// ---------------------------------------------------------------------------

type FetchMock = (url: string, init?: RequestInit) => Promise<Response>;

function makeFetch(payload: unknown, status = 200): FetchMock {
  return async (_url: string, _init?: RequestInit) => {
    const body = JSON.stringify(payload);
    return {
      ok: status >= 200 && status < 300,
      status,
      statusText: status === 200 ? "OK" : "Error",
      text: async () => body,
    } as unknown as Response;
  };
}

function makeHelix(fetchFn: FetchMock): Helix {
  const h = new Helix({ apiUrl: "http://test.local", token: "tok" });
  // @ts-ignore — inject mock fetch
  h["_fetchImpl"] = fetchFn;
  return h;
}

/**
 * Patch the global `fetch` used by _raw() for the duration of the callback.
 */
async function withFetch<T>(fetchFn: FetchMock, fn: (h: Helix) => Promise<T>): Promise<T> {
  const orig = globalThis.fetch;
  globalThis.fetch = fetchFn as typeof fetch;
  try {
    const h = new Helix({ apiUrl: "http://test.local", token: "tok" });
    return await fn(h);
  } finally {
    globalThis.fetch = orig;
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Pagination unwrap helpers", () => {
  const envelope: PaginatedResponse = { items: [{ id: "1" }], total: 1, limit: 50, offset: 0 };
  const bare = [{ id: "2" }];

  test("workflows.list() unwraps envelope", async () => {
    const result = await withFetch(makeFetch(envelope), (h) => h.workflows.list());
    expect(result).toEqual([{ id: "1" }]);
  });

  test("workflows.list() passes through bare array", async () => {
    const result = await withFetch(makeFetch(bare), (h) => h.workflows.list());
    expect(result).toEqual(bare);
  });

  test("workflows.paginated() returns full envelope from envelope", async () => {
    const result = await withFetch(makeFetch(envelope), (h) => h.workflows.paginated());
    expect(result.total).toBe(1);
    expect(result.limit).toBe(50);
    expect(result.offset).toBe(0);
    expect(result.items).toEqual([{ id: "1" }]);
  });

  test("workflows.paginated() synthesises envelope from bare array", async () => {
    const result = await withFetch(makeFetch(bare), (h) => h.workflows.paginated());
    expect(result.items).toEqual(bare);
    expect(result.total).toBe(1);
    expect(result.offset).toBe(0);
  });

  test("cutovers.list() unwraps envelope", async () => {
    const result = await withFetch(makeFetch(envelope), (h) => h.cutovers.list("proj-1"));
    expect(result).toEqual([{ id: "1" }]);
  });

  test("cutovers.paginated() returns full envelope", async () => {
    const result = await withFetch(makeFetch(envelope), (h) => h.cutovers.paginated("proj-1"));
    expect(result.total).toBe(1);
  });

  test("artifacts.listForProject() unwraps envelope", async () => {
    const artEnvelope: PaginatedResponse = {
      items: [{ id: "art-1", kind: "ddl" }],
      total: 1,
      limit: 50,
      offset: 0,
    };
    const result = await withFetch(makeFetch(artEnvelope), (h) => h.artifacts.listForProject("proj-1"));
    expect(result).toEqual([{ id: "art-1", kind: "ddl" }]);
  });

  test("artifacts.listForProjectPaginated() returns full envelope", async () => {
    const artEnvelope: PaginatedResponse = {
      items: [{ id: "art-1" }],
      total: 99,
      limit: 10,
      offset: 0,
    };
    const result = await withFetch(makeFetch(artEnvelope), (h) => h.artifacts.listForProjectPaginated("proj-1"));
    expect(result.total).toBe(99);
  });

  test("projects.list() handles bare array (not-yet-converted endpoint)", async () => {
    const projectsBare = [{ id: "p-1", name: "Oracle → Snowflake" }];
    const result = await withFetch(makeFetch(projectsBare), (h) => h.projects.list());
    expect(result).toEqual(projectsBare);
  });

  test("projects.paginated() synthesises envelope from bare array", async () => {
    const projectsBare = [{ id: "p-1" }, { id: "p-2" }];
    const result = await withFetch(makeFetch(projectsBare), (h) => h.projects.paginated());
    expect(result.items).toEqual(projectsBare);
    expect(result.total).toBe(2);
    expect(result.offset).toBe(0);
  });

  test("templates.list() unwraps envelope", async () => {
    const tplEnvelope: PaginatedResponse = {
      items: [{ id: "tpl-1", source: "oracle", target: "pg" }],
      total: 1,
      limit: 50,
      offset: 0,
    };
    const result = await withFetch(makeFetch(tplEnvelope), (h) => h.templates.list());
    expect(result).toEqual([{ id: "tpl-1", source: "oracle", target: "pg" }]);
  });

  test("templates.paginated() returns envelope shape", async () => {
    const tplEnvelope: PaginatedResponse = {
      items: [{ id: "tpl-1" }],
      total: 5,
      limit: 50,
      offset: 0,
    };
    const result = await withFetch(makeFetch(tplEnvelope), (h) => h.templates.paginated());
    expect(result.total).toBe(5);
  });

  test("knowledge.search() unwraps envelope", async () => {
    const searchEnvelope: PaginatedResponse = {
      items: [{ id: "doc-1", title: "Migration guide" }],
      total: 1,
      limit: 5,
      offset: 0,
    };
    const result = await withFetch(makeFetch(searchEnvelope), (h) => h.knowledge.search("migration"));
    expect(result).toEqual([{ id: "doc-1", title: "Migration guide" }]);
  });

  test("knowledge.searchPaginated() returns full envelope", async () => {
    const searchEnvelope: PaginatedResponse = {
      items: [{ id: "doc-1" }],
      total: 7,
      limit: 5,
      offset: 0,
    };
    const result = await withFetch(makeFetch(searchEnvelope), (h) =>
      h.knowledge.searchPaginated("migration")
    );
    expect(result.total).toBe(7);
  });

  test("_getPaginated() synthesises envelope from bare array", async () => {
    const bare2 = [{ x: 1 }, { x: 2 }];
    const result = await withFetch(makeFetch(bare2), (h) => h._getPaginated("/api/v1/anything"));
    expect(result.total).toBe(2);
    expect(result.items.length).toBe(2);
  });

  test("_getPaginated() preserves envelope from server", async () => {
    const env: PaginatedResponse = { items: [{ x: 99 }], total: 99, limit: 10, offset: 40 };
    const result = await withFetch(makeFetch(env), (h) => h._getPaginated("/api/v1/anything"));
    expect(result.total).toBe(99);
    expect(result.offset).toBe(40);
  });

  test("envelope with null total is preserved", async () => {
    const env: PaginatedResponse = { items: [], total: null, limit: 50, offset: 0 };
    const result = await withFetch(makeFetch(env), (h) => h._getPaginated("/api/v1/anything"));
    expect(result.total).toBeNull();
  });
});

describe("PaginatedResponse type", () => {
  test("PaginatedResponse is importable and structurally valid", () => {
    const pr: PaginatedResponse<{ id: string }> = {
      items: [{ id: "x" }],
      total: 1,
      limit: 10,
      offset: 0,
    };
    expect(pr.items).toHaveLength(1);
  });
});
