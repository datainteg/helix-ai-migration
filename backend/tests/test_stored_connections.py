"""Tests for stored-connection encryption + test/discover endpoints.

Covers the new flow added with the connector-encryption work:
  - POST /projects/{pid}/sources persists Fernet-encrypted config + masked preview
  - GET response masks sensitive fields, never returns plaintext
  - PATCH rotates credentials
  - DELETE removes
  - /sources/{sid}/test uses stored creds (no inline config required)
  - /sources/{sid}/discover/schemas does the same
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch


def _login(client, email: str, slug: str) -> tuple[str, str]:
    """Bootstrap an org + admin, return (bearer_token, project_id)."""
    client.post(
        "/api/v1/auth/first-admin",
        json={
            "email": email,
            "name": "Tester",
            "password": "Test123!",
            "organization_name": f"Org-{slug}",
            "organization_slug": slug,
        },
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "Test123!"})
    token = login.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    proj = client.post("/api/v1/projects", json={"name": "P"}, headers=h)
    return token, proj.json()["id"]


# ── Create + mask ────────────────────────────────────────────────────


def test_create_source_encrypts_config_and_returns_mask(client):
    token, pid = _login(client, "sc@t.com", "sc")
    h = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        f"/api/v1/projects/{pid}/sources",
        json={
            "name": "Prod DB",
            "connector_type": "postgres",
            "config": {
                "host": "db.example.com",
                "port": 5432,
                "username": "admin",
                "password": "supersecret123",
            },
        },
        headers=h,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Prod DB"
    assert body["connector_type"] == "postgres"
    # Mask must hide the password.
    assert body["config_masked"] is not None
    assert "supersecret123" not in body["config_masked"]
    assert "***t123" in body["config_masked"]  # last 4 visible
    assert "db.example.com" in body["config_masked"]  # host plaintext OK


def test_create_target_encrypts_aws_keys(client):
    token, pid = _login(client, "tg@t.com", "tg")
    h = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        f"/api/v1/projects/{pid}/targets",
        json={
            "name": "Backup Bucket",
            "connector_type": "s3",
            "config": {
                "bucket": "my-bucket",
                "access_key_id": "AKIAEXAMPLEAAAA1234",
                "secret_access_key": "supersecretAWS123",
                "region": "us-east-1",
            },
        },
        headers=h,
    )
    assert resp.status_code == 201
    masked = resp.json()["config_masked"]
    assert "supersecretAWS123" not in masked
    assert "AKIAEXAMPLEAAAA1234" not in masked
    assert "my-bucket" in masked


def test_get_response_never_returns_plaintext_config(client):
    """Response model has no `config` field — only `config_masked`."""
    token, pid = _login(client, "np@t.com", "np")
    h = {"Authorization": f"Bearer {token}"}
    client.post(
        f"/api/v1/projects/{pid}/sources",
        json={"name": "X", "connector_type": "postgres", "config": {"password": "secret"}},
        headers=h,
    )
    listing = client.get(f"/api/v1/projects/{pid}/sources", headers=h).json()
    assert listing
    for row in listing:
        assert "config" not in row, "raw config must never appear in API response"
        assert "encrypted_config" not in row


# ── Update + delete ──────────────────────────────────────────────────


def test_patch_source_rotates_credentials(client):
    token, pid = _login(client, "rot@t.com", "rot")
    h = {"Authorization": f"Bearer {token}"}
    created = client.post(
        f"/api/v1/projects/{pid}/sources",
        json={"name": "DB", "connector_type": "postgres", "config": {"password": "old123"}},
        headers=h,
    ).json()
    sid = created["id"]

    patched = client.patch(
        f"/api/v1/projects/{pid}/sources/{sid}",
        json={"config": {"password": "newPassword456"}},
        headers=h,
    )
    assert patched.status_code == 200
    masked = patched.json()["config_masked"]
    assert "old123" not in masked
    assert "***d456" in masked


def test_delete_source_removes_row(client):
    token, pid = _login(client, "del@t.com", "del")
    h = {"Authorization": f"Bearer {token}"}
    created = client.post(
        f"/api/v1/projects/{pid}/sources",
        json={"name": "DB", "connector_type": "postgres", "config": {"password": "x"}},
        headers=h,
    ).json()
    sid = created["id"]

    resp = client.delete(f"/api/v1/projects/{pid}/sources/{sid}", headers=h)
    assert resp.status_code == 204

    listing = client.get(f"/api/v1/projects/{pid}/sources", headers=h).json()
    assert all(r["id"] != sid for r in listing)


# ── Test + discover using stored creds ──────────────────────────────


def test_stored_connection_test_uses_decrypted_config(client):
    """The /test endpoint should pass DECRYPTED config to the connector service."""
    token, pid = _login(client, "tst@t.com", "tst")
    h = {"Authorization": f"Bearer {token}"}
    sid = client.post(
        f"/api/v1/projects/{pid}/sources",
        json={
            "name": "DB",
            "connector_type": "postgres",
            "config": {"host": "db", "password": "secret_password"},
        },
        headers=h,
    ).json()["id"]

    # Patch the connector test to capture what config it received.
    from app.services import connector_service as svc

    class FakeResult:
        success = True
        message = "ok"

    captured = {}

    async def fake_test(connector_type, config):
        captured["connector_type"] = connector_type
        captured["config"] = config
        return FakeResult()

    with patch.object(svc, "test_connection", new=fake_test):
        resp = client.post(
            f"/api/v1/projects/{pid}/sources/{sid}/test",
            headers=h,
        )

    assert resp.status_code == 200
    assert resp.json()["success"] is True
    # Decrypted config reached the connector service intact.
    assert captured["connector_type"] == "postgres"
    assert captured["config"]["host"] == "db"
    assert captured["config"]["password"] == "secret_password"


def test_stored_connection_test_400_when_no_creds(client):
    token, pid = _login(client, "noc@t.com", "noc")
    h = {"Authorization": f"Bearer {token}"}
    # Create without config.
    sid = client.post(
        f"/api/v1/projects/{pid}/sources",
        json={"name": "Bare", "connector_type": "postgres"},
        headers=h,
    ).json()["id"]

    resp = client.post(f"/api/v1/projects/{pid}/sources/{sid}/test", headers=h)
    assert resp.status_code == 400


def test_stored_connection_test_404_for_unknown(client):
    token, pid = _login(client, "unk@t.com", "unk")
    h = {"Authorization": f"Bearer {token}"}
    resp = client.post(f"/api/v1/projects/{pid}/sources/00000000-no/test", headers=h)
    assert resp.status_code == 404


def test_stored_connection_discover_schemas(client):
    token, pid = _login(client, "disc@t.com", "disc")
    h = {"Authorization": f"Bearer {token}"}
    sid = client.post(
        f"/api/v1/projects/{pid}/sources",
        json={"name": "DB", "connector_type": "postgres", "config": {"password": "x"}},
        headers=h,
    ).json()["id"]

    from app.services import connector_service as svc

    class FakeSchema:
        schema_name = "public"

    async def fake_discover(connector_type, config):
        return [FakeSchema()]

    with patch.object(svc, "discover_schemas", new=fake_discover):
        resp = client.post(
            f"/api/v1/projects/{pid}/sources/{sid}/discover/schemas",
            headers=h,
        )

    assert resp.status_code == 200
    assert resp.json() == [{"schema_name": "public"}]
