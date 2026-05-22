import io
import json


def test_code_review_and_approval_flow(client):
    """Full dev workspace flow: upload → analyze → review → convert → approve."""

    client.post("/api/v1/auth/first-admin", json={
        "email": "dev@t.com", "name": "Dev", "password": "Test123!",
        "organization_name": "O", "organization_slug": "o",
    })
    login = client.post("/api/v1/auth/login", json={"email": "dev@t.com", "password": "Test123!"})
    token = login.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    resp = client.post("/api/v1/projects", json={"name": "Dev Project"}, headers=h)
    pid = resp.json()["id"]

    # Upload
    files = {"file": ("etl.py", io.BytesIO(b"import pandas as pd\n\ndf = pd.read_csv('data.csv')\nprint(df.head())"), "text/x-python")}
    resp = client.post(f"/api/v1/projects/{pid}/artifacts/upload", files=files, headers=h)
    assert resp.status_code == 200
    aid = resp.json()["id"]

    # Code Analysis (Task 14-15)
    resp = client.post(f"/api/v1/artifacts/{aid}/analyze", headers=h)
    assert resp.status_code == 200
    analysis = resp.json()
    assert "summary" in analysis
    assert analysis["confidence_score"] is not None

    # Code Review (Task 15)
    resp = client.post(f"/api/v1/artifacts/{aid}/review", headers=h)
    assert resp.status_code == 200
    review = resp.json()
    assert "hardcoded_secrets_detected" in review

    # Get review details
    resp = client.get("/api/v1/code-reviews/nonexistent", headers=h)
    assert resp.status_code == 404

    # Start conversion (Task 16)
    resp = client.post(f"/api/v1/artifacts/{aid}/convert", json={"target_type": "databricks_notebook"}, headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "draft"
    vid = data["conversion_run_id"]

    # Approve (Task 17)
    resp = client.post(f"/api/v1/artifact-versions/{vid}/approve", headers=h)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    # Reject test
    resp = client.post("/api/v1/artifact-versions/nonexistent/reject", headers=h)
    assert resp.status_code == 404

    # Verify version history updated
    resp = client.get(f"/api/v1/artifacts/{aid}/versions", headers=h)
    assert resp.status_code == 200
    versions = resp.json()
    assert len(versions) >= 2  # v1 (uploaded) + v2 (generated draft)
    assert any(v["approval_status"] == "approved" for v in versions)
