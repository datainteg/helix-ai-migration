"""Tests for agent-workflow read endpoints: list, status-with-steps,
artifacts, artifact-content (incl. path-validation), and cross-org isolation.

These cover the new endpoints added when the frontend `/agents` page was
wired to live backend data.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime


def _login(client, email: str, slug: str) -> str:
    """Bootstrap an org + admin, return their bearer token."""
    client.post(
        "/api/v1/auth/first-admin",
        json={
            "email": email,
            "name": "Tester",
            "password": "Test123!",
            "organization_name": f"Org-{slug}",
            "organization_slug": slug,
        },
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "Test123!"})
    return login.json()["access_token"]


def _seed_workflow(client, token, *, status: str = "completed", mode: str = "local_fallback"):
    """Create project + workflow_run + a couple of steps. Returns workflow_id."""
    from app.db.session import SessionLocal
    from app.models.identity import User
    from app.models.project import Project
    from app.models.workflow import WorkflowRun, WorkflowStep

    h = {"Authorization": f"Bearer {token}"}
    resp = client.post("/api/v1/projects", json={"name": "WF Project"}, headers=h)
    pid = resp.json()["id"]

    # Insert workflow_run + 2 steps directly so the test doesn't depend on
    # the BMAD executor (which would call LLMs).
    db = SessionLocal()
    try:
        proj = db.query(Project).filter(Project.id == pid).first()
        org_id = proj.organization_id
        run = WorkflowRun(
            organization_id=org_id,
            project_id=pid,
            requirement_id="req-1",
            workflow_id=f"bmad-{pid}-req-1",
            run_id="run-1",
            status=status,
            mode=mode,
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # Persist artifact file so artifact-content can read it.
        tmpfile = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
        tmpfile.write("---\nagent: analyst\n---\n# Sample artifact\nbody")
        tmpfile.close()
        artifact_path = tmpfile.name

        step1 = WorkflowStep(
            workflow_run_id=run.id,
            agent_name="analyst",
            step_order=1,
            status="completed",
            raw_output=json.dumps({"summary": "ok", "artifact_paths": [artifact_path]}),
            parsed_output_json={"summary": "ok"},
            provider_name="llm",
            model_name="claude-sonnet-4-6",
        )
        step2 = WorkflowStep(
            workflow_run_id=run.id,
            agent_name="pm",
            step_order=2,
            status="completed",
            raw_output=json.dumps({"summary": "pm ok"}),
            parsed_output_json={"summary": "pm ok"},
            provider_name="mock",
        )
        db.add_all([step1, step2])
        db.commit()
        return run.workflow_id, pid, artifact_path
    finally:
        db.close()


# ── List ─────────────────────────────────────────────────────────────


def test_list_all_workflows_returns_runs_for_org(client):
    token = _login(client, "w1@t.com", "w1")
    wf_id, _, _ = _seed_workflow(client, token)

    resp = client.get("/api/v1/agent-workflows", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert any(r["workflow_id"] == wf_id for r in body)


def test_list_all_workflows_paginates(client):
    token = _login(client, "wp@t.com", "wp")
    for _ in range(3):
        _seed_workflow(client, token)

    resp = client.get(
        "/api/v1/agent-workflows?limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# ── Status with steps ────────────────────────────────────────────────


def test_get_workflow_returns_steps_with_provider(client):
    token = _login(client, "ws@t.com", "ws")
    wf_id, _, _ = _seed_workflow(client, token)

    resp = client.get(
        f"/api/v1/agent-workflows/{wf_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["workflow_id"] == wf_id
    assert body["status"] == "completed"
    assert len(body["steps"]) == 2
    analyst_step = next(s for s in body["steps"] if s["agent_name"] == "analyst")
    assert analyst_step["provider_name"] == "llm"
    assert analyst_step["model_name"] == "claude-sonnet-4-6"
    assert analyst_step["artifact_path"] is not None


def test_get_workflow_404_for_unknown(client):
    token = _login(client, "wm@t.com", "wm")
    resp = client.get(
        "/api/v1/agent-workflows/bmad-nope-nope",
        headers={"Authorization": f"Bearer {token}"},
    )
    # New code: cross-org/unknown workflows return 404.
    assert resp.status_code == 404


def test_get_workflow_cross_org_rejected(client):
    """Org A creates workflow; org B tries to read it — must 404."""
    token_a = _login(client, "a@t.com", "orga")
    wf_id_a, _, _ = _seed_workflow(client, token_a)

    # Second admin in a different org.
    client.post(
        "/api/v1/auth/first-admin",
        json={
            "email": "b@t.com",
            "name": "B",
            "password": "Test123!",
            "organization_name": "Org-B",
            "organization_slug": "orgb",
        },
    )
    # NOTE: first-admin only works once. Use direct DB seed for second org.
    from app.db.session import SessionLocal
    from app.models.identity import Organization, OrganizationMember, Role, User
    from app.services.auth_service import hash_password, _seed_default_roles_and_permissions

    db = SessionLocal()
    try:
        org_b = Organization(name="Org-B-direct", slug="orgb-direct", status="active")
        db.add(org_b)
        db.flush()
        user_b = User(
            email="b2@t.com",
            name="B2",
            password_hash=hash_password("Test123!"),
            is_super_admin=False,
        )
        db.add(user_b)
        db.flush()
        _seed_default_roles_and_permissions(db, org_b.id)
        admin_role = db.query(Role).filter(
            Role.organization_id == org_b.id, Role.name == "admin"
        ).first()
        db.add(OrganizationMember(
            organization_id=org_b.id, user_id=user_b.id, role_id=admin_role.id, status="active",
        ))
        db.commit()
    finally:
        db.close()

    login_b = client.post("/api/v1/auth/login", json={"email": "b2@t.com", "password": "Test123!"})
    token_b = login_b.json()["access_token"]

    resp = client.get(
        f"/api/v1/agent-workflows/{wf_id_a}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404, "cross-org workflow read must be rejected"


# ── Artifacts ────────────────────────────────────────────────────────


def test_list_workflow_artifacts(client):
    token = _login(client, "wa@t.com", "wa")
    wf_id, _, artifact_path = _seed_workflow(client, token)

    resp = client.get(
        f"/api/v1/agent-workflows/{wf_id}/artifacts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["agent_name"] == "analyst"
    assert body[0]["artifact_path"] == artifact_path


def test_read_artifact_content_returns_markdown(client):
    token = _login(client, "wc@t.com", "wc")
    wf_id, _, artifact_path = _seed_workflow(client, token)

    resp = client.get(
        f"/api/v1/agent-workflows/{wf_id}/artifact-content",
        params={"path": artifact_path},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["path"] == artifact_path
    assert "Sample artifact" in body["content"]


def test_read_artifact_content_path_traversal_rejected(client):
    """Path must be in this workflow's allowlist — arbitrary reads must 403."""
    token = _login(client, "wpt@t.com", "wpt")
    wf_id, _, _ = _seed_workflow(client, token)

    resp = client.get(
        f"/api/v1/agent-workflows/{wf_id}/artifact-content",
        params={"path": "/etc/passwd"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_read_artifact_content_missing_file_404(client):
    """If the persisted path no longer exists on disk → 404, not crash."""
    token = _login(client, "wf404@t.com", "wf404")
    wf_id, _, artifact_path = _seed_workflow(client, token)

    # Remove the temp file we created.
    os.remove(artifact_path)

    resp = client.get(
        f"/api/v1/agent-workflows/{wf_id}/artifact-content",
        params={"path": artifact_path},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
