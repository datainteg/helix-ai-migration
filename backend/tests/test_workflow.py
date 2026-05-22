def test_workflow_flow(client):
    """BMAD workflow test — start workflow, check approval gate."""

    client.post("/api/v1/auth/first-admin", json={
        "email": "w@t.com", "name": "W", "password": "Test123!",
        "organization_name": "O", "organization_slug": "o",
    })
    login = client.post("/api/v1/auth/login", json={"email": "w@t.com", "password": "Test123!"})
    token = login.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    # Create project + requirement
    resp = client.post("/api/v1/projects", json={"name": "WF Project"}, headers=h)
    pid = resp.json()["id"]
    resp = client.post(f"/api/v1/projects/{pid}/requirements", json={"source_text": "Migrate X to Y"}, headers=h)
    rid = resp.json()["id"]

    # Start workflow
    resp = client.post(f"/api/v1/projects/{pid}/agent-workflows", json={"requirement_id": rid}, headers=h)
    assert resp.status_code == 200
    wf = resp.json()["workflow"]
    assert wf["status"] in ["approved", "rejected"]

    # Approve step
    resp = client.post("/api/v1/agent-workflows/test-wf-id/approve", json={"decision": "approved", "notes": "Looks good"}, headers=h)
    assert resp.status_code == 200
