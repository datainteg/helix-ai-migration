from app.auth.jwt import create_access_token, hash_password
from app.models.identity import Organization, OrganizationMember, Role, User
from app.services.auth_service import seed_permissions, seed_roles


def _create_user_in_new_org(db_session, email: str, org_slug: str, role_name: str = "admin") -> tuple[str, str, str]:
    seed_permissions(db_session)

    org = Organization(name=org_slug.title(), slug=org_slug)
    db_session.add(org)
    db_session.flush()
    seed_roles(db_session, org.id)

    role = db_session.query(Role).filter(Role.organization_id == org.id, Role.name == role_name).first()
    user = User(email=email, name=email, password_hash=hash_password("Test123!"))
    db_session.add(user)
    db_session.flush()

    membership = OrganizationMember(organization_id=org.id, user_id=user.id, role_id=role.id)
    db_session.add(membership)
    db_session.commit()

    return create_access_token(str(user.id)), str(user.id), str(org.id)


def test_auth_flow(client):
    """Full auth flow — order matters, state is shared within one test."""

    # 1. First admin setup
    resp = client.post("/api/v1/auth/first-admin", json={
        "email": "admin@helix.datainteg.io",
        "name": "Admin User",
        "password": "SecurePass123!",
        "organization_name": "Acme Corp",
        "organization_slug": "acme-corp",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # 2. Cannot create first admin twice
    resp = client.post("/api/v1/auth/first-admin", json={
        "email": "admin2@helix.datainteg.io",
        "name": "Admin 2",
        "password": "SecurePass456!",
        "organization_name": "Another Org",
        "organization_slug": "another-org",
    })
    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"]

    # 3. Login with correct password
    resp = client.post("/api/v1/auth/login", json={
        "email": "admin@helix.datainteg.io",
        "password": "SecurePass123!",
    })
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # 4. Login with wrong password
    resp = client.post("/api/v1/auth/login", json={
        "email": "admin@helix.datainteg.io",
        "password": "WrongPassword",
    })
    assert resp.status_code == 401

    # 5. Get current user
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    me = resp.json()
    assert me["email"] == "admin@helix.datainteg.io"
    assert me["is_super_admin"] is True

    # 6. Unauthorized without token
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code in [401, 403]


def test_cross_organization_access_is_denied(client, db_session):
    client.post("/api/v1/auth/first-admin", json={
        "email": "org1@helix.datainteg.io",
        "name": "Org One Admin",
        "password": "SecurePass123!",
        "organization_name": "Org One",
        "organization_slug": "org-one",
    })
    login = client.post("/api/v1/auth/login", json={
        "email": "org1@helix.datainteg.io",
        "password": "SecurePass123!",
    })
    org1_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    org2_token, _, _ = _create_user_in_new_org(db_session, "org2@helix.datainteg.io", "org-two")
    org2_headers = {"Authorization": f"Bearer {org2_token}"}

    resp = client.post("/api/v1/projects", json={"name": "Org One Project"}, headers=org1_headers)
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    resp = client.post("/api/v1/llm-providers", json={
        "provider_type": "openai",
        "name": "Org One Provider",
        "api_key": "sk-org-one-key",
        "default_model": "gpt-4.1",
    }, headers=org1_headers)
    assert resp.status_code == 201
    provider_id = resp.json()["id"]

    resp = client.get(f"/api/v1/projects/{project_id}", headers=org2_headers)
    assert resp.status_code == 404

    resp = client.post(
        f"/api/v1/projects/{project_id}/requirements",
        json={"source_text": "Cross org write should fail"},
        headers=org2_headers,
    )
    assert resp.status_code == 404

    resp = client.get("/api/v1/projects", headers=org2_headers)
    assert resp.status_code == 200
    assert resp.json() == []

    resp = client.get(f"/api/v1/llm-providers/{provider_id}", headers=org2_headers)
    assert resp.status_code == 404

    resp = client.get("/api/v1/llm-providers", headers=org2_headers)
    assert resp.status_code == 200
    assert resp.json() == []

    resp = client.post("/api/v1/llm-agent-mappings", json={
        "agent_type": "business_analyst",
        "provider_id": provider_id,
        "model": "gpt-4.1",
    }, headers=org2_headers)
    assert resp.status_code == 404


def test_basic_rbac_denies_viewer_admin_actions(client, db_session):
    viewer_token, _, _ = _create_user_in_new_org(db_session, "viewer@helix.datainteg.io", "viewer-org", "viewer")
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    resp = client.get("/api/v1/llm-providers", headers=viewer_headers)
    assert resp.status_code == 403

    resp = client.post("/api/v1/llm-providers", json={
        "provider_type": "openai",
        "name": "Denied Provider",
        "api_key": "sk-denied",
        "default_model": "gpt-4.1",
    }, headers=viewer_headers)
    assert resp.status_code == 403

    resp = client.get("/api/v1/system/health", headers=viewer_headers)
    assert resp.status_code == 403
