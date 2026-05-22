import io


def test_val_audit_health_flow(client):
    """Test validation, audit, and health endpoints."""

    client.post("/api/v1/auth/first-admin", json={
        "email": "final@t.com", "name": "F", "password": "Test123!",
        "organization_name": "O", "organization_slug": "o",
    })
    login = client.post("/api/v1/auth/login", json={"email": "final@t.com", "password": "Test123!"})
    token = login.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    resp = client.post("/api/v1/projects", json={"name": "Final Project"}, headers=h)
    pid = resp.json()["id"]

    # Validation rule
    resp = client.post(f"/api/v1/projects/{pid}/validation-rules", json={"rule_type": "row_count", "target_ref": "customers"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["rule_type"] == "row_count"

    # List rules
    resp = client.get(f"/api/v1/projects/{pid}/validation-rules", headers=h)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Start validation run
    resp = client.post(f"/api/v1/projects/{pid}/validation-runs", headers=h)
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"

    # Start recon run
    resp = client.post(f"/api/v1/projects/{pid}/recon-runs", headers=h)
    assert resp.status_code == 200
    assert "difference" in resp.json()["summary"].lower()

    # Audit logs
    resp = client.get("/api/v1/audit-logs", headers=h)
    assert resp.status_code == 200

    # System health
    resp = client.get("/api/v1/system/health", headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert len(data["components"]) >= 4

    # Worker status
    resp = client.get("/api/v1/system/workers", headers=h)
    assert resp.status_code == 200

    # Failed jobs
    resp = client.get("/api/v1/system/failed-jobs", headers=h)
    assert resp.status_code == 200
