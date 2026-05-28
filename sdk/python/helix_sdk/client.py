"""Helix Python SDK client.

Public surface mirrors the CLI commands so users can move between the two
without learning two APIs. Resource namespaces are exposed as attributes
(`helix.projects`, `helix.workflows`, `helix.cost`, …) so call sites read
naturally.

Pagination envelope (v0.2.0+)
------------------------------
Converted list endpoints now return ``{items: T[], total: int, limit: int,
offset: int}`` instead of a bare array.  All ``.list()`` methods silently
unwrap the envelope so existing callers keep working unchanged.  Call the
companion ``paginated_*()`` methods (or use the low-level ``_get_paginated()``
helper) when you need ``total`` / paging metadata.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Optional, TypedDict

import httpx


class HelixError(RuntimeError):
    """Raised when the Helix API returns a non-2xx response."""

    def __init__(self, status: int, detail: str, *, path: str = "") -> None:
        super().__init__(f"{status} {detail} ({path})")
        self.status = status
        self.detail = detail
        self.path = path


class PaginatedResponse(TypedDict):
    """Envelope returned by converted list endpoints."""

    items: list[dict]
    total: Optional[int]
    limit: int
    offset: int


def _unwrap(data: Any) -> list[dict]:
    """Return ``data["items"]`` if the response is a pagination envelope,
    otherwise return *data* unchanged (bare-array back-compat)."""
    if isinstance(data, dict) and "items" in data:
        return data["items"]
    return data  # bare-array fallback


def _as_paginated(data: Any) -> PaginatedResponse:
    """Coerce *data* to a :class:`PaginatedResponse`.

    If the server still returns a bare array (endpoint not yet converted),
    synthesises an envelope with ``total=len(data)``, ``limit=len(data)``,
    ``offset=0`` so callers always see a consistent shape.
    """
    if isinstance(data, dict) and "items" in data:
        return PaginatedResponse(
            items=data["items"],
            total=data.get("total"),
            limit=data.get("limit", len(data["items"])),
            offset=data.get("offset", 0),
        )
    # bare-array fallback
    items: list[dict] = data if isinstance(data, list) else []
    return PaginatedResponse(items=items, total=len(items), limit=len(items), offset=0)


def _paginate_all(
    fetch_page: Callable[[int], PaginatedResponse],
    *,
    max_pages: int = 100,
) -> list[dict]:
    """Walk pagination envelopes by ``offset`` until all rows are collected.

    H-011: callers of ``.list()`` previously saw at most the server-side cap
    (100/200). ``.list_all()`` helpers delegate to this loop so they fetch
    every page transparently. Guarded by ``max_pages`` to prevent runaway
    requests if a buggy server keeps returning the same ``total`` forever.
    """
    collected: list[dict] = []
    offset = 0
    for _ in range(max_pages):
        page = fetch_page(offset)
        items = page.get("items") or []
        collected.extend(items)
        total = page.get("total")
        # Server may not know the true total (None) — fall back to "stop when
        # we get an empty page or a page smaller than the page size".
        page_size = page.get("limit") or len(items) or 1
        if total is not None and len(collected) >= total:
            break
        if not items or len(items) < page_size:
            break
        offset += page_size
    return collected


class _Resource:
    def __init__(self, client: "Helix") -> None:
        self._c = client


class _Projects(_Resource):
    _PAGE_SIZE = 200

    def list(self) -> list[dict]:
        """Return the first page (max ``_PAGE_SIZE`` rows).

        H-011: returns at most ``_PAGE_SIZE`` items even when the org has
        more. Use :meth:`paginated` for ``total`` metadata, or
        :meth:`list_all` to walk every page transparently.
        """
        return _unwrap(self._c._get(f"/api/v1/projects?limit={self._PAGE_SIZE}"))

    def paginated(self, offset: int = 0) -> PaginatedResponse:
        """Return the full pagination envelope for projects."""
        return _as_paginated(
            self._c._get(f"/api/v1/projects?limit={self._PAGE_SIZE}&offset={offset}")
        )

    def list_all(self) -> list[dict]:
        """Walk all pages and return every project (H-011)."""
        return _paginate_all(self.paginated)

    def get(self, project_id: str) -> dict:
        return self._c._get(f"/api/v1/projects/{project_id}")

    def create(self, name: str, description: str = "") -> dict:
        return self._c._post("/api/v1/projects", {"name": name, "description": description})


class _Workflows(_Resource):
    _PAGE_SIZE = 100

    def start(self, project_id: str, requirement_id: str, requirement_text: str = "") -> dict:
        return self._c._post(
            f"/api/v1/projects/{project_id}/agent-workflows",
            {"requirement_id": requirement_id, "requirement_text": requirement_text},
        )

    def status(self, workflow_id: str) -> dict:
        return self._c._get(f"/api/v1/agent-workflows/{workflow_id}")

    def list(self, project_id: Optional[str] = None) -> list[dict]:
        """Return the first page (max ``_PAGE_SIZE`` rows).

        H-011: this is the legacy "first page only" helper. Use
        :meth:`paginated` for ``total`` metadata or :meth:`list_all` to
        walk every page transparently.
        """
        if project_id:
            return _unwrap(
                self._c._get(
                    f"/api/v1/projects/{project_id}/agent-workflows?limit={self._PAGE_SIZE}"
                )
            )
        return _unwrap(self._c._get(f"/api/v1/agent-workflows?limit={self._PAGE_SIZE}"))

    def paginated(
        self,
        project_id: Optional[str] = None,
        offset: int = 0,
    ) -> PaginatedResponse:
        """Return the full pagination envelope for workflows."""
        if project_id:
            return _as_paginated(
                self._c._get(
                    f"/api/v1/projects/{project_id}/agent-workflows?limit={self._PAGE_SIZE}&offset={offset}"
                )
            )
        return _as_paginated(
            self._c._get(f"/api/v1/agent-workflows?limit={self._PAGE_SIZE}&offset={offset}")
        )

    def list_all(self, project_id: Optional[str] = None) -> list[dict]:
        """Walk all pages and return every workflow (H-011)."""
        return _paginate_all(lambda off: self.paginated(project_id, offset=off))

    def approve(self, workflow_id: str, notes: str = "") -> dict:
        return self._c._post(f"/api/v1/agent-workflows/{workflow_id}/signal-approve", {"decision": "approved", "notes": notes})

    def reject(self, workflow_id: str, notes: str = "") -> dict:
        return self._c._post(f"/api/v1/agent-workflows/{workflow_id}/signal-reject", {"decision": "rejected", "notes": notes})

    def replay(self, workflow_id: str, *, agent_prompt_overrides: dict | None = None, model_override: str | None = None) -> dict:
        return self._c._post(f"/api/v1/workflows/{workflow_id}/replay", {
            "agent_prompt_overrides": agent_prompt_overrides or {},
            "model_override": model_override,
        })


class _Cost(_Resource):
    def summary(self, days: int = 30) -> dict:
        return self._c._get(f"/api/v1/usage/llm?days={days}")

    def limit(self) -> dict:
        return self._c._get("/api/v1/usage/cost-limit")

    def set_limit(self, *, daily_usd_cap: float = 0.0, monthly_usd_cap: float = 0.0, enforcement: str = "hard") -> dict:
        return self._c._put("/api/v1/usage/cost-limit", {
            "daily_usd_cap": daily_usd_cap,
            "monthly_usd_cap": monthly_usd_cap,
            "enforcement": enforcement,
        })


class _Templates(_Resource):
    def list(self) -> list[dict]:
        """Return the full migration-template catalog.

        Note: the templates catalog is a static, in-memory list — the
        endpoint returns every entry in one bare-array response (no
        server-side paging). :meth:`list_all` is provided for API symmetry
        and simply returns the same full set.
        """
        return _unwrap(self._c._get("/api/v1/migration-templates"))

    def paginated(self) -> PaginatedResponse:
        """Return a pagination-shaped envelope for migration templates.

        Synthesised from the bare-array response so callers get a consistent
        ``{items,total,limit,offset}`` shape; ``total`` equals the catalog
        size.
        """
        return _as_paginated(self._c._get("/api/v1/migration-templates"))

    def list_all(self) -> list[dict]:
        """Return the full template catalog (H-011 symmetry helper)."""
        return _paginate_all(lambda _off: self.paginated())

    def clone(self, template_id: str, project_name: str, description: str | None = None) -> dict:
        return self._c._post("/api/v1/migration-templates/clone", {
            "template_id": template_id,
            "project_name": project_name,
            "project_description": description,
        })


class _Cutovers(_Resource):
    _PAGE_SIZE = 100

    def list(self, project_id: str) -> list[dict]:
        """Return the first page of cutovers for a project.

        H-011: server-paginated; use :meth:`list_all` to walk every page.
        """
        return _unwrap(
            self._c._get(f"/api/v1/projects/{project_id}/cutovers?limit={self._PAGE_SIZE}")
        )

    def paginated(self, project_id: str, offset: int = 0) -> PaginatedResponse:
        """Return the full pagination envelope for cutovers."""
        return _as_paginated(
            self._c._get(
                f"/api/v1/projects/{project_id}/cutovers?limit={self._PAGE_SIZE}&offset={offset}"
            )
        )

    def list_all(self, project_id: str) -> list[dict]:
        """Walk all pages and return every cutover for a project (H-011)."""
        return _paginate_all(lambda off: self.paginated(project_id, offset=off))

    def create(self, project_id: str, source_ref: str, target_ref: str, *, workflow_id: str | None = None, notes: str | None = None) -> dict:
        return self._c._post(f"/api/v1/projects/{project_id}/cutovers", {
            "source_ref": source_ref, "target_ref": target_ref, "workflow_id": workflow_id, "notes": notes,
        })

    def transition(self, cutover_id: str, target_state: str, notes: str = "") -> dict:
        return self._c._post(f"/api/v1/cutovers/{cutover_id}/transition", {"target_state": target_state, "notes": notes})

    def record_diff(self, cutover_id: str, *, source_count: int, target_count: int, sample_size: int, sample_hash: str | None = None) -> dict:
        diff_pct = 0.0 if source_count == 0 else abs(source_count - target_count) / source_count * 100
        return self._c._post(f"/api/v1/cutovers/{cutover_id}/diff", {
            "source_count": source_count, "target_count": target_count,
            "diff_pct": diff_pct, "sample_size": sample_size, "sample_hash": sample_hash,
        })

    def tail_tick(self, cutover_id: str, *, rows_seen: int, rows_applied: int, lag_seconds: float, high_water_mark: str, notes: str | None = None) -> dict:
        return self._c._post(f"/api/v1/cutovers/{cutover_id}/tail-sync/tick", {
            "rows_seen": rows_seen, "rows_applied": rows_applied,
            "lag_seconds": lag_seconds, "high_water_mark": high_water_mark, "notes": notes,
        })


class _Knowledge(_Resource):
    def upload(self, title: str, content: str, *, source_url: str | None = None, tags: str | None = None) -> dict:
        return self._c._post("/api/v1/knowledge/docs", {
            "title": title, "content": content, "source_url": source_url, "tags": tags,
        })

    def search(self, q: str, limit: int = 5) -> list[dict]:
        """Return the top-``limit`` matching knowledge docs.

        Note: ``/knowledge/search`` is a relevance-ranked top-N endpoint, NOT
        an offset-paginated list (server caps ``limit`` at 20). There is no
        ``search_all`` because the endpoint never returns more than the top-N
        you ask for — raise ``limit`` (up to 20) to widen the result set.
        """
        return _unwrap(self._c._get(f"/api/v1/knowledge/search?q={q}&limit={limit}"))

    def search_paginated(self, q: str, limit: int = 5) -> PaginatedResponse:
        """Return a pagination-shaped envelope for knowledge search results.

        Synthesised from the bare top-N response so callers get a consistent
        ``{items,total,limit,offset}`` shape; there is no true server-side
        offset paging for relevance search.
        """
        return _as_paginated(self._c._get(f"/api/v1/knowledge/search?q={q}&limit={limit}"))


class _SchemaDrift(_Resource):
    def snapshot(self, project_id: str, source_ref: str, schemas: list[str], tables: list[dict]) -> dict:
        return self._c._post(
            f"/api/v1/projects/{project_id}/sources/{source_ref}/schema-snapshots",
            {"schemas": schemas, "tables": tables},
        )

    def drift(self, project_id: str, source_ref: str) -> dict:
        return self._c._get(f"/api/v1/projects/{project_id}/sources/{source_ref}/drift")


class _Artifacts(_Resource):
    _PAGE_SIZE = 100

    def list_for_project(self, project_id: str) -> list[dict]:
        """Return the first page of artifacts for a project.

        H-011: server-paginated; use :meth:`list_all_for_project` to walk
        every page transparently.
        """
        return _unwrap(
            self._c._get(f"/api/v1/projects/{project_id}/artifacts?limit={self._PAGE_SIZE}")
        )

    def list_for_project_paginated(
        self,
        project_id: str,
        offset: int = 0,
    ) -> PaginatedResponse:
        """Return the full pagination envelope for project artifacts."""
        return _as_paginated(
            self._c._get(
                f"/api/v1/projects/{project_id}/artifacts?limit={self._PAGE_SIZE}&offset={offset}"
            )
        )

    def list_all_for_project(self, project_id: str) -> list[dict]:
        """Walk all pages and return every artifact for a project (H-011)."""
        return _paginate_all(
            lambda off: self.list_for_project_paginated(project_id, offset=off)
        )

    def generate_rollback(self, artifact_id: str) -> dict:
        return self._c._post(f"/api/v1/artifacts/{artifact_id}/generate-rollback", {})

    def pair_review(self, artifact_id: str, *, reviewer_model: str | None = None, reviewer_provider_type: str | None = None) -> dict:
        return self._c._post(f"/api/v1/artifacts/{artifact_id}/pair-review", {
            "reviewer_model": reviewer_model, "reviewer_provider_type": reviewer_provider_type,
        })


class Helix:
    """Top-level SDK entry point."""

    def __init__(self, api_url: str, *, token: str = "", timeout: float = 30.0) -> None:
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.timeout = timeout

        self.projects = _Projects(self)
        self.workflows = _Workflows(self)
        self.cost = _Cost(self)
        self.templates = _Templates(self)
        self.cutovers = _Cutovers(self)
        self.knowledge = _Knowledge(self)
        self.schema_drift = _SchemaDrift(self)
        self.artifacts = _Artifacts(self)

    # ── Auth ──────────────────────────────────────────────────────────

    def login(self, email: str, password: str) -> dict:
        res = httpx.post(f"{self.api_url}/api/v1/auth/login", json={"email": email, "password": password}, timeout=self.timeout)
        self._raise_for(res, "/api/v1/auth/login")
        body = res.json()
        self.token = body["access_token"]
        return body

    def whoami(self) -> dict:
        return self._get("/api/v1/auth/me")

    # ── Paginated helper ──────────────────────────────────────────────

    def _get_paginated(self, path: str) -> PaginatedResponse:
        """GET *path* and return a :class:`PaginatedResponse` regardless of
        whether the server sends a bare array or a pagination envelope."""
        return _as_paginated(self._get(path))

    # ── Internals ─────────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise HelixError(401, "No token; call .login() first", path="<auth>")
        return {"Authorization": f"Bearer {self.token}"}

    def _get(self, path: str) -> Any:
        res = httpx.get(f"{self.api_url}{path}", headers=self._headers(), timeout=self.timeout)
        self._raise_for(res, path)
        return res.json()

    def _post(self, path: str, body: dict) -> Any:
        res = httpx.post(f"{self.api_url}{path}", json=body, headers=self._headers(), timeout=self.timeout)
        self._raise_for(res, path)
        return res.json() if res.text else {}

    def _put(self, path: str, body: dict) -> Any:
        res = httpx.put(f"{self.api_url}{path}", json=body, headers=self._headers(), timeout=self.timeout)
        self._raise_for(res, path)
        return res.json() if res.text else {}

    @staticmethod
    def _raise_for(res: httpx.Response, path: str) -> None:
        if 200 <= res.status_code < 300:
            return
        detail = ""
        try:
            # L-010: narrow the parse guard to JSON-decode failures (and the
            # AttributeError when the decoded body isn't a dict) instead of a
            # blanket ``except Exception`` that would also swallow programming
            # errors or KeyboardInterrupt.
            body = res.json()
            detail = body.get("detail", "") if isinstance(body, dict) else ""
        except (ValueError, json.JSONDecodeError):
            detail = res.text[:200]
        raise HelixError(res.status_code, detail or res.reason_phrase, path=path)
