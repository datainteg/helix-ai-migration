def test_auth_flow(client):
    """Full auth flow — order matters, state is shared within one test."""

    # 1. First admin setup
    resp = client.post("/api/v1/auth/first-admin", json={
        "email": "admin@helix.datainteg.io",
        "name": "Admin User",
        "password": "Secure123!",
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
        "password": "Secure456!",
        "organization_name": "Another Org",
        "organization_slug": "another-org",
    })
    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"]

    # 3. Login with correct password
    resp = client.post("/api/v1/auth/login", json={
        "email": "admin@helix.datainteg.io",
        "password": "Secure123!",
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
