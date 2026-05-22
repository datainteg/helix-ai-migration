def test_agent_flow(client):
    """Agent runtime flow — tasks, outputs, prompt registry."""

    client.post("/api/v1/auth/first-admin", json={
        "email": "a@t.com", "name": "A", "password": "Test123!",
        "organization_name": "O", "organization_slug": "o",
    })
    login = client.post("/api/v1/auth/login", json={"email": "a@t.com", "password": "Test123!"})
    token = login.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    # Create project
    resp = client.post("/api/v1/projects", json={"name": "P"}, headers=h)
    pid = resp.json()["id"]

    # Create agent task
    resp = client.post(f"/api/v1/projects/{pid}/agent-tasks", json={"agent_type": "business_analyst"}, headers=h)
    assert resp.status_code == 201
    tid = resp.json()["id"]
    assert resp.json()["status"] == "created"

    # Add output
    resp = client.post(f"/api/v1/agent-tasks/{tid}/outputs", json={
        "schema_name": "ba_output",
        "output_payload": '{"summary": "test"}',
        "confidence_score": 0.85,
    }, headers=h)
    assert resp.status_code == 201
    assert resp.json()["confidence_score"] == 0.85

    # Get outputs
    resp = client.get(f"/api/v1/agent-tasks/{tid}/outputs", headers=h)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Create prompt template
    resp = client.post("/api/v1/prompt-templates", json={
        "name": "ba_requirement_analysis",
        "agent_type": "business_analyst",
        "template": "Analyze migration requirements: {{input}}",
    }, headers=h)
    assert resp.status_code == 201
    tpl_id = resp.json()["id"]

    # Create prompt version
    resp = client.post(f"/api/v1/prompt-templates/{tpl_id}/versions", json={
        "content": "You are a BA agent. Analyze: {{input}}",
    }, headers=h)
    assert resp.status_code == 201
    assert resp.json()["version"] == "1"
