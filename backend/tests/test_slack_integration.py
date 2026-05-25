"""Slack integration tests — signature verification + command routing.

Only unit-tests the signature verifier directly. End-to-end command routing
needs a real Temporal handle so is deferred to a manual smoke test.
"""

import hashlib
import hmac
import time


def test_signature_verifier_accepts_valid():
    from app.api.integrations import _verify_slack_signature
    secret = "test-secret"
    body = b"command=/helix&text=status+wf-1"
    ts = str(int(time.time()))
    digest = hmac.new(secret.encode(), f"v0:{ts}:{body.decode()}".encode(), hashlib.sha256).hexdigest()
    sig = f"v0={digest}"
    assert _verify_slack_signature(secret, body, ts, sig) is True


def test_signature_verifier_rejects_bad_signature():
    from app.api.integrations import _verify_slack_signature
    body = b"command=/helix"
    ts = str(int(time.time()))
    assert _verify_slack_signature("secret", body, ts, "v0=deadbeef") is False


def test_signature_verifier_rejects_stale_timestamp():
    from app.api.integrations import _verify_slack_signature
    secret = "test-secret"
    body = b"command=/helix"
    ts = str(int(time.time()) - 10_000)  # 2.7 hrs old
    digest = hmac.new(secret.encode(), f"v0:{ts}:{body.decode()}".encode(), hashlib.sha256).hexdigest()
    assert _verify_slack_signature(secret, body, ts, f"v0={digest}") is False


def test_signature_verifier_rejects_non_int_timestamp():
    from app.api.integrations import _verify_slack_signature
    assert _verify_slack_signature("s", b"x", "not-a-timestamp", "v0=abc") is False


def test_slash_endpoint_503_when_unconfigured(client, monkeypatch):
    monkeypatch.delenv("SLACK_SIGNING_SECRET", raising=False)
    res = client.post("/api/v1/integrations/slack/command", data="text=status+wf-1")
    assert res.status_code == 503
