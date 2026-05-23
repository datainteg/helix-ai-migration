import httpx

from app.services import llm_provider_adapters


class MockHTTPResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


def mock_async_client_factory(monkeypatch, *, status_code: int | None = None, exception: Exception | None = None):
    calls = []

    class MockAsyncClient:
        def __init__(self, timeout: float):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, headers: dict):
            calls.append({"url": url, "timeout": self.timeout, "auth_header_present": "Authorization" in headers})
            if exception:
                raise exception
            return MockHTTPResponse(status_code)

    monkeypatch.setattr(llm_provider_adapters.httpx, "AsyncClient", MockAsyncClient)
    return calls


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

    connection_calls = mock_async_client_factory(monkeypatch, status_code=200)

    resp = client.post(f"/api/v1/llm-providers/{provider_id}/test", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["message"] == "Connected to My OpenAI"
    assert connection_calls == [{
        "url": "https://api.openai.com/v1/models",
        "timeout": 60.0,
        "auth_header_present": True,
    }]
    assert "sk-new-rotated-key-9999" not in resp.text

    mock_async_client_factory(monkeypatch, status_code=401)

    resp = client.post(f"/api/v1/llm-providers/{provider_id}/test", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["message"] == "Authentication failed"

    mock_async_client_factory(monkeypatch, status_code=403)
    resp = client.post(f"/api/v1/llm-providers/{provider_id}/test", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["message"] == "Authentication failed"

    mock_async_client_factory(monkeypatch, status_code=500)
    resp = client.post(f"/api/v1/llm-providers/{provider_id}/test", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["message"] == "Provider returned HTTP 500"

    mock_async_client_factory(monkeypatch, exception=httpx.TimeoutException("timeout"))
    resp = client.post(f"/api/v1/llm-providers/{provider_id}/test", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "timed out" in data["message"]

    mock_async_client_factory(monkeypatch, exception=httpx.ConnectError("connection failed"))
    resp = client.post(f"/api/v1/llm-providers/{provider_id}/test", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "connection failed" in data["message"]

    resp = client.post("/api/v1/llm-agent-mappings", json={
        "agent_type": "business_analyst", "provider_id": provider_id, "model": "claude-3-opus",
    }, headers=headers)
    assert resp.status_code == 201

    resp = client.get("/api/v1/llm-agent-mappings", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
