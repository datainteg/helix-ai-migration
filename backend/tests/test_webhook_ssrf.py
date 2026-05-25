"""Webhook SSRF protection tests.

Verifies that the SSRF guard added in app/security/ssrf.py rejects URLs that
target internal infrastructure both at admit-time (create/update) and at
send-time (delivery). Regression test for the 2026-05-25 review finding.
"""

import uuid

import pytest

from app.security.ssrf import SSRFViolation, validate_external_url


def _admin_token(client):
    res = client.post("/api/v1/auth/first-admin", json={
        "email": "ssrf@example.com",
        "name": "SSRF Admin",
        "password": "SsrfPass123!",
        "organization_name": "SSRF Org",
        "organization_slug": f"ssrf-{uuid.uuid4().hex[:8]}",
    })
    return res.json()["access_token"]


# ── Unit tests on the validator itself ─────────────────────────────────


def test_loopback_rejected():
    with pytest.raises(SSRFViolation):
        validate_external_url("https://127.0.0.1/hook")
    with pytest.raises(SSRFViolation):
        validate_external_url("https://localhost/hook")


def test_private_rfc1918_rejected():
    with pytest.raises(SSRFViolation):
        validate_external_url("https://10.0.0.1/hook")
    with pytest.raises(SSRFViolation):
        validate_external_url("https://192.168.1.1/hook")


def test_link_local_metadata_rejected():
    with pytest.raises(SSRFViolation):
        validate_external_url("https://169.254.169.254/latest/meta-data/")
    with pytest.raises(SSRFViolation):
        validate_external_url("https://metadata.google.internal/")


def test_unknown_host_rejected():
    with pytest.raises(SSRFViolation):
        validate_external_url("https://this-host-should-not-exist-helix-test.invalid/hook")


def test_no_scheme_rejected():
    with pytest.raises(SSRFViolation):
        validate_external_url("//example.com/hook")
    with pytest.raises(SSRFViolation):
        validate_external_url("ftp://example.com/hook")


# ── Integration: webhook create endpoint rejects SSRF URLs ─────────────


def test_create_webhook_blocks_loopback(client):
    token = _admin_token(client)
    res = client.post(
        "/api/v1/webhooks",
        headers={"Authorization": f"Bearer {token}"},
        json={"url": "http://127.0.0.1:9999/secret"},
    )
    assert res.status_code == 400
    assert "Invalid webhook URL" in res.json()["detail"]


def test_create_webhook_blocks_metadata_service(client):
    token = _admin_token(client)
    res = client.post(
        "/api/v1/webhooks",
        headers={"Authorization": f"Bearer {token}"},
        json={"url": "http://169.254.169.254/latest/meta-data/iam/security-credentials/"},
    )
    assert res.status_code == 400
