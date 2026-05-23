import io
from pathlib import Path

from app.core.config import settings
from app.storage.local import build_safe_artifact_path, sanitize_filename


def test_safe_filename_sanitization_cases():
    assert sanitize_filename("../../evil.py") == "evil.py"
    assert sanitize_filename("..\\evil.py") == "evil.py"
    assert sanitize_filename("normal.py") == "normal.py"
    assert sanitize_filename("file name with spaces.py") == "file_name_with_spaces.py"
    assert sanitize_filename("weird#$name.sql") == "weird__name.sql"


def test_safe_artifact_path_is_generated_under_storage_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ARTIFACT_STORAGE_PATH", str(tmp_path))

    unsafe_filenames = [
        "../../evil.py",
        "..\\evil.py",
        "normal.py",
        "file name with spaces.py",
        "weird#$name.sql",
    ]

    for filename in unsafe_filenames:
        path = build_safe_artifact_path("project-1", filename)
        path.resolve().relative_to(tmp_path.resolve())
        assert path.parent.name == "project-1"
        assert path.name != sanitize_filename(filename)
        assert len(path.stem) == 32
        assert path.suffix == Path(sanitize_filename(filename)).suffix.lower()


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


def test_artifact_upload_with_unsafe_filename_stays_inside_storage_root(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ARTIFACT_STORAGE_PATH", str(tmp_path))

    client.post("/api/v1/auth/first-admin", json={
        "email": "unsafe@t.com", "name": "U", "password": "Test123!",
        "organization_name": "O", "organization_slug": "o",
    })
    login = client.post("/api/v1/auth/login", json={"email": "unsafe@t.com", "password": "Test123!"})
    token = login.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    resp = client.post("/api/v1/projects", json={"name": "Unsafe Upload Project"}, headers=h)
    pid = resp.json()["id"]

    files = {"file": ("../../evil.py", io.BytesIO(b"print('safe')"), "text/x-python")}
    resp = client.post(f"/api/v1/projects/{pid}/artifacts/upload", files=files, headers=h)

    assert resp.status_code == 200
    data = resp.json()
    stored_path = Path(data["storage_path"]).resolve()
    stored_path.relative_to(tmp_path.resolve())
    assert data["filename"] == "../../evil.py"
    assert stored_path.name != "evil.py"
    assert stored_path.suffix == ".py"
    assert stored_path.read_bytes() == b"print('safe')"
