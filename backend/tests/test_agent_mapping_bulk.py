"""Tests for PUT /llm-agent-mappings — bulk replace endpoint used by the
admin /agent-mapping page's Save button."""

from __future__ import annotations


def _login(client, email: str, slug: str):
    client.post(
        "/api/v1/auth/first-admin",
        json={
            "email": email,
            "name": "Admin",
            "password": "TestPass123!",
            "organization_name": f"Org-{slug}",
            "organization_slug": slug,
        },
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "TestPass123!"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _create_provider(client, h, name: str = "OpenAI Prod") -> str:
    resp = client.post(
        "/api/v1/llm-providers",
        json={
            "provider_type": "openai",
            "name": name,
            "base_url": "https://api.openai.com/v1",
            "default_model": "gpt-4o",
            "api_key": "sk-test-key-not-real",
        },
        headers=h,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_put_replaces_existing_mappings(client):
    h = _login(client, "map@t.com", "map")
    provider_id = _create_provider(client, h)

    payload = [
        {
            "agent_type": "bmad-agent-analyst",
            "provider_id": provider_id,
            "model": "gpt-4o-mini",
            "temperature": 0.2,
            "max_tokens": 2048,
        },
        {
            "agent_type": "bmad-agent-architect",
            "provider_id": provider_id,
            "model": "gpt-4o",
            "temperature": 0.5,
            "max_tokens": 4096,
        },
    ]

    resp = client.put("/api/v1/llm-agent-mappings", json=payload, headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 2
    by_agent = {m["agent_type"]: m for m in body}
    assert by_agent["bmad-agent-analyst"]["model"] == "gpt-4o-mini"
    assert by_agent["bmad-agent-architect"]["temperature"] == 0.5


def test_put_replaces_drops_old_mappings(client):
    h = _login(client, "drop@t.com", "drop")
    provider_id = _create_provider(client, h)

    # Insert 3 mappings.
    client.put(
        "/api/v1/llm-agent-mappings",
        json=[
            {"agent_type": "bmad-agent-analyst", "provider_id": provider_id, "model": "a", "temperature": 0.1, "max_tokens": 100},
            {"agent_type": "bmad-agent-pm", "provider_id": provider_id, "model": "b", "temperature": 0.1, "max_tokens": 100},
            {"agent_type": "bmad-agent-architect", "provider_id": provider_id, "model": "c", "temperature": 0.1, "max_tokens": 100},
        ],
        headers=h,
    )

    # Replace with just 1.
    resp = client.put(
        "/api/v1/llm-agent-mappings",
        json=[
            {"agent_type": "bmad-agent-dev", "provider_id": provider_id, "model": "z", "temperature": 0.1, "max_tokens": 100},
        ],
        headers=h,
    )
    assert resp.status_code == 200
    listing = client.get("/api/v1/llm-agent-mappings", headers=h).json()
    assert len(listing) == 1
    assert listing[0]["agent_type"] == "bmad-agent-dev"


def test_put_rejects_unknown_provider(client):
    h = _login(client, "bad@t.com", "bad")
    resp = client.put(
        "/api/v1/llm-agent-mappings",
        json=[
            {
                "agent_type": "bmad-agent-analyst",
                "provider_id": "00000000-0000-0000-0000-000000000000",
                "model": "x",
                "temperature": 0.1,
                "max_tokens": 100,
            }
        ],
        headers=h,
    )
    assert resp.status_code == 404


def test_put_empty_list_clears_all_mappings(client):
    h = _login(client, "empty@t.com", "empty")
    provider_id = _create_provider(client, h)
    client.put(
        "/api/v1/llm-agent-mappings",
        json=[
            {"agent_type": "bmad-agent-analyst", "provider_id": provider_id, "model": "a", "temperature": 0.1, "max_tokens": 100},
        ],
        headers=h,
    )
    # Reset to empty.
    resp = client.put("/api/v1/llm-agent-mappings", json=[], headers=h)
    assert resp.status_code == 200
    assert resp.json() == []
    listing = client.get("/api/v1/llm-agent-mappings", headers=h).json()
    assert listing == []


def test_put_requires_admin_permission(client):
    """Non-admin users should be rejected by require_permission('admin:llm:write')."""
    h = _login(client, "noperm@t.com", "noperm")
    provider_id = _create_provider(client, h)

    # Demote: create a viewer-role user in same org via direct DB seed.
    from app.db.session import SessionLocal
    from app.models.identity import OrganizationMember, Role, User
    from app.services.auth_service import hash_password

    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.email == "noperm@t.com").first()
        membership = admin_user.memberships[0]
        org_id = membership.organization_id
        viewer_role = db.query(Role).filter(
            Role.organization_id == org_id, Role.name == "viewer"
        ).first()
        if not viewer_role:
            # Some seed flows don't create "viewer" — skip the test in that case.
            import pytest
            pytest.skip("viewer role not seeded for this org")

        viewer_user = User(
            email="viewer@t.com",
            name="Viewer",
            password_hash=hash_password("TestPass123!"),
            is_super_admin=False,
        )
        db.add(viewer_user)
        db.flush()
        db.add(OrganizationMember(
            organization_id=org_id,
            user_id=viewer_user.id,
            role_id=viewer_role.id,
            status="active",
        ))
        db.commit()
    finally:
        db.close()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "viewer@t.com", "password": "TestPass123!"},
    )
    viewer_h = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.put(
        "/api/v1/llm-agent-mappings",
        json=[
            {
                "agent_type": "bmad-agent-analyst",
                "provider_id": provider_id,
                "model": "x",
                "temperature": 0.1,
                "max_tokens": 100,
            }
        ],
        headers=viewer_h,
    )
    assert resp.status_code == 403
