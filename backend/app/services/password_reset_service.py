"""Password reset: generate token, validate, apply new password."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.identity import User, PasswordResetToken
from app.auth.jwt import hash_password

logger = logging.getLogger(__name__)

_TOKEN_TTL_MINUTES = 30

# SEC-004: pre-computed bcrypt hash used to burn ~the same CPU on the
# not-found branch as the found branch. Pre-computed once at import time
# so we are not measuring `gensalt()` work each call.
_DUMMY_BCRYPT_HASH = bcrypt.hashpw(b"helix-pwreset-dummy", bcrypt.gensalt()).decode("utf-8")


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def request_password_reset(db: Session, email: str) -> str | None:
    """Create a reset token for the user. Returns raw token (caller sends via email).
    Returns None if email not found — caller should NOT reveal this to the client.

    SEC-004: equalize wall-clock cost between the found / not-found
    branches by running a dummy bcrypt verification (~60 ms) on the
    not-found path. Without this, an attacker scripting the endpoint
    could distinguish real accounts by latency despite the 202 reply.
    """
    user = db.query(User).filter(User.email == email, User.status == "active").first()
    if not user:
        # Constant-time-ish: burn equivalent CPU so the response latency
        # does not leak user existence. bcrypt.checkpw with a fixed dummy
        # hash is the same shape of work as a real password-derive path.
        try:
            bcrypt.checkpw(b"helix-pwreset-dummy", _DUMMY_BCRYPT_HASH.encode("utf-8"))
        except Exception:  # noqa: BLE001
            pass
        return None

    # M-001: invalidate every still-valid token for this user before minting a
    # fresh one. Previously each request created a new token while leaving all
    # prior ones usable — an attacker who intercepted an earlier reset link kept
    # a 30-minute window even after the legitimate user requested a new link.
    now = datetime.now(timezone.utc)
    (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.user_id == str(user.id),
            PasswordResetToken.used_at.is_(None),
        )
        .update({PasswordResetToken.used_at: now}, synchronize_session=False)
    )

    raw_token = secrets.token_urlsafe(32)
    expires_at = now + timedelta(minutes=_TOKEN_TTL_MINUTES)
    record = PasswordResetToken(
        user_id=str(user.id),
        token_hash=_hash_token(raw_token),
        expires_at=expires_at,
    )
    db.add(record)
    db.commit()
    logger.info("password_reset_token_created user_id=%s", user.id)
    return raw_token


def confirm_password_reset(db: Session, raw_token: str, new_password: str) -> None:
    """Validate token and apply new password. Raises HTTPException on invalid/expired."""
    token_hash = _hash_token(raw_token)
    record = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or already-used reset token")
    if record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset token has expired")

    user = db.query(User).filter(User.id == record.user_id).first()
    if not user or user.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account not active")

    user.password_hash = hash_password(new_password)
    record.used_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("password_reset_completed user_id=%s", user.id)
