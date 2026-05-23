"""Tests for password reset flow."""

import pytest


def test_reset_request_unknown_email(client):
    """Unknown email always returns 202 (no enumeration)."""
    res = client.post("/api/v1/auth/password-reset/request", json={"email": "nobody@example.com"})
    assert res.status_code == 202
    assert res.json()["status"] == "accepted"


def test_reset_request_and_confirm(client, db_session):
    """Full reset flow: register user → request token → confirm new password."""
    from app.models.identity import User
    from app.auth.jwt import hash_password

    user = User(
        email="reset@example.com",
        name="Reset User",
        password_hash=hash_password("OldPass123!"),
        status="active",
    )
    db_session.add(user)
    db_session.commit()

    res = client.post("/api/v1/auth/password-reset/request", json={"email": "reset@example.com"})
    assert res.status_code == 202

    from app.models.identity import PasswordResetToken
    record = db_session.query(PasswordResetToken).filter(PasswordResetToken.user_id == str(user.id)).first()
    assert record is not None

    import hashlib, secrets
    # We need the raw token — reconstruct from hash by brute-force is impossible.
    # Instead: patch service to return token, or query by user_id and verify confirm endpoint
    # with a directly-generated raw token and its hash stored.
    raw = secrets.token_urlsafe(32)
    record.token_hash = hashlib.sha256(raw.encode()).hexdigest()
    db_session.commit()

    res = client.post("/api/v1/auth/password-reset/confirm", json={"token": raw, "new_password": "NewPass456!"})
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    # Old password no longer works
    res = client.post("/api/v1/auth/login", json={"email": "reset@example.com", "password": "OldPass123!"})
    assert res.status_code == 401

    # New password works
    res = client.post("/api/v1/auth/login", json={"email": "reset@example.com", "password": "NewPass456!"})
    assert res.status_code == 200


def test_confirm_invalid_token(client):
    """Invalid token returns 400."""
    res = client.post("/api/v1/auth/password-reset/confirm", json={"token": "bad-token", "new_password": "x"})
    assert res.status_code == 400


def test_confirm_expired_token(client, db_session):
    """Expired token returns 400."""
    from datetime import datetime, timezone, timedelta
    import hashlib, secrets
    from app.models.identity import User, PasswordResetToken
    from app.auth.jwt import hash_password

    user = User(
        email="expired@example.com",
        name="Expired User",
        password_hash=hash_password("Pass123!"),
        status="active",
    )
    db_session.add(user)
    db_session.flush()

    raw = secrets.token_urlsafe(32)
    record = PasswordResetToken(
        user_id=str(user.id),
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db_session.add(record)
    db_session.commit()

    res = client.post("/api/v1/auth/password-reset/confirm", json={"token": raw, "new_password": "NewPass!"})
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()
