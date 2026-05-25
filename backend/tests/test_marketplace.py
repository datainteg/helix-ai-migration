"""Marketplace catalog tests."""

import uuid


def _admin_token(client):
    res = client.post("/api/v1/auth/first-admin", json={
        "email": "market@example.com",
        "name": "Marketplace Admin",
        "password": "MarketPass123!",
        "organization_name": "Market Org",
        "organization_slug": f"market-{uuid.uuid4().hex[:8]}",
    })
    return res.json()["access_token"]


def test_marketplace_requires_auth(client):
    res = client.get("/api/v1/marketplace")
    assert res.status_code in (401, 403)


def test_marketplace_lists_known_entries(client):
    token = _admin_token(client)
    res = client.get("/api/v1/marketplace", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    ids = {e["id"] for e in res.json()}
    assert "connector-teradata" in ids
    assert "agent-finops" in ids


def test_marketplace_filter_by_kind(client):
    token = _admin_token(client)
    res = client.get("/api/v1/marketplace?kind=agent", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    rows = res.json()
    assert all(r["kind"] == "agent" for r in rows)


def test_marketplace_get_404(client):
    token = _admin_token(client)
    res = client.get("/api/v1/marketplace/does-not-exist", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404
