from app.api import llm_providers as llm_providers_api
from app.schemas.llm import TestConnectionResponse as LLMTestConnectionResponse


def test_llm_flow_uses_mocked_provider_connection(client, monkeypatch):
    """Full LLM provider flow with no real external LLM API calls."""

    client.post("/api/v1/auth/first-admin", json={
        "email": "admin@test.com", "name": "Admin", "password": "Test123!",
        "organization_name": "TestOrg", "organization_slug": "test-org",
    })
    login = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Test123!"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post("/api/v1/llm-providers", json={
        "provider_type": "openai", "name": "My OpenAI",
        "api_key": "sk-test-key-12345678", "default_model": "gpt-4.1",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My OpenAI"
    assert data["api_key_masked"].count("*") > 5
    assert "api_key" not in data
    assert "sk-test-key-12345678" not in resp.text

    resp = client.get("/api/v1/llm-providers", headers=headers)
    assert resp.status_code == 200
    providers = resp.json()
    assert len(providers) >= 1
    provider_id = providers[0]["id"]
    assert "sk-test-key-12345678" not in resp.text

    resp = client.get(f"/api/v1/llm-providers/{provider_id}", headers=headers)
    assert resp.status_code == 200
    assert "api_key" not in resp.json()
    assert "sk-test-key-12345678" not in resp.text

    resp = client.post(f"/api/v1/llm-providers/{provider_id}/rotate-key", json={
        "new_api_key": "sk-new-rotated-key-9999",
    }, headers=headers)
    assert resp.status_code == 200
    assert "sk-new-rotated-key-9999" not in resp.text

    connection_calls = []

    async def mock_connection_success(db, org_id: str, provider_id: str):
        connection_calls.append(provider_id)
        return LLMTestConnectionResponse(success=True, message="mocked provider reachable")

    monkeypatch.setattr(llm_providers_api, "test_connection", mock_connection_success)

    resp = client.post(f"/api/v1/llm-providers/{provider_id}/test", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["message"] == "mocked provider reachable"
    assert connection_calls == [provider_id]

    async def mock_connection_failure(db, org_id: str, provider_id: str):
        return LLMTestConnectionResponse(success=False, message="mocked authentication failed")

    monkeypatch.setattr(llm_providers_api, "test_connection", mock_connection_failure)

    resp = client.post(f"/api/v1/llm-providers/{provider_id}/test", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["message"] == "mocked authentication failed"

    resp = client.post("/api/v1/llm-agent-mappings", json={
        "agent_type": "business_analyst", "provider_id": provider_id, "model": "claude-3-opus",
    }, headers=headers)
    assert resp.status_code == 201

    resp = client.get("/api/v1/llm-agent-mappings", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
