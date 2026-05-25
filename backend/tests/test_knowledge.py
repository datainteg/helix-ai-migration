"""Knowledge-base upload + search tests."""

import uuid


def _admin_token(client):
    res = client.post("/api/v1/auth/first-admin", json={
        "email": "kb@example.com",
        "name": "KB Admin",
        "password": "KbPass1234!",
        "organization_name": "KB Org",
        "organization_slug": f"kb-{uuid.uuid4().hex[:8]}",
    })
    return res.json()["access_token"]


def test_upload_and_list(client):
    token = _admin_token(client)
    h = {"Authorization": f"Bearer {token}"}

    res = client.post(
        "/api/v1/knowledge/docs", headers=h,
        json={"title": "Oracle GL schema", "content": "Table AR_PAYMENT has columns id, amount, currency.", "tags": "oracle,gl"},
    )
    assert res.status_code == 201

    listed = client.get("/api/v1/knowledge/docs", headers=h)
    assert listed.status_code == 200
    titles = [d["title"] for d in listed.json()]
    assert "Oracle GL schema" in titles


def test_search_returns_excerpt(client):
    token = _admin_token(client)
    h = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/knowledge/docs", headers=h, json={
        "title": "Snowflake migration runbook",
        "content": "Use COPY INTO from S3 staging. NUMBER(p,s) maps to NUMBER. Never use implicit NUMBER.",
        "tags": "snowflake,runbook",
    })

    res = client.get("/api/v1/knowledge/search?q=COPY+INTO&limit=5", headers=h)
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) >= 1
    assert "COPY INTO" in rows[0]["excerpt"]


def test_search_min_length(client):
    token = _admin_token(client)
    h = {"Authorization": f"Bearer {token}"}
    res = client.get("/api/v1/knowledge/search?q=a", headers=h)
    assert res.status_code == 422  # pydantic min_length=2


def test_delete_doc(client):
    token = _admin_token(client)
    h = {"Authorization": f"Bearer {token}"}
    create = client.post("/api/v1/knowledge/docs", headers=h, json={"title": "Disposable", "content": "delete me"})
    doc_id = create.json()["id"]
    res = client.delete(f"/api/v1/knowledge/docs/{doc_id}", headers=h)
    assert res.status_code == 204
    follow = client.get(f"/api/v1/knowledge/docs/{doc_id}", headers=h)
    assert follow.status_code == 404
