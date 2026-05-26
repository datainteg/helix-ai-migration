"""Tiny REST client for the Helix CLI.

No external dependencies beyond `httpx` (already used elsewhere in the repo)
and stdlib. Auth state persists in ~/.helix/config.json so commands don't
need --token on every call.

Pagination envelope (v0.2.0+)
------------------------------
Converted list endpoints now return ``{items: T[], total: int, limit: int,
offset: int}`` instead of a bare array.  All list helpers silently unwrap the
envelope so existing CLI commands keep working unchanged.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

import httpx


_CONFIG_DIR = Path.home() / ".helix"
_CONFIG_FILE = _CONFIG_DIR / "config.json"


def _load_config() -> dict[str, Any]:
    if not _CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_config(cfg: dict[str, Any]) -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    try:
        _CONFIG_FILE.chmod(0o600)
    except Exception:
        pass


def _unwrap(data: Any) -> list[dict]:
    """Return ``data["items"]`` if the response is a pagination envelope,
    otherwise return *data* unchanged (bare-array back-compat)."""
    if isinstance(data, dict) and "items" in data:
        return data["items"]
    return data  # bare-array fallback


class HelixClient:
    """Thin wrapper. Methods return parsed JSON; raise on non-2xx."""

    def __init__(self, api_url: Optional[str] = None, token: Optional[str] = None) -> None:
        cfg = _load_config()
        self.api_url = (api_url or cfg.get("api_url") or os.getenv("HELIX_API_URL") or "http://localhost:8000").rstrip("/")
        self.token = token or cfg.get("token") or os.getenv("HELIX_TOKEN") or ""

    # ── Auth ──────────────────────────────────────────────────────────

    def login(self, email: str, password: str) -> dict:
        res = httpx.post(
            f"{self.api_url}/api/v1/auth/login",
            json={"email": email, "password": password},
            timeout=15,
        )
        self._raise_for(res)
        body = res.json()
        self.token = body["access_token"]
        _save_config({"api_url": self.api_url, "token": self.token, "email": email})
        return body

    def whoami(self) -> dict:
        return self._get("/api/v1/auth/me")

    def logout(self) -> None:
        try:
            self._post("/api/v1/auth/logout", {})
        finally:
            _save_config({"api_url": self.api_url})

    # ── Projects ──────────────────────────────────────────────────────

    def list_projects(self) -> list[dict]:
        return _unwrap(self._get("/api/v1/projects?limit=200"))

    def create_project(self, name: str, description: str = "") -> dict:
        return self._post("/api/v1/projects", {"name": name, "description": description})

    # ── Workflows ─────────────────────────────────────────────────────

    def start_workflow(self, project_id: str, requirement_id: str, requirement_text: str = "") -> dict:
        return self._post(
            f"/api/v1/projects/{project_id}/agent-workflows",
            {"requirement_id": requirement_id, "requirement_text": requirement_text},
        )

    def workflow_status(self, workflow_id: str) -> dict:
        return self._get(f"/api/v1/agent-workflows/{workflow_id}")

    def list_workflows(self, project_id: Optional[str] = None) -> list[dict]:
        if project_id:
            return _unwrap(self._get(f"/api/v1/projects/{project_id}/agent-workflows?limit=100"))
        return _unwrap(self._get("/api/v1/agent-workflows?limit=100"))

    # ── Cost ──────────────────────────────────────────────────────────

    def cost_summary(self, days: int = 30) -> dict:
        return self._get(f"/api/v1/usage/llm?days={days}")

    def cost_limit(self) -> dict:
        return self._get("/api/v1/usage/cost-limit")

    # ── Templates ─────────────────────────────────────────────────────

    def list_templates(self) -> list[dict]:
        return _unwrap(self._get("/api/v1/migration-templates"))

    def clone_template(self, template_id: str, project_name: str) -> dict:
        return self._post(
            "/api/v1/migration-templates/clone",
            {"template_id": template_id, "project_name": project_name},
        )

    # ── Cutovers ──────────────────────────────────────────────────────

    def list_cutovers(self, project_id: str) -> list[dict]:
        return _unwrap(self._get(f"/api/v1/projects/{project_id}/cutovers"))

    def transition_cutover(self, cutover_id: str, target_state: str, notes: str = "") -> dict:
        return self._post(
            f"/api/v1/cutovers/{cutover_id}/transition",
            {"target_state": target_state, "notes": notes},
        )

    # ── Bootstrap (no auth required) ─────────────────────────────────

    def bootstrap_first_admin(
        self,
        email: str,
        password: str,
        name: str,
        org_name: str,
        org_slug: str,
    ) -> dict:
        """POST /api/v1/auth/first-admin.

        Returns the token response on success.
        Raises RuntimeError("already bootstrapped") with status 400 when a
        super-admin already exists (idempotent — callers should exit 0).
        Raises RuntimeError with the HTTP status/detail on any other error.
        """
        res = httpx.post(
            f"{self.api_url}/api/v1/auth/first-admin",
            json={
                "email": email,
                "password": password,
                "name": name,
                "organization_name": org_name,
                "organization_slug": org_slug,
            },
            timeout=30,
        )
        if res.status_code == 400:
            detail = ""
            try:
                detail = res.json().get("detail", "")
            except Exception:
                detail = res.text[:200]
            if "already" in detail.lower() or "exists" in detail.lower():
                raise RuntimeError("already bootstrapped")
            raise RuntimeError(f"400 {detail or res.reason_phrase}")
        self._raise_for(res)
        body = res.json()
        self.token = body["access_token"]
        _save_config({"api_url": self.api_url, "token": self.token, "email": email})
        return body

    # ── Internals ─────────────────────────────────────────────────────

    def _get(self, path: str) -> Any:
        res = httpx.get(f"{self.api_url}{path}", headers=self._headers(), timeout=30)
        self._raise_for(res)
        return res.json()

    def _post(self, path: str, body: dict) -> Any:
        res = httpx.post(f"{self.api_url}{path}", json=body, headers=self._headers(), timeout=60)
        self._raise_for(res)
        return res.json() if res.text else {}

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise RuntimeError("Not logged in. Run `helix login` first.")
        return {"Authorization": f"Bearer {self.token}"}

    @staticmethod
    def _raise_for(res: httpx.Response) -> None:
        if 200 <= res.status_code < 300:
            return
        detail = ""
        try:
            detail = res.json().get("detail", "")
        except Exception:
            detail = res.text[:200]
        raise RuntimeError(f"{res.status_code} {detail or res.reason_phrase}")
