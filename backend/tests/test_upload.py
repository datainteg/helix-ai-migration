import io


def test_artifact_upload_flow(client):
    """Test artifact upload API, validation, and metadata."""

    client.post("/api/v1/auth/first-admin", json={
        "email": "up@t.com", "name": "U", "password": "Test123!",
        "organization_name": "O", "organization_slug": "o",
    })
    login = client.post("/api/v1/auth/login", json={"email": "up@t.com", "password": "Test123!"})
    token = login.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    # Create project
    resp = client.post("/api/v1/projects", json={"name": "Upload Project"}, headers=h)
    pid = resp.json()["id"]

    # Upload .py file
    files = {"file": ("script.py", io.BytesIO(b"print('hello')"), "text/x-python")}
    resp = client.post(f"/api/v1/projects/{pid}/artifacts/upload", files=files, headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert data["filename"] == "script.py"
    assert data["file_type"] == "py"
    assert len(data["content_hash"]) == 64

    # Upload .sql file
    files = {"file": ("query.sql", io.BytesIO(b"SELECT 1"), "text/plain")}
    resp = client.post(f"/api/v1/projects/{pid}/artifacts/upload", files=files, headers=h)
    assert resp.status_code == 200

    # Reject unsupported type
    files = {"file": ("data.csv", io.BytesIO(b"a,b,c"), "text/csv")}
    resp = client.post(f"/api/v1/projects/{pid}/artifacts/upload", files=files, headers=h)
    assert resp.status_code == 400

    # List artifacts
    resp = client.get(f"/api/v1/projects/{pid}/artifacts", headers=h)
    assert resp.status_code == 200
    artifacts = resp.json()
    assert len(artifacts) == 2

    # Get versions
    aid = artifacts[0]["id"]
    resp = client.get(f"/api/v1/artifacts/{aid}/versions", headers=h)
    assert resp.status_code == 200
    versions = resp.json()
    assert len(versions) == 1
    assert versions[0]["approval_status"] == "draft"
