"""Helix Python SDK client.

Public surface mirrors the CLI commands so users can move between the two
without learning two APIs. Resource namespaces are exposed as attributes
(`helix.projects`, `helix.workflows`, `helix.cost`, …) so call sites read
naturally.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx


class HelixError(RuntimeError):
    """Raised when the Helix API returns a non-2xx response."""

    def __init__(self, status: int, detail: str, *, path: str = "") -> None:
        super().__init__(f"{status} {detail} ({path})")
        self.status = status
        self.detail = detail
        self.path = path


class _Resource:
    def __init__(self, client: "Helix") -> None:
        self._c = client


class _Projects(_Resource):
    def list(self) -> list[dict]:
        return self._c._get("/api/v1/projects?limit=200")

    def get(self, project_id: str) -> dict:
        return self._c._get(f"/api/v1/projects/{project_id}")

    def create(self, name: str, description: str = "") -> dict:
        return self._c._post("/api/v1/projects", {"name": name, "description": description})


class _Workflows(_Resource):
    def start(self, project_id: str, requirement_id: str, requirement_text: str = "") -> dict:
        return self._c._post(
            f"/api/v1/projects/{project_id}/agent-workflows",
            {"requirement_id": requirement_id, "requirement_text": requirement_text},
        )

    def status(self, workflow_id: str) -> dict:
        return self._c._get(f"/api/v1/agent-workflows/{workflow_id}")

    def list(self, project_id: Optional[str] = None) -> list[dict]:
        if project_id:
            return self._c._get(f"/api/v1/projects/{project_id}/agent-workflows?limit=100")
        return self._c._get("/api/v1/agent-workflows?limit=100")

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
        return self._c._get("/api/v1/migration-templates")

    def clone(self, template_id: str, project_name: str, description: str | None = None) -> dict:
        return self._c._post("/api/v1/migration-templates/clone", {
            "template_id": template_id,
            "project_name": project_name,
            "project_description": description,
        })


class _Cutovers(_Resource):
    def list(self, project_id: str) -> list[dict]:
        return self._c._get(f"/api/v1/projects/{project_id}/cutovers")

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
        return self._c._get(f"/api/v1/knowledge/search?q={q}&limit={limit}")


class _SchemaDrift(_Resource):
    def snapshot(self, project_id: str, source_ref: str, schemas: list[str], tables: list[dict]) -> dict:
        return self._c._post(
            f"/api/v1/projects/{project_id}/sources/{source_ref}/schema-snapshots",
            {"schemas": schemas, "tables": tables},
        )

    def drift(self, project_id: str, source_ref: str) -> dict:
        return self._c._get(f"/api/v1/projects/{project_id}/sources/{source_ref}/drift")


class _Artifacts(_Resource):
    def list_for_project(self, project_id: str) -> list[dict]:
        return self._c._get(f"/api/v1/projects/{project_id}/artifacts")

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
            detail = res.json().get("detail", "")
        except Exception:
            detail = res.text[:200]
        raise HelixError(res.status_code, detail or res.reason_phrase, path=path)
