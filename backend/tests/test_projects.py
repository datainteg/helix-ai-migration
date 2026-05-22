def test_project_flow(client):
    """Full project workspace flow."""

    # Auth setup
    client.post("/api/v1/auth/first-admin", json={
        "email": "admin@p.com", "name": "Admin", "password": "Test123!",
        "organization_name": "Org", "organization_slug": "org",
    })
    login = client.post("/api/v1/auth/login", json={"email": "admin@p.com", "password": "Test123!"})
    token = login.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    # Create project
    resp = client.post("/api/v1/projects", json={"name": "Migration X", "risk_level": "medium"}, headers=h)
    assert resp.status_code == 201
    pid = resp.json()["id"]

    # List projects
    resp = client.get("/api/v1/projects", headers=h)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Add requirement
    resp = client.post(f"/api/v1/projects/{pid}/requirements", json={"source_text": "Migrate CRM from Oracle to Snowflake"}, headers=h)
    assert resp.status_code == 201

    # Add source
    resp = client.post(f"/api/v1/projects/{pid}/sources", json={"name": "Oracle CRM", "connector_type": "oracle"}, headers=h)
    assert resp.status_code == 201

    # Add target
    resp = client.post(f"/api/v1/projects/{pid}/targets", json={"name": "Snowflake DW", "connector_type": "snowflake"}, headers=h)
    assert resp.status_code == 201

    # Add schema metadata
    resp = client.post(f"/api/v1/projects/{pid}/schemas", json={"name": "public", "schema_type": "source"}, headers=h)
    assert resp.status_code == 201
    sid = resp.json()["id"]

    # Add table
    resp = client.post(f"/api/v1/schemas/{sid}/tables", json={"name": "customers", "row_count": "150000"}, headers=h)
    assert resp.status_code == 201
    tid = resp.json()["id"]

    # Add column
    resp = client.post(f"/api/v1/tables/{tid}/columns", json={"name": "customer_id", "data_type": "NUMBER", "nullable": "NO"}, headers=h)
    assert resp.status_code == 201
