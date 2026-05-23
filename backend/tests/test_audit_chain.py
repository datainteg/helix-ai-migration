"""Tests for audit log tamper-evidence (HMAC hash chain)."""

import pytest


def _make_admin(client, db_session):
    """Helper — set up first admin and return auth token."""
    res = client.post("/api/v1/auth/first-admin", json={
        "email": "audit@example.com",
        "name": "Audit Admin",
        "password": "AuditPass123!",
        "organization_name": "Audit Org",
        "organization_slug": f"audit-org-{__import__('uuid').uuid4().hex[:8]}",
    })
    return res.json()["access_token"]


def test_audit_log_has_entry_hash(client, db_session):
    """Audit entries written by write_audit() must have non-null entry_hash."""
    token = _make_admin(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/v1/audit-logs", headers=headers)
    assert res.status_code == 200
    logs = res.json()
    assert len(logs) > 0
    for log in logs:
        assert log.get("entry_hash") is not None, f"Missing entry_hash on log {log['id']}"


def test_audit_chain_verify_passes(client, db_session):
    """Chain integrity check should pass for freshly written logs."""
    token = _make_admin(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/v1/audit-logs/verify", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["integrity"] == "ok"
    assert data["broken"] == []


def test_audit_chain_detects_tampering(client, db_session):
    """Manually corrupting an entry_hash should be detected by /verify."""
    from app.models.observability import AuditLog

    token = _make_admin(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch org_id of the first log
    logs_res = client.get("/api/v1/audit-logs", headers=headers)
    first_log_id = logs_res.json()[-1]["id"]

    # Corrupt the hash directly in DB
    log = db_session.query(AuditLog).filter(AuditLog.id == first_log_id).first()
    log.entry_hash = "deadbeef" * 8
    db_session.commit()

    res = client.get("/api/v1/audit-logs/verify", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["integrity"] == "tampered"
    assert first_log_id in data["broken"]
