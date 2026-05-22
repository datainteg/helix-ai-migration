def test_llm_flow(client):
    """Full LLM provider flow — shared state within one test."""

    client.post("/api/v1/auth/first-admin", json={
        "email": "admin@test.com", "name": "Admin", "password": "Test123!",
        "organization_name": "TestOrg", "organization_slug": "test-org",
    })
    login = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Test123!"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create provider
    resp = client.post("/api/v1/llm-providers", json={
        "provider_type": "openai", "name": "My OpenAI",
        "api_key": "sk-test-key-12345678", "default_model": "gpt-4.1",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My OpenAI"
    assert data["api_key_masked"].count("*") > 5

    # 2. List providers
    resp = client.get("/api/v1/llm-providers", headers=headers)
    assert resp.status_code == 200
    providers = resp.json()
    assert len(providers) >= 1
    provider_id = providers[0]["id"]

    # 3. Key rotation
    resp = client.post(f"/api/v1/llm-providers/{provider_id}/rotate-key", json={
        "new_api_key": "sk-new-rotated-key-9999",
    }, headers=headers)
    assert resp.status_code == 200

    # 4. Test connection
    resp = client.post(f"/api/v1/llm-providers/{provider_id}/test", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # 5. Agent mapping
    resp = client.post("/api/v1/llm-agent-mappings", json={
        "agent_type": "business_analyst", "provider_id": provider_id, "model": "claude-3-opus",
    }, headers=headers)
    assert resp.status_code == 201

    # 6. List mappings
    resp = client.get("/api/v1/llm-agent-mappings", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
