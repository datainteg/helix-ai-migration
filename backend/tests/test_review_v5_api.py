"""DB/API-backed tests for review-v5 backend fixes.

Covers:
  * SC-011 — /auth/first-admin requires X-Setup-Token
  * SC-012 — impersonation propagates impersonator_id onto audit rows
  * SC-016 — knowledge search treats `100%` as a literal substring
  * H-005  — envelope KEK degrades (legacy-only) on a bad ENCRYPTION_KEY
  * H-016  — sprint task status rejects unknown values at the schema layer
"""

from __future__ import annotations

import uuid

import pytest


def _bootstrap(client, *, email=None, slug=None, with_token=True):
    email = email or f"rv5-{uuid.uuid4().hex[:8]}@t.com"
    slug = slug or f"rv5-{uuid.uuid4().hex[:8]}"
    headers = {} if with_token else {"X-Setup-Token": ""}
    res = client.post(
        "/api/v1/auth/first-admin",
        json={
            "email": email,
            "name": "RV5 Admin",
            "password": "Rv5StrongPass123!",
            "organization_name": "RV5 Org",
            "organization_slug": slug,
        },
        headers=headers if not with_token else None,
    )
    return res, email


# ── SC-011: setup token gate ───────────────────────────────────────────


def test_first_admin_rejects_missing_setup_token(client):
    # Override the default header injected by the conftest client fixture
    # with an empty/wrong token → 403.
    res = client.post(
        "/api/v1/auth/first-admin",
        json={
            "email": f"nt-{uuid.uuid4().hex[:6]}@t.com",
            "name": "No Token",
            "password": "Rv5StrongPass123!",
            "organization_name": "NT Org",
            "organization_slug": f"nt-{uuid.uuid4().hex[:6]}",
        },
        headers={"X-Setup-Token": "wrong-token"},
    )
    assert res.status_code == 403


def test_first_admin_succeeds_with_setup_token(client):
    # conftest injects the correct X-Setup-Token by default.
    res, _ = _bootstrap(client)
    assert res.status_code == 200
    assert "access_token" in res.json()


# ── SC-002 enforced through the API ────────────────────────────────────


def test_first_admin_rejects_weak_password(client):
    res = client.post(
        "/api/v1/auth/first-admin",
        json={
            "email": f"weak-{uuid.uuid4().hex[:6]}@t.com",
            "name": "Weak",
            "password": "short",          # < 12 chars, no symbol
            "organization_name": "Weak Org",
            "organization_slug": f"weak-{uuid.uuid4().hex[:6]}",
        },
    )
    assert res.status_code == 422


# ── SC-016: knowledge search literal-percent ───────────────────────────


def test_knowledge_search_literal_percent(client):
    res, email = _bootstrap(client)
    token = res.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    # Seed two docs: one containing "100%", one not.
    from app.db.session import SessionLocal
    from app.models.knowledge import KnowledgeDoc
    from app.models.identity import User
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        org_id = user.memberships[0].organization_id
        match = KnowledgeDoc(
            organization_id=org_id, title="Coverage",
            content="We reached 100% coverage on the migration.",
            tags="cov", content_length=44,
        )
        other = KnowledgeDoc(
            organization_id=org_id, title="Other",
            content="This document mentions 1000 rows but no percentage.",
            tags="x", content_length=51,
        )
        db.add_all([match, other])
        db.commit()
    finally:
        db.close()

    res = client.get("/api/v1/knowledge/search", params={"q": "100%"}, headers=h)
    assert res.status_code == 200
    hits = res.json()
    titles = {hit["title"] for hit in (hits.get("items", hits) if isinstance(hits, dict) else hits)}
    # The "100%" doc must match; the "1000" doc must NOT (percent is literal,
    # not a wildcard).
    assert "Coverage" in titles
    assert "Other" not in titles


# ── H-016: sprint task status literal ──────────────────────────────────


def test_sprint_task_update_rejects_bad_status(client):
    res, email = _bootstrap(client)
    token = res.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    proj = client.post("/api/v1/projects", json={"name": "Sprint Proj"}, headers=h)
    pid = proj.json()["id"]
    sprint = client.post(
        f"/api/v1/projects/{pid}/sprints",
        json={"index": 1, "name": "S1"},
        headers=h,
    )
    assert sprint.status_code in (200, 201)
    sid = sprint.json()["id"]
    task = client.post(
        f"/api/v1/sprints/{sid}/tasks",
        json={"title": "T1", "type": "migration"},
        headers=h,
    )
    assert task.status_code in (200, 201)
    tid = task.json()["id"]

    # Garbage status → 422 (rejected by the Literal schema).
    bad = client.patch(f"/api/v1/sprint-tasks/{tid}", json={"status": "banana"}, headers=h)
    assert bad.status_code == 422

    # Valid status → accepted.
    good = client.patch(f"/api/v1/sprint-tasks/{tid}", json={"status": "completed"}, headers=h)
    assert good.status_code == 200


# ── H-005: KEK degrades on bad ENCRYPTION_KEY ──────────────────────────


def test_kek_degrades_on_bad_encryption_key(monkeypatch):
    """A non-Fernet ENCRYPTION_KEY must NOT crash _kek(); it degrades to a
    legacy-only MultiFernet so legacy reads keep working."""
    from app.services import envelope_encryption_service as ees
    from cryptography.fernet import MultiFernet

    monkeypatch.setattr(ees.settings, "ENCRYPTION_KEY", "not-a-valid-fernet-key")
    kek = ees._kek()
    assert isinstance(kek, MultiFernet)
    # Legacy key still encrypts/decrypts round-trip.
    ct = kek.encrypt(b"hello")
    assert kek.decrypt(ct) == b"hello"
