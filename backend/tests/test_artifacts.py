import hashlib


def test_artifact_metadata_creation(client):
    """Test artifact metadata and versioning models."""

    client.post("/api/v1/auth/first-admin", json={
        "email": "art@t.com", "name": "A", "password": "Test123!",
        "organization_name": "O", "organization_slug": "o",
    })
    login = client.post("/api/v1/auth/login", json={"email": "art@t.com", "password": "Test123!"})
    token = login.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    # Create project
    resp = client.post("/api/v1/projects", json={"name": "Artifact Project"}, headers=h)
    pid = resp.json()["id"]

    # Verify artifact tables exist by checking imports work
    from app.models.artifacts import CodeArtifact, CodeArtifactVersion, ArtifactApproval
    from app.services.artifact_version_service import hash_content

    test_hash = hash_content(b"print('hello')")
    assert len(test_hash) == 64
    assert test_hash == hashlib.sha256(b"print('hello')").hexdigest()

    # Verify models can be instantiated
    a = CodeArtifact(organization_id="org1", project_id=pid, filename="test.py", file_type="py", storage_path="/tmp/test.py", content_hash=test_hash)
    assert a.file_type == "py"
    assert a.content_hash == test_hash

    v = CodeArtifactVersion(artifact_id="id1", version_number="1", content_hash=test_hash, storage_path="/tmp/test.py", approval_status="draft")
    assert v.approval_status == "draft"

    approval = ArtifactApproval(artifact_version_id="v1", decision="approved", notes="LGTM", approved_by="user1")
    assert approval.decision == "approved"
